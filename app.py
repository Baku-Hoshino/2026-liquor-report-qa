"""A small dependency-free, cited Q&A web page for the report index."""
import html
import json
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
from pipeline import DATA, SOURCES, fts_terms, terms, vector

CHUNKS = json.loads((DATA / "chunks.json").read_text())
IDF = json.loads((DATA / "idf.json").read_text())
VECTORS = np.load(DATA / "vectors.npy", mmap_mode="r")


def search(question, limit=10):
    question = question.strip()[:200]
    if not question:
        return []
    named = [s["company"] for s in SOURCES if s["company"] in question]
    multi = any(w in question for w in ("十家", "各家", "分别", "比较", "哪家", "所有", "全景")) and not named
    retrieval_q = question
    for name in named:
        retrieval_q = retrieval_q.replace(name, "")
    retrieval_q = re.sub(r"2026|年|上半年|半年度|多少|分别|十家|公司|哪家", "", retrieval_q)
    retrieval_q = retrieval_q.replace("归母净利润", "归属于上市公司股东的净利润")
    v = vector(terms(retrieval_q), IDF)
    scores = VECTORS @ v
    if named:
        allowed = {c["code"] for c in CHUNKS if c["company"] in named}
        scores = np.array([s if c["code"] in allowed else -1 for s, c in zip(scores, CHUNKS)])
    top_vector = np.argpartition(scores, -min(100, len(scores)))[-min(100, len(scores)):]
    top_vector = sorted(top_vector, key=lambda i: scores[i], reverse=True)
    lexical = [x for x in fts_terms(retrieval_q) if len(x) == 2 and x not in {"公司", "报告", "半年", "哪些", "分别", "多少", "2026"}]
    lexical = list(dict.fromkeys(lexical))[:16]
    top_bm25 = []
    if lexical:
        db = sqlite3.connect(DATA / "search.sqlite")
        query = " OR ".join('"' + x + '"' for x in lexical)
        try:
            top_bm25 = [int(r[0]) for r in db.execute(
                "SELECT chunk_id FROM fts WHERE fts MATCH ? ORDER BY bm25(fts) LIMIT 100", (query,))]
        except sqlite3.OperationalError:
            pass
        db.close()
    fused = {}
    for rank, i in enumerate(top_vector):
        fused[i] = fused.get(i, 0) + 1 / (60 + rank + 1)
    for rank, i in enumerate(top_bm25):
        fused[i] = fused.get(i, 0) + 1 / (60 + rank + 1)
    metric = None
    if "营业收入" in question:
        metric = "营业收入"
    elif "净利润" in question:
        metric = "归属于上市公司股东的净利润"
    elif "现金流" in question:
        metric = "经营活动产生的现金流量净额"
    if metric:
        for i, c in enumerate(CHUNKS):
            if c["page"] > 12:
                continue
            first = c["text"].split("|")[0].replace(" ", "")
            wanted = metric.replace(" ", "")
            if wanted in first and re.search(r"\d[\d,]{5,}", c["text"]):
                # The summary table near the beginning of a report is the
                # correct scope for group-level half-year financial metrics.
                fused[i] = fused.get(i, 0) + (0.12 if c["kind"] == "table" else 0.045)
    items = sorted(fused, key=fused.get, reverse=True)
    if named:
        items = [i for i in items if CHUNKS[i]["company"] in named]
    if multi:
        selected = []
        for src in SOURCES:
            match = next((i for i in items if CHUNKS[i]["company"] == src["company"]), None)
            if match is not None:
                selected.append(match)
        items = selected
    else:
        seen_pages = set()
        selected = []
        for i in items:
            c = CHUNKS[i]
            key = (c["code"], c["page"])
            if key in seen_pages:
                continue
            seen_pages.add(key)
            selected.append(i)
            if len(selected) >= limit:
                break
        items = selected
    return [{**CHUNKS[i], "vector_score": round(float(scores[i]), 3),
             "hybrid_score": round(fused.get(i, 0), 5)} for i in items[:limit]]


def page(question, results):
    esc = html.escape
    count = len(CHUNKS)
    nav = '<div class="brand">FIN<span>·</span>10 <small>2026 半年报问答库</small></div><div class="tag">来源：巨潮资讯 · 原文可追溯</div>'
    query = esc(question)
    form = f'''<form action="/" method="get"><input name="q" aria-label="输入财报问题" value="{query}" placeholder="例如：贵州茅台 2026 年上半年营业收入是多少？" required><button>检索问答 →</button></form>'''
    examples = '<div class="examples">试试：<a href="/?q=贵州茅台2026年上半年营业收入是多少">贵州茅台营业收入</a><a href="/?q=十家公司的营业收入分别是多少">10 家营收全景</a><a href="/?q=五粮液的经营活动现金流量净额是多少">五粮液现金流</a></div>'
    cards = ''
    if question:
        cards += f'<div class="answer-head"><div><div class="eyebrow">检索结果</div><h2>{esc(question)}</h2></div><div class="count">{len(results)} 条证据</div></div>'
        cards += '<p class="note">以下为财报原文证据摘录，数值比较与口径换算请对照 PDF 复核。</p>'
        if not results:
            cards += '<div class="empty">没有找到可靠的证据。可尝试公司简称、指标全称或报告章节。</div>'
        for n, r in enumerate(results, 1):
            txt = esc(r['text'][:570])
            if len(r['text']) > 570:
                txt += '…'
            cards += f'''<article class="card"><div class="card-top"><span class="rank">{n:02d}</span><strong>{esc(r['company'])}</strong><span class="kind">{('表格行' if r['kind']=='table' else '正文')}</span></div><div class="section">{esc(r['section'])}</div><blockquote>{txt}</blockquote><a class="source" target="_blank" rel="noopener" href="{esc(r['url'])}#page={r['page']}">查看 2026 年半年报 · PDF 第 {r['page']} 页 ↗</a></article>'''
    else:
        cards = '<div class="welcome"><span>01 / RETRIEVAL</span><h2>对 10 家白酒公司的<br>半年报直接提问。</h2><p>每条回答都指回原报告的公司、章节和 PDF 页码。混合检索同时使用向量和 BM25。</p></div>'
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>2026 白酒半年报问答库</title><style>
    :root{{--ink:#152e33;--teal:#176b65;--paper:#f7f6f1;--line:#d8ded7;--muted:#667975}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:var(--ink)}}header{{height:74px;background:#123c3b;color:white;display:flex;align-items:center;justify-content:space-between;padding:0 max(5vw,28px)}}.brand{{font-size:24px;font-weight:800;letter-spacing:.04em}}.brand span{{color:#f7b75b}}.brand small{{font-size:13px;font-weight:400;margin-left:14px;letter-spacing:0;color:#d6e9e3}}.tag{{font-size:12px;color:#a9d5ca}}main{{max-width:1050px;margin:0 auto;padding:56px 28px 90px}}h1{{font-family:Georgia,"Songti SC",serif;font-size:48px;letter-spacing:.02em;margin:0 0 8px}}.subtitle{{color:var(--muted);margin:0 0 34px}}form{{display:flex;background:white;border:1px solid var(--line);box-shadow:0 13px 30px #133e3b0e;padding:7px;border-radius:12px}}input{{flex:1;border:0;outline:0;font-size:17px;padding:15px 18px;min-width:0}}button{{border:0;background:var(--teal);color:white;font-weight:700;padding:0 25px;border-radius:8px;cursor:pointer;font-size:15px}}button:hover{{background:#0e5651}}.examples{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-top:14px}}.examples a{{color:var(--teal);background:#e6efeb;text-decoration:none;padding:6px 10px;border-radius:20px}}.welcome{{margin-top:82px;background:#e7eee8;padding:50px;border-left:5px solid var(--teal)}}.welcome span,.eyebrow{{font-size:11px;font-weight:800;color:var(--teal);letter-spacing:.18em}}.welcome h2{{font-family:Georgia,"Songti SC",serif;font-size:40px;line-height:1.3;margin:18px 0}}.welcome p{{color:var(--muted);max-width:620px;line-height:1.8}}.answer-head{{display:flex;justify-content:space-between;align-items:end;margin-top:60px;border-bottom:1px solid var(--line);padding-bottom:18px}}.answer-head h2{{font-size:25px;margin:9px 0 0}}.count{{font-size:12px;color:var(--muted)}}.note{{font-size:13px;color:var(--muted);margin:16px 0 24px}}.card{{background:white;border:1px solid var(--line);border-radius:10px;margin:16px 0;padding:22px 27px;box-shadow:0 2px 7px #193b3708}}.card-top{{display:flex;align-items:center;gap:12px}}.rank{{font-family:Georgia,serif;color:#a5b4ae;font-size:18px}}.card-top strong{{font-size:18px}}.kind{{font-size:11px;color:var(--teal);background:#e8f1ed;padding:4px 8px;border-radius:4px}}.section{{font-size:12px;color:var(--muted);margin:10px 0 12px 30px}}blockquote{{white-space:pre-wrap;line-height:1.7;margin:0 0 16px 30px;color:#2d4546;font-size:14px}}.source{{display:inline-block;margin-left:30px;color:var(--teal);font-size:13px;text-decoration:none;font-weight:700}}.source:hover{{text-decoration:underline}}footer{{border-top:1px solid var(--line);padding:24px 5vw;font-size:12px;color:var(--muted)}}@media(max-width:650px){{header{{padding:0 20px}}.tag{{display:none}}main{{padding:35px 18px}}h1{{font-size:35px}}form{{display:block}}input{{width:100%}}button{{padding:14px;width:100%}}.welcome{{padding:30px}}.welcome h2{{font-size:30px}}}}
    </style></head><body><header>{nav}</header><main><h1>让财报回答问题。</h1><p class="subtitle">10 家 A 股白酒企业 · 2026 年半年度报告 · {count:,} 个带出处的文本与表格块</p>{form}{examples}{cards}</main><footer>课程作业 3 · 方向 A ｜ 向量余弦 + BM25 混合检索 ｜ 原始 PDF 不进入代码仓库</footer></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path not in {"/", "/api/search"}:
            self.send_error(404); return
        q = parse_qs(u.query).get("q", [""])[0].strip()
        result = search(q)
        if u.path == "/api/search":
            body = json.dumps({"question": q, "results": result}, ensure_ascii=False).encode()
            mime = "application/json; charset=utf-8"
        else:
            body = page(q, result).encode()
            mime = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)


if __name__ == "__main__":
    print("Open http://127.0.0.1:8765", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
