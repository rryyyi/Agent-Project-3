# MTR Polyglot Agent

An evidence-grounded Agent portfolio for a Hong Kong metro scenario: multilingual station normalization, bounded conversation context, graph routing, document retrieval and reusable tools.

[中文详细文档](README.md) · [Architecture](docs/architecture.md) · [Evaluation](docs/evaluation.md) · [CI](https://github.com/rryyyi/Agent-Project-3/actions)

## Scope and provenance

This is an independently rebuilt public portfolio inspired by the author's described Agent engineering experience. It is not a release of an employer's proprietary system and is not affiliated with MTR. All packaged transit/FAQ data is synthetic and authored for this demonstration. Historical resume metrics are not reproduced or validated by this repository.

The default runtime needs no API key, GPU, Redis or model download. Optional adapters connect BGE-M3 dense embeddings, a cross-encoder reranker, an OpenAI-compatible synthesis endpoint and Redis. Default intent parsing is a transparent rule/alias baseline, not a learned multilingual classifier.

## Quickstart

```bash
git clone https://github.com/rryyyi/Agent-Project-3.git
cd Agent-Project-3
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,mcp,redis]"
mtr-agent demo
mtr-agent chat "How to get from Central to Hung Hom?"
mtr-agent evaluate --output artifacts/evaluation.json
python -m pytest -q
mtr-agent serve
```

Python 3.11+ required; 3.12 recommended. Run `mtr-agent --help` for CLI commands. The HTTP service defaults to `127.0.0.1:8000`; OpenAPI docs are at `/docs`. Set `MTR_API_KEY` to require bearer authentication for every endpoint except `/health`.

## What is implemented

- Longest-match station aliases across traditional/simplified Chinese, English and abbreviations; explicit direction and contextual destination rewriting.
- Line-state Dijkstra with fastest/fewest-transfer objectives, segments and `NEXT_ON_LINE` evidence triples.
- Source-preserving chunks, small-corpus BM25, optional dense retrieval, RRF, optional reranking and extractive character budgets.
- A single validated tool registry shared by HTTP, Function Calling JSON schemas and an official MCP SDK stdio server.
- Bounded TTL/LRU session slots and tool cache, optional Redis fallback, session turn locking and structured traces.
- Vector PDF text/geometry extraction with file hashes and **unreviewed** connection candidates. No automatic OCR or arbitrary complex-map guarantees.
- Authored regression evaluation, failure cases, reproducible in-process timing, CI, container recipe and contribution templates.

```bash
mtr-agent mcp
mtr-agent parse-pdf authorized-map.pdf --output artifacts/candidates.json
mtr-agent benchmark --iterations 500 --concurrency 8 --output artifacts/benchmark.json
```

Function Calling integration provides schemas and execution; the default orchestrator does not run an autonomous LLM tool loop. Optional LLM synthesis only reformulates nonempty FAQ evidence and falls back to source extracts on failure.

## Evaluation limits

The 36-case synthetic regression set is visible during development, not a held-out enterprise benchmark. Reports include exact denominators. Retrieval Hit@3 measures target-document presence; route exact match compares explicitly labeled fields. Timing is warm-cache, in-process and offline, excluding HTTP and model inference. See [reports](docs/reports) and [methodology](docs/evaluation.md).

The sample graph contains 15 stations, 3 lines and synthetic travel weights. It does not provide live service, verified fares, last-train information or production multi-tenant guarantees. PDF candidates must be reviewed before editing the versioned network file. Read the [deployment guide](docs/deployment.md) before exposing the API.

## License

Original code and synthetic examples: [MIT](LICENSE). Third-party models and packages retain their own licenses.
