# 数据来源、PDF 审阅与图模式

## 合成数据清单

所有包内数据均为本作品集人工编写的教学样例，没有抓取企业文档、用户聊天、港铁官方 PDF 或实时数据。

| 文件 | 内容 | 范围与限制 |
|---|---|---|
| `src/mtr_agent/data/network.json` | 15 站、3 条线、15 条无向样例连接 | 只有局部网络，不覆盖机场、票价或运营状态 |
| `src/mtr_agent/data/faq.json` | 5 篇中英关键词 FAQ | 支付、行李、无障碍、失物、运营信息边界 |
| `src/mtr_agent/data/eval.jsonl` | 36 条人工回归样例 | 用来检查代码行为，不是独立企业测试集 |
| `tests/test_pdf.py` | 运行时生成矢量 PDF | 原创文字和直线；文件不入库 |

站名用于构造可理解的场景；连接、分钟和换乘成本均不作为真实乘车依据。网络 source 是 `SYNTHETIC-NETWORK-v1`，FAQ 是 `SYNTHETIC-FAQ-v1`。FAQ page 是合成资料的逻辑页编号，不伪称来自真实 PDF。

## Network JSON

```json
{
  "version": "your-reviewed-network-v2",
  "source": "authorized-file-sha256:... page:1 reviewer:...",
  "transfer_minutes": 4,
  "lines": {"TWL": "Tsuen Wan Line"},
  "stations": [
    {"id": "CEN", "name": "中環", "en": "Central", "aliases": ["中环"]},
    {"id": "ADM", "name": "金鐘", "en": "Admiralty", "aliases": ["金钟"]}
  ],
  "edges": [{"a": "CEN", "b": "ADM", "line": "TWL", "minutes": 2}]
}
```

- `station.id` 唯一；所有边必须引用存在的站点和线路。
- `minutes > 0` 且有限；`transfer_minutes >= 0` 且有限。
- 一条 edge 建为两个方向的邻接，不需手动录入反向重复边。
- 同站之间不同线路可以有各自连接；换乘由相邻边线路变化推导。
- 不同站点之间的步行换乘、出站换乘、无障碍路径尚未建模。
- 当前来源为全网级 source。若接入多份真实文档，应扩展到边级 source/page/有效期并更新校验和引用逻辑。

修改文件后启动新 Agent 以重建 Knowledge/Router/Retriever。内容哈希改变使工具缓存自动使用新键，但已运行的进程不会热重载数据。

## PDF 抽取和审核

```bash
mtr-agent parse-pdf map.pdf --output artifacts/map-candidates.json
```

解析器限制：文件不超过 30 MiB、100 页、未加密；参数限额可由 Python 接口调整。提取器仅在本地 CLI 中处理文件，不向 HTTP 暴露上传执行接口。

输出示意：

```json
{
  "filename": "map.pdf",
  "sha256": "content-hash",
  "requires_review": true,
  "pages": [{
    "page": 1,
    "labels": [{"text": "Central", "bbox": [50, 78, 88, 93], "station_ids": ["CEN"]}],
    "segments": [{"start": [65, 110], "end": [270, 110], "color": [1, 0, 0], "width": 3, "path_id": 0}],
    "candidate_edges": [{"a": "CEN", "b": "ADM", "segment_index": 0, "page": 1, "status": "unreviewed", "method": "nearest-label-endpoints"}],
    "needs_ocr": false
  }]
}
```

坐标单位为 PDF point，采用 PyMuPDF 页坐标。端点到文字中心默认 60 point 内才候选连接；一条线两端必须能匹配不同站点。文字行合并字体 span，防止同站名因字体切换被拆断。颜色作为证据保留，**不直接把 RGB 推断为某条线路**。

审核者应逐页：

1. 检查文字与站点别名是否一致；新站先补全标准 ID 和别名。
2. 对照原图核对连线，排除仅交叉、不换乘、跨线、支线和断开的情况。
3. 将曲线和多段折线合并为实际相邻站关系；当前工具不自动完成这一步。
4. 指定线路、方向语义及来源页码；记录审核者和文件哈希。
5. 单独获取或明确合成时间权重，不能从 PDF 距离推算运营分钟。
6. 将审核通过的边编辑为 Network JSON；未审核候选不直接导入 Router。
7. 加入正向、反向、支线、换乘、同站和断路测试，再发布新版本。

扫描页的 `needs_ocr` 表示没有提取文字，不代表已经执行 OCR。真正复杂路线图应增加 OCR/版面模型/视觉模型、几何折线合并、置信度校准和人工审核队列，并用标注边集统计 precision/recall；不能从当前两站矢量夹具推断复杂图纸的解析准确率。

## 新增 FAQ

每条记录至少有 `id/text/source`，建议含 `title/keywords/page`。`keywords` 是检索提示而非效果标签；新增数据后使用未参与调试的问句评测。不要把只适用于某时段的公告当永久知识，真实场景应补有效期、更新时间、权限和失效机制。
