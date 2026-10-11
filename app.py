"""Local UI and JSON API expose exactly the same actual RAG answer."""
import json,re,traceback
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
from engine import QA
from pipeline import ROOT
ENGINE=None
class Handler(BaseHTTPRequestHandler):
 def reply(self,body,mime='application/json; charset=utf-8',status=200):
  if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False).encode()
  self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/':self.reply((ROOT/'index.html').read_bytes(),'text/html; charset=utf-8')
  elif path=='/api/info':self.reply(json.loads((ROOT/'build_info.json').read_text()))
  elif path=='/api/evaluations':
   p=ROOT/'evaluation_records.json';self.reply(json.loads(p.read_text()) if p.exists() else [])
  elif path.startswith('/pdf/'):
   code=path[5:-4] if path.endswith('.pdf') else ''
   if re.fullmatch(r'\d{6}',code) and (ROOT/'reports'/(code+'.pdf')).exists():self.reply((ROOT/'reports'/(code+'.pdf')).read_bytes(),'application/pdf')
   else:self.send_error(404)
  elif path=='/health':self.reply({'ok':ENGINE is not None})
  else:self.send_error(404)
 def do_POST(self):
  if self.path!='/api/ask':self.send_error(404);return
  try:
   length=int(self.headers.get('Content-Length','0'))
   if length>4096:raise ValueError('问题过长')
   q=json.loads(self.rfile.read(length)).get('question','').strip()
   if not q or len(q)>500:raise ValueError('请输入1到500字的问题')
   self.reply(ENGINE.ask(q))
  except Exception as ex:traceback.print_exc();self.reply({'error':str(ex)},status=500)
if __name__=='__main__':
 print('Loading local embedding and answer models...',flush=True);ENGINE=QA()
 print('Ready: http://127.0.0.1:8767',flush=True);ThreadingHTTPServer(('127.0.0.1',8767),Handler).serve_forever()
