# Contributing

感谢提出可复现的问题和改进。维护语言以中文为主，英文 issue/PR 也欢迎。

## 开发环境

```bash
python -m venv .venv
# 激活虚拟环境后：
python -m pip install -e ".[dev,mcp,redis]"
ruff check src tests
ruff format --check src tests
pytest
mtr-agent evaluate
python -m build
```

默认验证不下载模型。涉及模型质量的改动请另附模型版本、数据范围、硬件和实际报告。使用特性分支，保持提交范围清楚，建议 feat/fix/docs/test/chore 前缀。

## 提交要求

- 行为改动附能说明问题的测试，修 bug 时保留复现案例。
- 改图数据时校验站点/线路引用、正反向路径和换乘。
- 新增资料说明来源、许可、有效期和是否合成；禁止提交企业机密、私人聊天、简历或个人联系方式。
- API/工具契约变更同步 README、MCP、测试和 CHANGELOG。
- 指标写明分母、配置与限制，避免把 regression score 写成线上业务效果。
- 安全漏洞不要在公开 issue 贴 key 或可利用的私人数据，按 SECURITY.md 处理。

PR 应解释问题、用户可见变化、验证命令及已知限制。仓库使用 MIT；贡献者应确保有权按此许可提交原创内容。
