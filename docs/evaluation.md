# 评测、指标与实验方法

## 可复现命令

```bash
python -m pip install -e ".[dev,mcp,redis]"
mtr-agent evaluate --output artifacts/evaluation.json
mtr-agent benchmark --iterations 500 --concurrency 8 --output artifacts/benchmark.json
python -m pytest --cov=mtr_agent --cov-report=term-missing
ruff check src tests
ruff format --check src tests
```

已提交报告位于 `docs/reports/`。JSON 记录创建时间、Python、数据版本、模式、样本数、指标分母、失败项和局限。benchmark 始终构造离线 Agent，不读取模型环境变量；evaluate/chat/demo 通过 factory 读取已配置的模型。

## 数据集与指标

`src/mtr_agent/data/eval.jsonl` 是 36 条人工编写的合成回归用例。它用于验证已实现需求，开发者能看到所有问句，因此不是盲测集，也不代表真实香港乘客语言分布。当前两类意图 route/knowledge，澄清和拒答用独立 status 表示。

- `intent_accuracy`：全体 36 条意图分类是否匹配。
- `status_accuracy`：全体 36 条 answered/clarification/unsupported 是否匹配。
- `retrieval_hit_at_3`：有 document_id 标注的用例中，目标文档是否进入前三条 evidence。一个 relevant 文档标注不足以评估标准的全相关集合 Recall@K；不把该指标命名为检索准确率。
- `route_exact_match`：有 route 标注的用例中，所有给定字段与输出是否相同。数组使用顺序相等，数值精确比较；未标注字段不评分。
- `failures`：失败用例 ID、失败指标和实际结果；CLI 有失败时返回非零退出码，便于 CI 阻断回归。

多轮用例通过相同 session 字段串联；不同组隔离。评测器只输出合成用例 ID 和结果，不依赖企业数据。

## 自定义用例

```json
{"id":"new-001","message":"由HKU去紅磡點搭","intent":"route","status":"answered","route":{"origin":"HKU","destination":"HUH","transfers":1}}
{"id":"new-002","message":"Octopus payment","intent":"knowledge","status":"answered","document_id":"faq-octopus"}
```

```bash
mtr-agent evaluate --dataset path/to/held-out.jsonl --output artifacts/held-out.json
```

每行至少包含唯一 id、非空 message、intent、status。可选 route/document_id/session。空数据集、坏 JSON、缺字段、重复 ID 明确失败。真实用户样本应先获得授权并脱敏，禁止把企业测试集直接提交公开仓库。

## 性能方法

`benchmark` 执行 4 种固定请求，先预热工具缓存，每次用新会话，避免上下文改变语义；用线程池模拟并发，记录单次完整 Agent 调用耗时与整轮墙钟耗时。P50/P95/P99 按排序后的下取整索引取得，报告记录迭代数、并发度、平台与 workload。

它测的是**小样例、暖缓存、同进程、无模型**的开销。它不包含 HTTP 调度、TLS、网络、Redis 远程往返、GPU、外部 LLM 或大索引，因此不能根据该结果声称“生产高并发低延迟”。

线上实验应另测：冷启动/冷缓存/暖缓存；命中与未命中；不同语言与句长；数据规模；HTTP 分位延迟；超时与错误率；模型推理；Redis 故障；同会话争用与多会话负载。记录 CPU/GPU、依赖、数据/模型版本、目标 QPS 和持续时间，不只报告最好的一轮。

## 业务效果实验建议

1. 独立准备开发集与盲测集，按用户/会话/时间切分，避免相似问句泄漏。
2. 三语混合场景按语言比例、俗称、拼写错误、否定、反向问法分层；报告类别样本数、混淆矩阵和槽位准确率。
3. 检索标注完整相关文档集合，评 Recall@K、MRR、nDCG；按语言和知识类型细分。
4. 路线评测标注可接受路径集合和时间有效性，允许等价最优路径，单独统计换乘正确率、站序正确率与引用覆盖。
5. 回答评证据支持率、事实一致性、拒答准确率；自动判分结合人工复核，不能仅依赖同一个模型自评。
6. 固定数据与模型版本，做 BM25 → +改写 → +dense → +rerank → +缓存/压缩的消融，质量和延迟分别统计。
7. 为每个比例报告分母与置信区间，小样本的 100% 不代表线上必然正确。

## 与简历指标的关系

原简历描述的意图 89%、检索 78%→91%、复杂换乘问题 92% 未提供原始样本、业务日志或统计口径。本仓库不验证这些历史指标，也不以 36 条演示集冒充其复现。公开报告只证明该版本在当前样例上的行为与配置。
