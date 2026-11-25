# 技术阅读与面试索引

这份索引帮助读者从真实代码理解工程决策，也帮助维护者准确说明实现范围。所有表述应与代码和运行证据一致。

## 先运行，再追踪

```bash
mtr-agent demo
mtr-agent chat "How to get from Central to Hung Hom?"
mtr-agent evaluate
python -m pytest -q
```

从 `cli.py` → `factory.py` → `Agent.chat` → `understand` → `Tools.call` → Router/Retriever，最后查看响应中的 trace/citations。HTTP 和 MCP 都调用同一工具层。

## 核心讨论点

| 问题 | 代码位置 | 应能解释的技术要点 |
|---|---|---|
| 混合语言到底怎么处理？ | understanding.py / knowledge.py | 词表规范化、最长别名、英文边界、规则语法覆盖与局限 |
| 为什么旺角东不会匹配成旺角？ | Knowledge.mentions | 匹配候选按长度选择，排除重叠，再按位置排序 |
| 多轮为什么不会串用户？ | Agent / TTLCache | 会话 ID 分区、原子 turn 的分片锁、有界 TTL；单租户权限边界 |
| 为什么只用站点 Dijkstra 不够？ | Router.route | 当前线路决定换乘成本，需要 `(站点, 线路)` 状态 |
| Graph RAG 和普通 RAG 的分工？ | Router / Retriever | 结构化约束精确求解与文本证据检索，避免向量模型推测站序 |
| PDF 图线就能自动得到路线吗？ | pdf.py | 只能得到局部几何候选，需审核复杂交叉/曲线/标注，不推测时间表 |
| BM25 和 dense 分数怎么融合？ | retrieval.rrf | 不同尺度用排序融合，候选数、RRF k 和相似度阈值需独立调参 |
| BGE-M3 哪些能力实际接入？ | adapters.BGEEncoder | SentenceTransformers dense；没有 sparse/ColBERT 分支 |
| Function Calling/MCP 做到了哪一步？ | tools.py / mcp_server.py | Schema + 验证执行器、官方 MCP 传输；默认无 LLM 自主工具循环 |
| 缓存怎么避免旧数据？ | Tools.version / ToolCache.key | 知识哈希、检索配置、工具参数；模型 revision 等需发布时固定 |
| LLM 超时怎么办？ | Agent._turn / adapters.py | 限时 HTTP、原文回退、保留证据、日志脱敏；无分布式重试风暴 |
| 怎么证明效果？ | evaluation.py / reports | 有分母的回归指标、失败归因；与盲测业务指标区分 |

## 可讲清楚的取舍

- 小语料无需立即使用大型向量/图数据库；通过接口保留替换能力。
- 先确定性路线求解，再让模型整理文本，降低推理事实漂移。
- 有界状态和明确降级优先于无上限自治循环。
- 工具共享实现不意味着传输协议相同：HTTP、Function Calling schema 和 MCP 各自承担不同职责。
- 轻量本地缓存不等于分布式一致性；单进程演示不等于多租户生产部署。
- 质量指标、性能指标、历史业务指标是不同证据，必须交代测试条件。

## 演示建议

用三语混合问句展示别名与 query，再展示同会话追问和另一会话澄清；然后对照路线三元组解释换乘；用无证据和未知站点展示边界；最后打开 tests 与报告说明如何防回归。模型模式和复杂 PDF 的未来扩展应明确标为扩展，不把未测能力当完成项。

## 下一阶段应验证什么

1. 独立真实中英粤问句上的槽位泛化，而非继续堆演示集规则。
2. 复杂路线图标注边集上的解析 precision/recall。
3. 固定模型 revision 的 BGE/Rerank 消融及成本。
4. 用户认证绑定会话后的多租户权限隔离。
5. HTTP 冷/暖缓存及外部模型条件下的分位延迟与失败率。

阅读者无需依赖形容词判断水平；可执行结果、清晰接口、失败边界与技术取舍就是仓库提供的审查材料。
