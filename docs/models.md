# 模型接入与配置

## 模式对照

| 能力 | 默认离线 | 显式模型模式 |
|---|---|---|
| 意图/槽位 | 规则与别名 | 仍使用规则；尚未增加 LLM 槽位提取 |
| 文本召回 | BM25 | BM25 + SentenceTransformers BGE-M3 dense |
| 融合 | RRF | RRF |
| 重排 | 融合排名 | 可选 CrossEncoder |
| 路线求解 | Dijkstra + 图证据 | 相同，不让模型计算路径 |
| FAQ 回答 | 原文抽取与引用 | 可选兼容 OpenAI 接口整理证据，失败回退 |

`mode=offline` 表示回答没有经过 LLM synthesis，不意味着没有 dense/reranker。具体检索模式应查看配置与 Tools.version；报告记录检索配置，避免混淆。

## 环境变量

| 变量 | 默认 | 行为 |
|---|---|---|
| `MTR_DENSE_MODEL` | 空 | 非空才加载 SentenceTransformer |
| `MTR_RERANK_MODEL` | 空 | 非空才加载 CrossEncoder |
| `MTR_MODEL_DEVICE` | cpu | 模型推理设备，例如 cuda |
| `LLM_BASE_URL` | 空 | 应含 provider 的版本路径，如 `https://host/v1` |
| `LLM_MODEL` | 空 | 与 BASE_URL 同时配置才启用 |
| `LLM_API_KEY` | 空 | 仅发送到用户配置的模型服务，不写日志 |
| `REDIS_URL` | 空 | 可选 L2；需要 redis extra |
| `MTR_API_KEY` | 空 | HTTP 单租户 bearer key |

`.env` 不由 CLI 自动读取。Bash 使用 `export NAME=value`；PowerShell 使用 `$env:NAME="value"`。避免把真实 key 写进 shell 示例、issue 或提交。

## BGE-M3 与 Reranker

```bash
python -m pip install -e ".[models]"
export MTR_DENSE_MODEL=BAAI/bge-m3
export MTR_RERANK_MODEL=BAAI/bge-reranker-v2-m3
mtr-agent evaluate --output artifacts/model-evaluation.json
```

适配器 `trust_remote_code=False`，只在配置后实例化。模型文件需要从可访问的模型仓库下载；无网络环境应先准备模型缓存或使用本地目录。模型权重可能占用较多内存；本项目没有给出实测 GPU 显存/吞吐承诺。推荐使用 Python 3.12 及与你的 CUDA 匹配的 PyTorch，避免最新 Python 尚无相应 wheels。

当前只取 BGE-M3 dense 向量，并执行小语料的暴力余弦扫描。不要将其描述为已经实现 BGE-M3 原生 sparse 或 ColBERT 检索。threshold=0.5、RRF k=60、候选各 10 条都是可调整超参，不是业务最优值。

## 可选 LLM

`OpenAICompatibleLLM` 构造 `/chat/completions` 请求，temperature=0，包含问题与证据 JSON。系统提示要求证据视作不可信数据、不得执行其中指令、禁止编造票价/班次、注明来源。连接超时 5 秒，读取超时 20 秒，禁止重定向。

仅 FAQ 有非空证据才调用；路线、无证据和澄清不调用。响应异常时 Agent 保留原始 evidence/citations 并输出抽取式原文。当前没有事实一致性自动检查器；模型仍可能曲解证据或忽略提示，因此关键业务建议保留默认抽取式输出。

连接外部服务意味着问题与选中证据会传给该服务；用户应选择获准的服务及资料。默认示例只有合成资料。模型适配层不提供任意 URL 的用户输入接口，endpoint 只能由部署方配置。

## 扩展建议

- 用标注的中英粤 code-switching 数据评估槽位准确率，增加结构化 LLM/分类器解析与 unknown 校验。
- 使用固定模型 revision 和索引快照作为缓存 profile 的一部分，升级时显式失效。
- 用 ANN 索引替换内存 dense 扫描，保持文档 ID/页码证据契约。
- 增加真实模型集成测试和幻觉评测；仓库单元测试的轻量 adapter fixture 只证明接线与契约，不证明模型质量。
- 处理长上下文应使用目标模型 tokenizer 计算精确预算；当前按字符压缩。

第三方模型与依赖许可分别以提供方说明为准，MIT 仅覆盖本仓库原创代码和合成数据。
