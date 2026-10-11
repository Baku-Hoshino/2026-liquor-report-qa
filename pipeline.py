"""Official PDFs -> page text / complete table rows -> BGE + SQLite BM25."""
from __future__ import annotations
import hashlib,json,re,sqlite3,sys,time,urllib.request
from pathlib import Path
import numpy as np
import pdfplumber
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent
DATA,REPORTS=ROOT/'data',ROOT/'reports'
SOURCES=json.loads((ROOT/'sources.json').read_text())
EMBED_DIR=ROOT/'models/bge-small-zh-v1.5'
def tight(s):return re.sub(r'\s+','',str(s or '')).replace('\u200b','')
def terms(s):
 out=[]
 for w in re.findall(r'[\u3400-\u9fff]+|[a-zA-Z]+|\d+(?:\.\d+)?',s.lower()):
  out.append(w)
  if re.search(r'[\u3400-\u9fff]',w):out += [w[i:i+2] for i in range(len(w)-1)]
 return list(dict.fromkeys(out))
def download():
 REPORTS.mkdir(exist_ok=True)
 for s in SOURCES:
  p=REPORTS/(s['code']+'.pdf')
  if not p.exists():
   req=urllib.request.Request(s['url'],headers={'User-Agent':'Mozilla/5.0'})
   b=urllib.request.urlopen(req,timeout=120).read()
   if not b.startswith(b'%PDF'):raise ValueError('not a PDF: '+s['company'])
   p.write_bytes(b)
  print(s['company'],p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
def is_header(row):
 joined=' '.join(row)
 return any(w in joined for w in ['本报告期','上年同期','本期发生额','上期发生额','2026年半年度','2025年半年度','期末余额','期初余额','营业收入比']) and not any(re.search(r'\d[\d,]*\.\d{2}',c) for c in row)
def monetary(row):
 return any(re.search(r'-?\d[\d,]*\.\d{2}',str(c or '')) for c in row)
def normalized_groups(raw):
 """Retain headers, merged header hierarchy, blank cells, and wrapped labels.
 Numeric answer values are never inserted or inferred by this parser.
 """
 rows=[[tight(c) for c in r] for r in raw];groups=[];headers=None;pending=[];label_prefix='';skip=0;grid_mode=False
 first_data=next((i for i,r in enumerate(rows) if monetary(r)),0)
 if 1<first_data<=6 and (is_header(rows[0]) or any(x in ''.join(rows[0]) for x in ['项目','关联方','科目'])):
  width=len(rows[0]);headers=['']*width;parents=['']*width
  for hr in rows[:first_data]:
   last='';origin=0
   for j,v in enumerate(hr):
    if v:last=v;origin=j
    elif raw[rows.index(hr)][j] is not None:last=''
    candidate=v or (last if parents[j]==parents[origin] else '')
    if candidate and candidate not in headers[j].split(' / '):headers[j]+=(' / ' if headers[j] else '')+candidate
   parents=headers.copy()
  headers=[h or '原表第'+str(i+1)+'列（表头未解析）' for i,h in enumerate(headers)]
  skip=first_data;grid_mode=True
 for raw_row in rows[skip:]:
  row=[c for c in raw_row if c]
  if not row:continue
  if is_header(row):
   if pending:groups.append((headers,pending));pending=[]
   headers=row;grid_mode=False
   if re.match(r'^(本报告期|本期发生额|上年同期|202[56]年)',row[0]):headers=['指标']+row
   continue
  if headers is None:
   if not monetary(row) and len(row)>1:
    headers=row;continue
   headers=['原表第'+str(i+1)+'列（表头未解析）' for i in range(len(raw_row))];grid_mode=True
  if len(row)==1 and len(headers)>1 and not monetary(row):
   if row[0].startswith(('归属于','经营活动产生','其中：','非流动资产','非流动性资产')):
    label_prefix+=row[0]
   elif pending:pending[-1][0]+=row[0]
   else:label_prefix+=row[0]
   continue
  if label_prefix:
   raw_row=raw_row.copy();raw_row[0]=label_prefix+raw_row[0];label_prefix='';row=[c for c in raw_row if c]
  if grid_mode and len(raw_row)==len(headers):row=raw_row
  elif len(raw_row)==len(headers):row=raw_row
  elif len(row)!=len(headers):
   hdr=['原表第'+str(i+1)+'列（表头未解析）' for i in range(len(raw_row))];groups.append((hdr,[raw_row]));continue
  pending.append(row)
 if pending:groups.append((headers,pending))
 return groups
def extract():
 DATA.mkdir(exist_ok=True);chunks=[];pages=[];manifest=[]
 for src in SOURCES:
  path=REPORTS/(src['code']+'.pdf');reader=PdfReader(path)
  if '2026年半年度报告' not in tight(reader.pages[0].extract_text()):raise ValueError('wrong period '+src['company'])
  section='封面/目录';subheading='';count0=len(chunks);previous_table=None
  with pdfplumber.open(path) as pdf:
   for pi,p in enumerate(pdf.pages,1):
    txt=p.extract_text(layout=False) or '';lines=[x.strip() for x in txt.splitlines() if x.strip()]
    for line in lines:
     h=tight(line)
     if pi>3 and re.match(r'^第[一二三四五六七八九十]+节',h) and len(h)<40:section=h
    base={**src,'period':'2026年半年度','page':pi,'section':section};pages.append({**base,'text':txt})
    buf=[];length=0
    for line in lines:
     if length+len(line)>650 and buf:
      chunks.append({**base,'kind':'text','text':'\n'.join(buf)});buf=buf[-1:];length=sum(map(len,buf))
     buf.append(line);length+=len(line)
    if buf:chunks.append({**base,'kind':'text','text':'\n'.join(buf)})
    for ti,table in enumerate(p.find_tables(),1):
     raw=table.extract();above=p.crop((0,max(0,table.bbox[1]-100),p.width,table.bbox[1])).extract_text() or ''
     unit_matches=re.findall(r'单位[：:]\s*([^\n]{1,30})',above);unit=unit_matches[-1] if unit_matches else '见指标名称及原页'
     heading=next((x for x in reversed(above.splitlines()) if re.match(r'^[（(]?\d+[.、）)]|^[一二三四五六七八九十]+[、.]',tight(x))),subheading)
     if heading:subheading=heading
     groups=normalized_groups(raw)
     continued=None
     # A continuation is allowed only across adjacent pages at matching grid width,
     # with the prior table reaching the page bottom and current table at page top.
     if previous_table and previous_table['page']==pi-1 and previous_table['near_bottom'] and table.bbox[1]<130 and raw and len(raw[0])==previous_table['width'] and groups and all('未解析' in h for h in groups[0][0]):
      if len(previous_table['headers'])==len(raw[0]):
       groups=[(previous_table['headers'] if all('未解析' in h for h in hdr) else hdr,rs) for hdr,rs in groups]
       continued=previous_table['header_page'];unit=previous_table['unit'];subheading=previous_table['heading']
     valid=next((h for h,rs in reversed(groups) if not any('未解析' in x for x in h)),None)
     if valid:previous_table={'page':pi,'near_bottom':table.bbox[3]>p.height-180,'width':len(raw[0]),'headers':valid,'unit':unit,'heading':subheading,'header_page':continued or pi}
     else:previous_table=None
     for headers,rows in groups:
      for ri,row in enumerate(rows,1):
       if not any(row):continue
       row_unit='元（人民币）' if any('（元）' in x or '(元)' in x for x in row) else unit
       body='\n'.join(f'{h}：{v or "空白"}' for h,v in zip(headers,row))
       chunks.append({**base,'kind':'table','table_id':f'{src["code"]}-p{pi}-t{ti}','table_heading':subheading,'headers':headers,'cells':row,'unit':row_unit,'header_resolved':not any('未解析' in h for h in headers),'row_index':ri,'header_source_page':continued or pi,'bbox':list(table.bbox),'text':f'表格：{subheading}\n单位：{row_unit}\n'+body})
    # Store the raw grids once per page rather than duplicating them per row.
    pages[-1]['tables']=[t.extract() for t in p.find_tables()]
  rc=chunks[count0:]
  for i,c in enumerate(rc):c['id']=f'{src["code"]}-p{c["page"]}-{c["kind"][0]}{i:05d}'
  manifest.append({**src,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pages':len(reader.pages),'chunks':len(rc)})
  print(src['company'],len(reader.pages),'pages',len(rc),'chunks',flush=True)
 (DATA/'chunks.json').write_text(json.dumps(chunks,ensure_ascii=False));(DATA/'pages.json').write_text(json.dumps(pages,ensure_ascii=False));(ROOT/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));print('EXTRACT TOTAL',len(chunks),flush=True)
class Embedder:
 def __init__(self):
  import torch
  from transformers import AutoTokenizer,AutoModel
  self.torch=torch;self.device='mps' if torch.backends.mps.is_available() else 'cpu'
  self.tokenizer=AutoTokenizer.from_pretrained(str(EMBED_DIR),trust_remote_code=False)
  self.model=AutoModel.from_pretrained(str(EMBED_DIR),trust_remote_code=False).to(self.device).eval()
 def encode(self,texts,query=False,batch=32):
  parts=[]
  for i in range(0,len(texts),batch):
   inp=[('为这个句子生成表示以用于检索相关文章：'+x) if query else x for x in texts[i:i+batch]]
   enc=self.tokenizer(inp,padding=True,truncation=True,max_length=512,return_tensors='pt').to(self.device)
   with self.torch.inference_mode():
    v=self.model(**enc).last_hidden_state[:,0];v=self.torch.nn.functional.normalize(v,p=2,dim=1)
   parts.append(v.cpu().numpy())
  return np.concatenate(parts)
def build():
 started=time.monotonic();chunks=json.loads((DATA/'chunks.json').read_text());emb=Embedder();parts=[]
 for i in range(0,len(chunks),256):
  parts.append(emb.encode([c['company']+' '+c['section']+' '+c['text'] for c in chunks[i:i+256]]));print('EMBED',min(i+256,len(chunks)),'/',len(chunks),flush=True)
 vectors=np.concatenate(parts);np.save(DATA/'vectors.npy',vectors)
 db=sqlite3.connect(DATA/'search.sqlite');db.execute('DROP TABLE IF EXISTS fts');db.execute('CREATE VIRTUAL TABLE fts USING fts5(tokens, chunk_id UNINDEXED, company UNINDEXED)')
 db.executemany('INSERT INTO fts VALUES (?,?,?)',((' '.join(terms(c['text'])),i,c['company']) for i,c in enumerate(chunks)));db.commit();db.close()
 info={'embedding_model':'BAAI/bge-small-zh-v1.5','dimensions':vectors.shape[1],'chunks':len(chunks),'index_seconds':round(time.monotonic()-started,2),'device':emb.device,'bm25':'SQLite FTS5','text_blocks':sum(c['kind']=='text' for c in chunks),'table_rows':sum(c['kind']=='table' for c in chunks),'headers_unresolved':sum(c['kind']=='table' and not c['header_resolved'] for c in chunks)}
 (ROOT/'build_info.json').write_text(json.dumps(info,ensure_ascii=False,indent=2));print(info,flush=True)
if __name__=='__main__':
 if len(sys.argv)!=2 or sys.argv[1] not in ['download','extract','build']:raise SystemExit('python pipeline.py download|extract|build')
 globals()[sys.argv[1]]()
