"""Call the same QA engine as the UI; save actual outputs before grading.
gold.json is read only by this evaluator, never by retrieval or generation.
"""
import json,hashlib,datetime
from pathlib import Path
from engine import QA
from pipeline import ROOT
CASES=[
 ('贵州茅台2026年上半年营业收入是多少','revenue','贵州茅台'),
 ('五粮液主要销售模式有哪些','sales_modes','五粮液'),
 ('泸州老窖2026年上半年归母净利润是多少','profit','泸州老窖'),
 ('山西汾酒经营活动产生的现金流量净额是多少','cashflow','山西汾酒'),
 ('洋河股份2026年上半年营业收入同比变化是多少','revenue_yoy','洋河股份'),
 ('古井贡酒2026年上半年研发投入是多少','research_scope','古井贡酒'),
 ('今世缘2026年上半年营业收入是多少','revenue','今世缘'),
 ('舍得酒业2026年上半年归母净利润是多少','profit','舍得酒业'),
 ('十家公司的营业收入分别是多少','revenue',None),
 ('十家公司的归母净利润分别是多少','profit',None)]
def audit(r,kind,company,gold):
 ev=r['evidence'];out=r['answer'];byid={c['id']:c for c in ev}
 if kind=='sales_modes':
  required=gold[kind][company];recall=all(any(w in c['text'] for c in ev) for w in required)
  correct=all(w in out['answer'] for w in required) and bool(out['citations']) and not r['validation_errors']
  reason='核对五粮液PDF第9页：经销、直销及团购/专卖店/线上均须出现。'
 elif kind=='research_scope':
  recall=any('研发费用' in c['text'] for c in ev)
  text=out['answer'];correct=any(w in text for w in ['无法','不能','未提供','不足','没有']) and '研发投入' in text and '研发费用' in text and not any(x.get('metric')=='研发投入' and x.get('value')==gold[kind]['fee'] for x in out['rows']) and bool(out['citations']) and not r['validation_errors']
  reason='费用证据不是投入总额。此题单独评价口径提示与拒答，不计入数值题正确率。'
 else:
  truth={company:gold[kind][company]} if company else gold[kind]
  recall=all(any(c['company']==n and v in c['text'] for c in ev) for n,v in truth.items())
  correct=len(out['rows'])==len(truth) and not r['validation_errors']
  for n,v in truth.items():
   row=next((x for x in out['rows'] if x.get('company')==n),{})
   c=byid.get(row.get('evidence_id'),{})
   correct=correct and row.get('value')==v and row.get('period')=='2026年半年度' and row.get('unit') in (['%'] if kind=='revenue_yoy' else ['元','人民币元','元（人民币）']) and c.get('company')==n and v in c.get('text','')
  reason='比对的是程序实际返回的rows，不是从gold复制的展示答案；须同时满足公司、期间、单位、数值和对应引用。'
 return {'recall_sufficient':bool(recall),'answer_correct':bool(correct),'verdict':'正确（口径拒答）' if kind=='research_scope' and correct else ('正确' if correct else '错误/不完整'),'reason':reason,'manual_review':'需核对evaluation.md所列原页与实际输出'}
def write_report(rs):
 lines=['# 作业3：10题实际答案与逐题核对','',
 '本文件由实际运行记录生成。最终回答与网页使用同一个QA.ask；gold只在评价阶段读取。保留完整模型原始输出、校验前结果、页面实际结果、两路召回ID及原文证据，见evaluation_records.json。','',
 '召回评价：本轮已读块是否覆盖预先核对的证据义务。回答评价：实际回答的数值、单位、期间、公司和引用是否同时正确。研发投入题另计口径拒答，不能拿首条证据出现目标值当作答案正确率。','',
 '|题号|问题|召回证据足够|最终回答判定|耗时（秒）|','|---|---|---|---|---|']
 for i,r in enumerate(rs,1):lines.append(f'|{i}|{r["question"]}|{"是" if r["audit"]["recall_sufficient"] else "否"}|{r["audit"]["verdict"]}|{r["seconds"]}|')
 for i,r in enumerate(rs,1):
  lines += ['',f'## 第{i}题：{r["question"]}','', '**页面实际回答**','',r['answer']['answer'],'']
  if r['answer']['rows']:
   lines += ['|公司|指标|期间|实际输出值|单位|引用块与原页|','|---|---|---|---|---|---|']
   for row in r['answer']['rows']:
    c=next((c for c in r['evidence'] if c['id']==row['evidence_id']),None)
    cite=f'[{row["evidence_id"]}]({c["url"]}#page={c["page"]})' if c else '无有效出处'
    lines.append('|'+ '|'.join(str(row.get(k,'')) for k in ['company','metric','period','value','unit'])+'|'+cite+'|')
  lines += ['',f'最终回答判定：**{r["audit"]["verdict"]}**。{r["audit"]["reason"]}',f'证据检查：{r["validation_errors"] or "通过"}。','', '**本轮召回并读过的全部块**','']
  for c in r['evidence']:
   lines += [f'### `{c["id"]}` {c["company"]}，{c["section"]}，PDF第{c["page"]}页',f'[原页]({c["url"]}#page={c["page"]})；向量余弦{c["vector_score"]}；融合分{c["rrf_score"]}。','', '```text',c['text'],'```','']
  lines += ['**错在哪 / 口径与限制**','', '\n'.join(r['answer']['limitations']) or '本题未发现数值、单位、期间或引用错误。','']
 (ROOT/'evaluation.md').write_text('\n'.join(lines))
def main():
 qa=QA();rs=[]
 for q,kind,company in CASES:
  r=qa.ask(q);r['case_type']=kind;r['run_time']=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat();rs.append(r)
  (ROOT/'evaluation_ungraded.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2))
  print(len(rs),q,'seconds',r['seconds'],'answer',r['answer'],'checks',r['validation_errors'],flush=True)
 # Actual answer records have already been persisted; only now load the truth.
 gold=json.loads((ROOT/'gold.json').read_text())
 for r,(_,kind,company) in zip(rs,CASES):r['audit']=audit(r,kind,company,gold)
 (ROOT/'evaluation_records.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2));write_report(rs)
 summary={'questions':10,'panorama_questions':2,'recall_sufficient':sum(r['audit']['recall_sufficient'] for r in rs),'answer_correct':sum(r['audit']['answer_correct'] for r in rs),'answerable_questions_correct':sum(r['audit']['answer_correct'] for r in rs if r['case_type']!='research_scope'),'answerable_questions':9,'scope_refusal_correct':rs[5]['audit']['answer_correct'],'ungraded_record_sha256':hashlib.sha256((ROOT/'evaluation_ungraded.json').read_bytes()).hexdigest()}
 (ROOT/'evaluation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(summary,flush=True)
if __name__=='__main__':main()
