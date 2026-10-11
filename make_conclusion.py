"""Create a one-page conclusion from the saved, actually measured evaluation."""
import json,re
from pathlib import Path
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
ROOT=Path(__file__).resolve().parent
font='/System/Library/Fonts/STHeiti Medium.ttc'
if Path(font).exists():pdfmetrics.registerFont(TTFont('Chinese',font,subfontIndex=0))
else:pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'));font=None
FONT='Chinese' if font else 'STSong-Light'
W,H=A4;INK=HexColor('#203733');GREEN=HexColor('#176753');MUTED=HexColor('#65766c')
def text(c,x,y,s,size=10,color=INK):
 c.setFont(FONT,size);c.setFillColor(color);c.drawString(x,y,s)
def wrap(c,x,y,s,width,size=10,leading=16):
 line=''
 for ch in re.findall(r'[A-Za-z0-9][A-Za-z0-9.,%/+-]*|.',s):
  if pdfmetrics.stringWidth(line+ch,FONT,size)>width and line:text(c,x,y,line,size);y-=leading;line=''
  line+=ch
 if line:text(c,x,y,line,size);y-=leading
 return y
def main():
 summary=json.loads((ROOT/'evaluation_summary.json').read_text())
 c=canvas.Canvas(str(ROOT/'conclusion.pdf'),pagesize=A4);c.setTitle('作业3｜白酒半年报问答库修订结论')
 c.setFillColor(HexColor('#f6f7f2'));c.rect(0,0,W,H,fill=1,stroke=0)
 text(c,42,H-42,'人工智能与数据分析 · 作业3 · 方向A · 2026-10-11',9,MUTED)
 text(c,42,H-80,'找到证据以后，答案仍要逐项核对',21)
 y=H-111;y=wrap(c,42,y,'10家白酒上市公司 · 2026年半年度报告全文 · BGE语义嵌入 + BM25 + 本地Qwen2.5-7B',W-84,10,16)
 c.setFillColor(HexColor('#e4eee6'));c.roundRect(42,y-78,W-84,65,7,fill=1,stroke=0)
 text(c,56,y-35,f'证据义务满足：{summary["recall_sufficient"]}/10',12,GREEN)
 text(c,300,y-35,f'完整正确答案：{summary["answer_correct"]}/10',12,GREEN)
 text(c,56,y-59,'另有1题部分正确、1题失败；9道有明确答案的题中8道正确。',9,MUTED)
 y-=102
 sections=[
 ('本次补了什么','恢复表格本期、上期及同比列，保留公司、章节、单位与PDF页码；全景题按10家公司分别取证。使用真实嵌入模型与回答模型，提交代码仓库、页面截图和10题实际输出。原始生成、引用、全部已读块和逐题判定均可在仓库复核。'),
 ('哪类题答得好','单公司明确财务指标题和销售模式题核对通过；营收全景题输出10家公司本期收入，金额、单位和各自出处均一致。对这10题，所需材料全部读到，但这只是证据义务核对，不能称为模型答案准确率。'),
 ('哪类题翻车，为什么','研发投入题未把研发费用当投入，但未充分解释口径，判部分正确。古井合并研发费用34,920,057.51元（PDF第38、118页）与母公司14,176,456.49元（第40页）不能直接证明投入总额。归母净利润全景题已读到10家公司证据，仍把茅台44,516,880,421.86元抄成4,451,688,042.18元，并生成无效引用；错误被拦截，此题仍计失败。'),
 ('改进后的结果与限制','首轮实际答案仅4/10完整正确，保留失败记录后，修正提示词和取证范围，再测为8/10完整正确。题集已参与调试，不能当作未知题泛化成绩。14,953块中仍有2,902个复杂表格行的表头未可靠恢复，已标记并排除出最终表格证据；本次使用的财务摘要行逐项核对原页。'),
 ('结论','数字更新频繁、需要出处的财报事实问答适合建库；微调更适合稳定格式。可靠回答还要区分费用与投入、本期与上期、合并与母公司，并校验实际答案。下一步优先改善长答案的复制与引用一致性，而不是把检索命中冒充回答正确。')]
 for title,body in sections:
  text(c,42,y,title,12,GREEN);y-=22;y=wrap(c,42,y,body,W-84,10.5,17);y-=15
 assert y>60, y
 text(c,42,47,'复核入口：github.com/Baku-Hoshino/2026-liquor-report-qa · evaluation.md',8.5,MUTED)
 c.linkURL('https://github.com/Baku-Hoshino/2026-liquor-report-qa', (42,44,W-42,60),relative=0)
 text(c,W-85,27,'1 / 1',8,MUTED);c.save();print('one-page conclusion generated, remaining y=',y)
if __name__=='__main__':main()
