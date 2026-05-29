"""MCP 服务基类

提供所有 MCP 服务的共享基础设施:
- 线程安全的异步锁管理
- 连接错误检测
- MCP 客户端初始化与重置
- 工具查询与调用（含超时和断线重连）
- 健康检查
- 结果解析
- 单例工厂

子类只需实现 _build_mcp_config() 和域名业务方法。
"""

import asyncio
import json
import threading
from typing import Any, Dict, List, Optional, TypeVar, Callable

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

T = TypeVar("T", bound="BaseMCPService")


class BaseMCPService:
    """MCP 服务抽象基类

    子类覆写 _service_name 和 _build_mcp_config() 即可获得完整的 MCP 客户端管理能力。
    """

    _service_name: str = "MCP"

    _CONNECTION_ERROR_KEYWORDS: List[str] = [
        "connection", "connect", "timeout", "timed out",
        "sse", "eof", "broken pipe", "reset", "refused",
        "network", "unreachable", "host", "dns",
    ]

    def __init__(self):
        self._client: Optional[MultiServerMCPClient] = None
        self._tools: Optional[List[BaseTool]] = None
        self._async_lock: Optional[asyncio.Lock] = None

    # ---- 子类必须实现 ----

    def _build_mcp_config(self) -> Dict[str, Any]:
        """构建 MultiServerMCPClient 配置字典"""
        raise NotImplementedError(
            f"{self.__class__.__name__} 必须实现 _build_mcp_config()"
        )

    # ---- 连接错误检测 ----

    @classmethod
    def _is_connection_error(cls, e: Exception) -> bool:
        if isinstance(e, (ConnectionError, ConnectionResetError, ConnectionAbortedError, OSError)):
            return True
        if isinstance(e, asyncio.TimeoutError):
            return True
        msg = str(e).lower()
        return any(kw in msg for kw in cls._CONNECTION_ERROR_KEYWORDS)

    # ---- 异步锁 ----

    def _get_async_lock(self) -> asyncio.Lock:
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    # ---- 客户端生命周期 ----

    async def _init_client(self) -> None:
        """初始化 MCP 客户端（双重检查锁定，幂等）"""
        if self._client is not None and self._tools is not None:
            return

        async with self._get_async_lock():
            if self._client is not None and self._tools is not None:
                return

            config = self._build_mcp_config()
            self._client = MultiServerMCPClient(config)
            self._tools = await self._client.get_tools()

            print(f"✅ {self._service_name} MCP 适配器初始化成功")
            print(f"   工具数量: {len(self._tools)}")
            if self._tools:
                print("   可用工具:")
                for t in self._tools:
                    print(f"     - {t.name}")
                if len(self._tools) > 5:
                    print(f"     ... 还有 {len(self._tools) - 5} 个工具")

    async def _reset_client(self) -> None:
        """重置 MCP 客户端（连接异常时调用）"""
        async with self._get_async_lock():
            if self._client is not None:
                try:
                    if hasattr(self._client, 'close'):
                        await self._client.close()
                except Exception:
                    pass
            self._client = None
            self._tools = None
            print(f"🔄 {self._service_name} MCP 客户端已重置，将在下次调用时重新连接")

    # ---- 工具查询 ----

    async def get_tools(self) -> List[BaseTool]:
        await self._init_client()
        return self._tools  # type: ignore[return-value]

    async def get_tool(self, name: str) -> Optional[BaseTool]:
        tools = await self.get_tools()
        for t in tools:
            if t.name == name or t.name.lower() == name.lower():
                return t
        return None

    # ---- 核心调用 ----

    async def _call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Any:
        """调用 MCP 工具，含超时和断线自动重连"""
        await self._init_client()
        tool = await self.get_tool(tool_name)
        if tool is None:
            raise ValueError(f"{self._service_name} MCP 工具不存在: {tool_name}")

        try:
            result = await asyncio.wait_for(
                tool.ainvoke(arguments), timeout=timeout
            )
            return result
        except Exception as e:
            if self._is_connection_error(e):
                print(f"🔄 {self._service_name} MCP 连接异常 [{tool_name}]: {str(e)[:150]}")
                print("   尝试重置客户端并重新连接...")
                await self._reset_client()
                try:
                    await self._init_client()
                    tool = await self.get_tool(tool_name)
                    if tool is None:
                        raise ValueError(
                            f"重连后{self._service_name} MCP 工具仍不存在: {tool_name}"
                        )
                    result = await asyncio.wait_for(
                        tool.ainvoke(arguments), timeout=timeout
                    )
                    print(f"✅ {self._service_name} MCP 重连后工具调用成功 [{tool_name}]")
                    return result
                except Exception as reconnect_err:
                    print(f"❌ {self._service_name} MCP 重连后调用仍失败 [{tool_name}]: {str(reconnect_err)[:150]}")
                    raise
            raise

    # ---- 健康检查 ----

    async def health_check(self) -> bool:
        try:
            await self._init_client()
            return self._tools is not None and len(self._tools) > 0
        except Exception:
            return False

    # ---- 结果解析 ----

    @staticmethod
    def _parse_result(result: Any) -> Any:
        if isinstance(result, (dict, list)):
            return result
        if isinstance(result, str):
            try:
                return json.loads(result)
            except (json.JSONDecodeError, TypeError):
                return {"raw_result": result}
        return {"raw_result": str(result)}


def get_service_singleton(
    key: str,
    factory: Callable[[], Optional[T]],
) -> Optional[T]:
    """线程安全的服务单例获取器

    Args:
        key: 单例注册键
        factory: 返回服务实例或 None 的工厂函数

    Returns:
        服务单例，或 None（工厂返回 None 时）
    """
    return factory()
