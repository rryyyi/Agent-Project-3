# Local verification — 2026-11-25

## Environment and result

Windows, Python 3.14.4, isolated `.venv`; default offline Agent, no model weights or external LLM, no running Redis. This is a local snapshot, not a production benchmark.

| Check | Actual outcome |
|---|---|
| Editable install `python -m pip install -e ".[dev,mcp,redis]"` | Success in isolated virtual environment |
| `python -m pip check` | No broken requirements |
| `pytest --cov=mtr_agent --cov-report=term-missing -q` | 44 passed; aggregate coverage 89% (786 statements, 83 missed) |
| Ruff lint and format | Passed |
| `python -m build` | Built sdist and wheel successfully |
| Wheel resources | Contains network.json, faq.json and eval.jsonl |
| CLI demo | Six cases executed; structured JSON saved locally as scratch |
| Evaluation | 36 samples; intent 36/36, status 36/36, target-document Hit@3 13/13, explicit route fields 13/13 |
| Real HTTP subprocess | Loopback health and route POST passed |
| Real official MCP stdio subprocess | initialize, list_tools and route_plan JSON-RPC passed |
| PDF ingestion | Runtime-generated vector PDF coordinates, source hash and unreviewed connection candidate verified |
| Redis outage | Fault-injected client verified local fallback; no live Redis integration measurement |
| Real BGE-M3 / Reranker inference | Not run; adapter fixtures validate integration contracts only |
| External LLM | HTTP request contract and timeout fallback tested with fixture; no paid/external inference |
| Local Docker build/run | Not run: Docker Desktop Linux engine unavailable |

The virtual environment resolved FastAPI 0.165.0, Starlette 1.10.0, Pydantic 2.14.4, MCP 1.30.0, PyMuPDF 1.28.2, pytest 9.2.0 and Ruff 0.17.6. Starlette TestClient emitted one deprecation warning recommending httpx2; tests passed, and the real HTTP subprocess smoke test also passed. No dependency warning was suppressed.

## Measured performance

See [benchmark.json](benchmark.json): 500 calls, 8 threads, warm-cache in-process offline workload; mean 1.262 ms, P50 0.254 ms, P95 0.469 ms, P99 47.070 ms, approximately 3490.77 calls/s on this run. Scheduling and contention produce tail outliers. These values exclude HTTP, model inference and network and must not be used as a production capacity claim.

## Review and fixes

Final review was performed by the author in a separate self-review pass because no independent subagent tool was available. This is weaker than independent review.

Behavioral findings were reproduced in tests before correction:

- English infinitive `to` in a payment question incorrectly triggered route intent.
- English contextual destination follow-up was not recognized.
- Explicit unknown origin in a contextual question could incorrectly reuse old origin.
- Extra unsupported waypoints could be silently ignored.
- Tool station parameters could resolve a known substring inside ambiguous free text.

Regression tests now cover all these cases. Full suite remained green after fixes. No known critical finding remains in the intended single-tenant, synthetic offline demo scope. General semantic coverage, OCR/VLM, production auth/session stores, large-scale ANN and model-quality validation remain explicitly documented extensions.

## Publication validation

GitHub CI runs Python 3.11/3.12/3.13 and a Linux container build. Its actual status is available from the repository Actions tab; this local report does not claim remote jobs have passed before observing them. Local Docker engine unavailability does not verify the container recipe.
