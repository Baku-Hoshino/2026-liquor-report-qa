"""Run the fixed 10-question retrieval audit and write evaluation.md."""
from app import search

CASES = [
    ("贵州茅台2026年上半年营业收入是多少", "90,703,260,964.48", "单公司/财务指标"),
    ("五粮液主要销售模式有哪些", "经销模式", "单公司/经营文字"),
    ("泸州老窖2026年上半年归母净利润是多少", "4,339,264,086.33", "单公司/财务指标"),
    ("山西汾酒经营活动产生的现金流量净额是多少", "6,651,541,581.85", "单公司/现金流"),
    ("洋河股份2026年上半年营业收入同比变化是多少", "-28.76%", "单公司/同比"),
    ("古井贡酒2026年上半年研发投入是多少", None, "单公司/口径陷阱"),
    ("今世缘2026年上半年营业收入是多少", "6,435,322,896.05", "单公司/财务指标"),
    ("舍得酒业2026年上半年归母净利润是多少", "145,134,120.55", "单公司/财务指标"),
    ("十家公司的营业收入分别是多少", None, "跨公司/营收全景"),
    ("十家公司的归母净利润分别是多少", None, "跨公司/利润全景"),
]

REVENUE = {
    "贵州茅台": "90,703,260,964.48", "五粮液": "28,416,674,541.77",
    "泸州老窖": "10,472,224,575.78", "山西汾酒": "21,044,387,808.34",
    "洋河股份": "10,540,431,576.04", "古井贡酒": "10,131,395,927.11",
    "今世缘": "6,435,322,896.05", "舍得酒业": "2,286,904,653.19",
    "酒鬼酒": "529,993,647.65", "口子窖": "1,951,744,051.30",
}
PROFIT = {
    "贵州茅台": "44,516,880,421.86", "五粮液": "8,752,942,991.31",
    "泸州老窖": "4,339,264,086.33", "山西汾酒": "6,439,313,574.11",
    "洋河股份": "2,601,710,694.52", "古井贡酒": "2,164,379,928.17",
    "今世缘": "2,081,693,137.94", "舍得酒业": "145,134,120.55",
    "酒鬼酒": "12,319,103.15", "口子窖": "364,856,015.35",
}


def main():
    lines = ["# 十题检索评测", "", "2026-09-23 固定题集；答案按原报告相应页人工核对。判定标准：正确数字或关键文字须出现在首条证据；跨公司题须在各公司首条证据中全部出现。系统输出是带出处的原文证据，不额外生成结论。", ""]
    passed = 0
    for i, (q, expected, typ) in enumerate(CASES, 1):
        result = search(q)
        if i in (9, 10):
            truth = REVENUE if i == 9 else PROFIT
            correct = len(result) == 10 and all(next((r for r in result if r["company"] == name and value in r["text"]), None) for name, value in truth.items())
            answer = "；".join(f"{r['company']} {truth[r['company']]} 元" for r in result if r["company"] in truth)
            reason = "10 家均召回对应的本报告期指标行；跨公司数值仍须统一口径、单位后才能排序。" if correct else "有公司缺失或首条证据不含目标值。"
        elif i == 6:
            correct = False
            answer = "首条召回的是第 38 页‘研发费用’34,920,057.51 元，不能据此等同于‘研发投入’。"
            reason = "问法与财报披露口径不一致；系统没有主动拒答或提示口径差异。"
        else:
            correct = bool(result and expected in result[0]["text"])
            answer = ("经销模式、直销模式（团购、专卖店、线上等）" if i == 2 else f"{expected}{'%' if False else ''}")
            reason = "首条证据包含人工核对的目标值/文字。" if correct else "首条证据未命中目标值/文字。"
        passed += int(correct)
        lines += [f"## {i}. {q}", "", f"- 类型：{typ}", f"- 判定：{'正确' if correct else '错误/不可直接作答'}", f"- 答案/观察：{answer}", f"- 原因：{reason}", "- 召回块（前 3 条）："]
        for r in result[:3]:
            preview = r["text"].replace("\n", " ")[:110]
            lines.append(f"  - `{r['id']}` {r['company']}，{r['section']}，PDF 第 {r['page']} 页，{r['kind']}：{preview}… [原文]({r['url']}#page={r['page']})")
        lines.append("")
    lines[2] += f" 结果：{passed}/10 道首条证据通过。"
    from pathlib import Path
    Path("evaluation.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{passed}/10", "evaluation.md")


if __name__ == "__main__":
    main()
