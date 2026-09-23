"""Render the one-page assignment conclusion as a PDF."""
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
OUT = HERE / "conclusion.pdf"
pdfmetrics.registerFont(TTFont("Heiti", "/System/Library/Fonts/STHeiti Medium.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("Songti", "/System/Library/Fonts/Supplemental/Songti.ttc", subfontIndex=0))
W, H = A4
INK = HexColor("#173735")
TEAL = HexColor("#186C65")
MUTED = HexColor("#657A76")
PAPER = HexColor("#F8F7F1")
LINE = HexColor("#D9E2DD")
ORANGE = HexColor("#D78C39")


def text(c, x, y, value, size=10, font="Heiti", color=INK):
    c.setFont(font, size); c.setFillColor(color); c.drawString(x, y, value)


def wrap(c, x, y, value, width, size=10, leading=17, color=INK):
    line = ""
    for ch in value:
        if pdfmetrics.stringWidth(line + ch, "Heiti", size) > width and line:
            text(c, x, y, line, size, color=color); y -= leading; line = ""
        line += ch
    if line:
        text(c, x, y, line, size, color=color); y -= leading
    return y


def section(c, y, no, title, body, height):
    c.setFillColor(HexColor("#FFFFFF")); c.roundRect(42, y-height, W-84, height, 9, fill=1, stroke=0)
    c.setFillColor(TEAL); c.roundRect(56, y-38, 30, 25, 5, fill=1, stroke=0)
    text(c, 63, y-30, no, 10, color=HexColor("#FFFFFF"))
    text(c, 99, y-31, title, 13)
    wrap(c, 56, y-59, body, W-112, 9.5, 16)
    return y-height-12


def main():
    c = canvas.Canvas(str(OUT), pagesize=A4)
    c.setTitle("2026 白酒半年报问答库｜一页结论")
    c.setAuthor("课程作业 3 · 方向 A")
    c.setFillColor(PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(INK); c.rect(0, H-179, W, 179, fill=1, stroke=0)
    text(c, 42, H-44, "MF70050.01  人工智能与数据分析  /  作业 3", 9, color=HexColor("#B9D8CF"))
    text(c, 42, H-91, "同一批财报，什么问题适合建库？", 22, "Songti", HexColor("#FFFFFF"))
    text(c, 42, H-121, "方向 A · 10 家 A 股白酒公司 2026 年半年报全文", 11, color=HexColor("#D9ECE6"))
    c.setFillColor(ORANGE); c.circle(W-55, H-92, 7, fill=1, stroke=0)

    y = H-210
    text(c, 42, y, "10", 33, color=TEAL); text(c, 101, y+5, "份官方半年报", 10, color=MUTED)
    text(c, 227, y, "18,224", 33, color=TEAL); text(c, 350, y+5, "个带出处的块", 10, color=MUTED)
    c.setStrokeColor(LINE); c.line(42, y-16, W-42, y-16)
    y -= 42
    y = section(c, y, "01", "怎么做", "下载 10 份半年报全文，逐页抽取文字、恢复表格；每块保留公司、章节和 PDF 页码。向量与 BM25 混合检索，答案直链原报告。", 105)
    y = section(c, y, "02", "真实测试", "固定 10 题：8 道单公司题、2 道跨公司全景题。9/10 题的首条证据包含人工核对的目标值或关键文字；两道全景题各覆盖 10 家公司、对应本期指标行。逐题召回块 ID、页码、判定与错误记录见仓库 evaluation.md。", 105)
    y = section(c, y, "03", "哪里有效", "营业收入、归母净利润、经营现金流等可在报表中明确定位的事实题表现最好。跨公司同一指标的资料收集也适合建库：数据随报告更新，引用页码可追溯；比较时仍须统一口径与单位。", 88)
    y = section(c, y, "04", "哪里翻车", "“古井贡酒研发投入是多少”只召回第 38 页的“研发费用”34,920,057.51 元。研发费用不能直接等于研发投入，系统仍把它排在首位。下一步应加指标别名与口径校验，并在证据不足时明确拒答。", 89)

    c.setFillColor(HexColor("#E8F0EB")); c.roundRect(42, 61, W-84, 57, 9, fill=1, stroke=0)
    text(c, 56, 98, "结论", 10, color=TEAL)
    wrap(c, 56, 80, "同一批财报，更新频繁且必须核对出处的事实问答适合建库；微调更适合学习稳定的董秘答复口径，不能替代财务数字的检索与引用。", W-112, 9.8, 15)
    text(c, 42, 38, "数据：巨潮资讯披露的 2026 年半年度报告全文 · 2026-09-23", 8, color=MUTED)
    text(c, W-87, 38, "01 / 01", 8, color=MUTED)
    c.save()
    print(OUT)


if __name__ == "__main__":
    main()
