# 部署、运行与故障排查

## 本地服务

```bash
python -m pip install -e ".[dev,mcp,redis]"
mtr-agent serve --host 127.0.0.1 --port 8000
```

CLI 通过 `factory.build_agent()` 显式读取环境变量；若直接使用 `create_app()`，默认创建离线 Agent。如需自定义 Python 部署：

```python
from mtr_agent.api import create_app
from mtr_agent.factory import build_agent

app = create_app(build_agent())
```

Uvicorn 不启用 access log，应用日志不写完整请求体。`/health` 只证明进程工作，`/ready` 表示 Agent 已初始化并返回知识版本，不验证所有外部服务持续可用。

## Docker Compose

```bash
cp .env.example .env
# 编辑 .env，设置自己的 MTR_API_KEY
docker compose up --build
```

容器基于 Python 3.12 slim，非 root 用户，根文件系统只读、临时目录 tmpfs、移除 capabilities、不允许提权。API 默认只绑定宿主机回环地址。README 所列模型包不包含在基础 Docker 镜像内，镜像安装 redis/mcp extra。

可选 Redis：在 `.env` 设置 `REDIS_URL=redis://redis:6379/0`，然后：

```bash
docker compose --profile redis up --build
```

Redis 无宿主机端口映射、无持久化，最多 64 MiB 数据；它是可丢失的缓存。生产网络应增加 Redis 身份验证、TLS、私网和独立访问控制。不要把该示例直接当公网 Redis 部署模板。

容器健康检查请求 `/health`，无需把 API key 放入镜像或健康检查命令。停止：`docker compose down`。

## 认证与会话归属

设置 `MTR_API_KEY` 后，除 `/health` 外均要求 bearer token，包括 `/docs`、`/ready`、`/metrics` 与工具接口。浏览器直接打开受保护的 `/docs` 不会自动带 header，可用支持自定义 header 的客户端，或在受信本地开发环境不配置 key。

```bash
curl http://127.0.0.1:8000/ready -H "Authorization: Bearer YOUR_KEY"
```

当前是单租户 demo：同一 bearer key 的客户端共享一个信任域，知道 session ID 就可以继续或删除该会话。**不提供用户级权限隔离**。多租户部署必须把认证主体绑定到会话、限制工具数据范围，并在返回引用前做权限过滤。不可只用客户端传来的 session ID 作为身份。

## 资源与并发

- message 1—2,000 字符；session ID 最多 64 字符且限制字符集。
- HTTP 检查 Content-Length，最多 16 KiB；部署网关必须额外按实际读取字节限制请求体，覆盖 chunked 和错误声明的长度。
- 单进程最多 32 个正在处理的 HTTP 请求，超出返回 503 和 Retry-After。
- 并发准入不是速率限制；网关仍需按用户/IP 的限流、超时和连接上限。
- 会话与轻量指标在内存中；进程重启即清空。多 worker 不共享会话，不应在当前设计下直接增加多进程并期待上下文一致。
- Redis 仅共享工具缓存，不共享会话、分片锁或指标。
- 线上需要共享会话存储、基于版本的并发写控制、分布式观测和缓存击穿保护后再水平扩展。

## 数据与模型发布

数据启动时读取、内容哈希参与缓存键；修改后重启服务。模型/索引/切片/Prompt 的版本应固定在发布配置并更新缓存 profile。环境变量不等同于密钥管理系统，部署时使用平台 Secret 注入。日志与 issue 不包含真实 key。

公开镜像前应在干净环境重新构建、扫描依赖与镜像，固定经过验证的版本/镜像摘要。当前 pyproject 使用有上界的版本范围便于安装；尚未提供跨平台锁文件，所以每次发布应记录 `pip freeze` 与模型 revision。

## 排障表

| 现象 | 检查方法 | 处理 |
|---|---|---|
| `mtr-agent` 找不到 | `python -m pip show mtr-polyglot-agent` | 激活正确虚拟环境，重新 editable install |
| Windows 中文输出失败 | 使用 CLI 自动 UTF-8；检查终端编码 | PowerShell/Windows Terminal 配合 UTF-8 |
| PowerShell 无法激活 | 本机执行策略限制 | 可直接运行 `.venv\Scripts\python.exe -m mtr_agent.cli demo` |
| 未知站点/要求澄清 | 查 network.json 站名与别名 | 使用样例网络站点；扩充数据后重新评测 |
| 检索无证据 | 查看 FAQ 与查询关键词 | 扩展知识/评测，而不是强制模型猜测 |
| LLM 退回原文 | trace 含 llm_unavailable | 检查 BASE_URL、MODEL、key、网络、供应商接口 |
| 模型下载失败 | 只有配置模型变量才触发 | 准备模型缓存/本地路径，核对依赖与网络 |
| Redis 失败但服务仍可用 | `/metrics` 的 redis_errors | 检查地址、profile、网络；默认允许本地回退 |
| Docker 无法连接 engine | `docker info` | 启动 Docker Desktop/Linux engine 后再构建 |
| CI 与本机不同 | 对比 Python 和安装包版本 | 使用 CI 矩阵版本、重建干净环境 |
| PDF 没有候选 | 检查 labels、segments、needs_ocr | 扫描件需 OCR；曲线/偏移需人工审阅 |

## 当前验证边界

本地真实验证记录见 `docs/reports/verification.md`。容器是否构建成功以 GitHub Actions container job 和实际本机运行结果为准，配置存在并不等于已经运行通过。生产 SLA、P99、高并发容量和模型质量均未由这份演示部署保证。
