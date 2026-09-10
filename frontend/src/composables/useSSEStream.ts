import { onUnmounted, ref } from 'vue'

/** 组件卸载时自动 abort 的 AbortController，避免 SSE 流在页面切换后继续写入已卸载组件的 ref */
export function useAbortController() {
  const controller = new AbortController()
  const aborted = ref(false)

  const abort = (reason?: string) => {
    if (!aborted.value) {
      aborted.value = true
      controller.abort(reason)
    }
  }

  onUnmounted(() => abort('component unmounted'))

  return { signal: controller.signal, abort, aborted }
}

export interface UseSSEStreamOptions<T> {
  /** 实际发起流式请求的函数，需把 signal 透传给底层 fetch */
  start: (signal: AbortSignal, onHeartbeat: () => void) => Promise<void>
  onEvent: (event: T) => void
  onError?: (error: Error) => void
  onDone?: () => void
  /** 断流自动重试次数（仅在收到 complete 之前断流时重试） */
  retries?: number
  retryDelay?: number
}

/**
 * 统一的 SSE 生命周期管理：
 * - 组件卸载自动 abort，杜绝连接/内存泄漏
 * - 心跳保活计数，断流可观测
 * - 收到 complete 前断流可指数退避重试
 */
export function useSSEStream<T extends { type: string }>(options: UseSSEStreamOptions<T>) {
  const { start, onEvent, onError, onDone, retries = 0, retryDelay = 1500 } = options

  const loading = ref(false)
  const heartbeatCount = ref(0)
  const { signal, abort, aborted } = useAbortController()

  let completed = false

  /** 调用方把事件先过一遍这个包装，才能判断"是否收到过 complete" */
  const onStreamEvent = (event: T) => {
    if (event.type === 'complete') completed = true
    onEvent(event)
  }

  const run = async () => {
    loading.value = true
    completed = false

    let attempt = 0
    while (true) {
      try {
        await start(signal, () => {
          heartbeatCount.value += 1
        })
        break
      } catch (error: any) {
        // 主动取消（组件卸载 / 用户中断）不重试
        if (aborted.value || signal.aborted) break
        if (completed) break
        if (attempt >= retries) {
          console.error('SSE 流失败:', error)
          onError?.(error instanceof Error ? error : new Error(String(error)))
          break
        }
        attempt += 1
        console.warn(`SSE 断流，${retryDelay * attempt}ms 后第 ${attempt} 次重试`)
        await new Promise((resolve) => setTimeout(resolve, retryDelay * attempt))
      }
    }

    loading.value = false
    onDone?.()
  }

  return { loading, heartbeatCount, abort, run, onStreamEvent }
}
