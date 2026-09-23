# 2026 白酒半年报问答库

方向 A 作业：10 家 A 股白酒公司 2026 年半年报全文，采用 **512 维字符 n-gram TF-IDF 向量余弦相似度 + SQLite FTS5 BM25** 混合检索。回答是可核对的原文摘录，附公司、章节、PDF 页码和原报告链接；不使用未配置的生成模型编造数字。

## 使用

```bash
python3 -m pip install -r requirements.txt
python3 pipeline.py download
python3 pipeline.py build
python3 app.py
```

打开 `http://127.0.0.1:8765`。报告 PDF 下载到 `reports/`，抽取结果和索引写入 `data/`，两者均不提交仓库。`sources.json` 保留 10 份官方披露文件的原始 URL。也可以运行 `python3 evaluate.py` 复现 10 题的召回记录。无需 API key。

## 方法及边界

- PDF 逐页提取文字；用 `pdfplumber` 恢复检测到的表格，每行连同列标题索引。每个块保留公司、章节、PDF 页码、来源 URL。页码指 PDF 阅读器页码，不一定等于页脚印刷页码。
- 向量使用固定维度的字符 2/3-gram TF-IDF 哈希和余弦相似度，不使用外部语义模型。BM25 使用 SQLite FTS5，对中文单字和双字词建索引。两路各召回候选后用倒数排名融合。
- 页面只输出检索到的证据摘录。跨公司问题会尽量分别给出各公司的原文片段；比较、口径换算和数值推理仍需人工复核。表格合并单元格、扫描页和跨页表可能抽取失败。
- `evaluation.md` 是本次实际运行结果，逐题记录召回块、答案与错误。`conclusion.pdf` 是一页总结，`screenshot.png` 是实际页面截图。

## 数据来源

巨潮资讯 2026 年半年报全文，下载于 2026-09-23。详情见 `sources.json`；10 份 PDF 均不纳入版本控制。
