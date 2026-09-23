"""Download official reports and build a page-cited hybrid retrieval index."""
import collections
import hashlib
import json
import math
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pdfplumber
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
DATA = ROOT / "data"
SOURCES = json.loads((ROOT / "sources.json").read_text())
DIM = 512


def terms(text):
    text = text.lower()
    han = re.findall(r"[\u3400-\u9fff]+", text)
    out = []
    for s in han:
        out.extend(s)
        out.extend(s[i:i + 2] for i in range(len(s) - 1))
        out.extend(s[i:i + 3] for i in range(len(s) - 2))
    out.extend(re.findall(r"[a-z]+|\d+(?:\.\d+)?", text))
    return out


def fts_terms(text):
    return [x for x in terms(text) if len(x) <= 2]


def download():
    REPORTS.mkdir(exist_ok=True)
    for src in SOURCES:
        path = REPORTS / f"{src['code']}.pdf"
        if path.exists() and path.read_bytes()[:4] == b"%PDF":
            print("cached", src["company"], path.stat().st_size)
            continue
        req = urllib.request.Request(src["url"], headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=90).read()
        if not data.startswith(b"%PDF"):
            raise RuntimeError(f"Not a PDF: {src['url']}")
        path.write_bytes(data)
        print("downloaded", src["company"], len(data))


def clean(text):
    text = text.replace("\u200b", "").replace("\u00a0", " ")
    return re.sub(r"[ \t]{2,}", "  ", text).strip()


def section_from(lines, current):
    for line in lines:
        s = re.sub(r"\s+", "", line)
        if len(s) < 33 and re.match(r"^第[一二三四五六七八九十0-9]+节[^.。·]{2,}$", s):
            current = s
    return current


def extract_one(src, start_id):
    path = REPORTS / f"{src['code']}.pdf"
    reader = PdfReader(path)
    chunks = []
    section = "封面/目录"
    with pdfplumber.open(path) as pdf:
        for idx, page in enumerate(reader.pages):
            raw = page.extract_text(extraction_mode="layout") or ""
            lines = [clean(x) for x in raw.splitlines() if clean(x)]
            if idx > 2:
                section = section_from(lines, section)
            # Keep contiguous lines together, retaining apparent row/column spacing.
            buf = []
            size = 0
            for line in lines:
                if size + len(line) > 360 and buf:
                    chunks.append(("text", "\n".join(buf)))
                    buf, size = [], 0
                buf.append(line)
                size += len(line)
            if buf:
                chunks.append(("text", "\n".join(buf)))
            # Explicit table rows restore column associations that PDF text often loses.
            try:
                tables = pdf.pages[idx].extract_tables()
            except Exception:
                tables = []
            for table in tables:
                rows = [[clean(str(c or "").replace("\n", " ")) for c in row] for row in table if row]
                if len(rows) < 2:
                    continue
                header = rows[0]
                for row in rows[1:]:
                    cells = [f"{header[i] or '列'+str(i+1)}: {v}" for i, v in enumerate(row) if v]
                    if cells:
                        chunks.append(("table", " | ".join(cells)[:700]))
            page_chunks = chunks
            chunks = []
            for kind, txt in page_chunks:
                if len(txt) < 16:
                    continue
                yield {"id": start_id, "code": src["code"], "company": src["company"],
                       "period": "2026年半年度", "page": idx + 1, "section": section,
                       "kind": kind, "text": txt, "url": src["url"]}
                start_id += 1


def vector(tokens, idf):
    v = np.zeros(DIM, dtype=np.float32)
    for tok, count in collections.Counter(tokens).items():
        h = int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "little")
        v[h % DIM] += (1 if (h >> 9) & 1 else -1) * (1 + math.log(count)) * idf.get(tok, 1)
    norm = np.linalg.norm(v)
    if norm:
        v /= norm
    return v


def build():
    DATA.mkdir(exist_ok=True)
    chunks = []
    for src in SOURCES:
        before = len(chunks)
        chunks.extend(extract_one(src, before))
        print(src["company"], "chunks", len(chunks) - before, flush=True)
    (DATA / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    token_docs = [terms(c["text"]) for c in chunks]
    df = collections.Counter(t for doc in token_docs for t in set(doc))
    idf = {t: math.log((len(chunks) + 1) / (n + 1)) + 1 for t, n in df.items()}
    (DATA / "idf.json").write_text(json.dumps(idf, ensure_ascii=False), encoding="utf-8")
    matrix = np.stack([vector(doc, idf) for doc in token_docs])
    np.save(DATA / "vectors.npy", matrix)
    db = sqlite3.connect(DATA / "search.sqlite")
    db.execute("DROP TABLE IF EXISTS fts")
    db.execute("CREATE VIRTUAL TABLE fts USING fts5(tokens, chunk_id UNINDEXED)")
    db.executemany("INSERT INTO fts(tokens,chunk_id) VALUES (?,?)",
                   ((" ".join(fts_terms(c["text"])), c["id"]) for c in chunks))
    db.commit(); db.close()
    print("total", len(chunks), "chunks", matrix.shape, flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"download", "build"}:
        raise SystemExit("usage: python pipeline.py download|build")
    (download if sys.argv[1] == "download" else build)()
