# 规划评测

`cases.json` 包含 30 个固定合成案例，覆盖正常规划、必去遗漏、开放冲突、当日超时、超预算、检索超时/非法候选/不可满足要求。候选、路线与模型 fixture 回复均为测试数据，不是从真实服务录制的结果。

## 离线回归

在 backend 目录运行：

```powershell
python -m evals.run_eval --mode fixture --output evals/results/fixture.json
python -m pytest -q
```

三组比较：

| variant | 路径 |
| --- | --- |
| direct | 固定完整行程回复；live 时直接要求模型输出 DayDetail |
| workflow | 当前 macro_planner_node + rule_assemble_day_timeline，冻结聚类/酒店/餐饮/路线输入 |
| validated | 同样编排后运行规则检查；有冲突时调用真实提案与两轮修复逻辑 |

fixture 给模型预设回复，仅用于验证规则、修复回路及失败降级。结果中的通过率不能当作真实模型准确率，更不能据此宣称准确率提升。三组时间只覆盖冻结输入后的规划片段；不含景点发现、真实检索和完整端到端耗时。修复后的候选建议可参与评分，但评测不会伪称用户已确认。

## 真实模型对比（会调用已配置的 LLM）

```powershell
python -m evals.run_eval --mode live --limit 3 --output evals/results/live-small.json
python -m evals.run_eval --mode live --repeat 3 --output evals/results/live.json
```

live 仍冻结外部工具数据，用真实模型生成和修复；不要与实际网络服务稳定性混为一谈。先小样本验证供应商兼容性，再重复至少三次观察波动。建议固定模型与参数，保留执行时的 commit、运行环境与模型配置（不含密钥）。报告包含数据集与规划器源码 SHA256。

真实工具可用性另用原有 smoke 测试（需要服务配置，可能产生请求费用）：

```powershell
python -m pytest -m smoke -o addopts='' -q
```

## 指标口径

- `constraint_pass`：不存在已知硬约束违规；未知价格、未知营业时间等仍可有警告。
- `poi_verifiable_rate`：景点具有 POI ID 与范围合法的经纬度的比例；不是实际 POI 真实性判定。
- `first_editable_ms`：编排/装配第一次产出可编辑详情的时间，修复等待另计在 `elapsed_ms`；单次样本包括 Python/DB 等本地开销。
- `llm_calls`、token 与成本：fixture 为 null；live 依赖模型 callback 和供应商用量信息。统一费率来自进程环境变量 `LLM_INPUT_CNY_PER_MILLION`、`LLM_OUTPUT_CNY_PER_MILLION`；费用不含地图/酒店等供应商收费。
- `repair_rounds`、`injected_fault`、`degraded`、`failure`：观察受限修复、故障注入与未处理系统异常。约束无法满足属于安全失败，不应被当作系统崩溃。

执行使用独立临时 SQLite，不改正式草稿和偏好。`results/fixture.json` 是本次可复现机制验证报告；毫秒耗时随机器变化，不是线上 SLA。当前案例主要覆盖单日约束，多日保留与并发安全由服务测试覆盖，后续可扩充真实城市与复杂跨城案例。
