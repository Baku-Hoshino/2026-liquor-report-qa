import json,hashlib
from pathlib import Path
from evaluate import write_report
p=Path('.')
rs=json.loads((p/'evaluation_records.json').read_text())
reasons=[
'对照贵州茅台PDF第5页，本报告期营业收入90,703,260,964.48元；实际行的公司、期间、金额、单位和出处均一致。',
'对照五粮液PDF第9页，实际回答包含经销、直销两大类，也包含团购、专卖店、线上三个直销子类，没有只列大类。',
'对照泸州老窖PDF第7页，实际答案4,339,264,086.33元，引用归属于上市公司股东的净利润本期列，未取扣非或上期列。',
'对照山西汾酒PDF第5页，实际答案6,651,541,581.85元，指标为经营活动产生的现金流量净额，期间和出处一致。',
'对照洋河股份PDF第7页，实际答案-28.76%，取本报告期比上年同期增减列，保留负号；未把本期收入金额当同比。',
'拒绝把费用冒充投入，rows为空，属于部分正确；但正文没有明确说明已找到的是“研发费用”，也没有解释合并与母公司口径的区别，因此按严格规则不计为完整正确。古井贡酒PDF第38页合并研发费用为34,920,057.51元，第40页母公司为14,176,456.49元，第118页是费用明细，均不能直接证明研发投入总额。',
'对照今世缘PDF第5页，实际答案6,435,322,896.05元，只输出一行本期营业收入，没有混入营业总收入。',
'对照舍得酒业PDF第5页，实际答案145,134,120.55元，引用本期归母净利润行，未误取443,290,477.79元的上期数。',
'逐家公司对照PDF第5/6/7页的主要会计数据表。实际输出10行，10家公司均齐，金额、单位、期间与各自引用一致。此项检查实际答案全表，不以首条召回命中判对。',
'虽然10家公司所需归母净利润行都已读到，模型仍把茅台44,516,880,421.86元抄成4,451,688,042.18元，并把证据义务文字放进citations，造成引用ID无效。校验后页面仅显示无法可靠作答；这道全景题判失败，不能用召回齐全代替答案正确。'
]
for i,(r,reason) in enumerate(zip(rs,reasons)):
 r['audit']['reason']=reason
 r['audit']['manual_review']='已逐题对照原始PDF；页码使用PDF阅读器页码。'
 if i==5:r['audit']['verdict']='部分正确（拒答但口径解释不足）';r['audit']['partial_correct']=True
 if i==9:r['audit']['verdict']='失败（错误生成已被拦截）'
(p/'evaluation_records.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2))
summary=json.loads((p/'evaluation_summary.json').read_text());summary.update({'partial_correct':1,'failed':1,'manual_review_completed':True,'fixed_question_set':True,'note':'8/10完整正确，1题部分正确，1题失败；在9道有明确答案的题中8道正确。召回10/10按已读证据义务核对，不代表一般检索召回率。'})
(p/'evaluation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
write_report(rs)
# Keep the model output untouched; review augments only the grading metadata.
assert hashlib.sha256((p/'evaluation_ungraded.json').read_bytes()).hexdigest()==summary['ungraded_record_sha256']
print('10 questions manually reviewed; original model output hash unchanged')
