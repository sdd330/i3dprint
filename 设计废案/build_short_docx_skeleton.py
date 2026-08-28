#!/usr/bin/env python3
"""Generate the short-term activity version design doc skeleton (17 chapters)."""
import copy
import os
import sys

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

OUT = "/Users/ycc/workspace/E3DP/校园3D打印平台设计-短期活动版.docx"

# (level, text)  ; level: 0=Title, 1=Heading1(部分), 2=Heading2(章节), 3=Heading3(小节)
STRUCTURE = [
    (0, "校园3D打印平台 设计说明（短期活动版）"),
    (1, "第一部分 · 平台概述与架构"),
    (2, "1. 项目概述"),
    (2, "2. 系统总体架构"),
    (1, "第二部分 · 核心业务对象"),
    (2, "3. 核心业务对象"),
    (1, "第三部分 · 打印主链（含成本核算终点）"),
    (2, "4. 打印业务流程"),
    (2, "5. Val1 模型审核"),
    (2, "6. 切片"),
    (2, "7. Val2 切片审核"),
    (2, "8. 打印执行"),
    (2, "9. Val3 实物验收"),
    (2, "10. Val3异常处理"),
    (2, "11. 费用核算"),
    (1, "第四部分 · 系统级"),
    (2, "12. 订单状态管理（两级状态机）"),
    (2, "13. 系统安全与可追溯性"),
    (1, "第五部分 · 独立功能模块"),
    (2, "14. AI辅助建模"),
    (2, "15. 站娘问答与三层帮助"),
    (2, "16. 配套运营与线下保障"),
    (1, "第六部分 · 收尾"),
    (2, "17. 总结"),
]


def set_base_font(doc):
    """Use Calibri for Latin, and a CJK-friendly fallback for Chinese."""
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    rpr = normal.element.get_or_add_rPr()
    rFonts = rpr.get_or_add_rFonts()
    rFonts.set(qn("w:eastAsia"), "微软雅黑")


def main():
    doc = Document()
    # A4
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(2.54)
    sec.left_margin = sec.right_margin = Cm(3.18)
    set_base_font(doc)

    for level, text in STRUCTURE:
        if level == 0:
            h = doc.add_heading("", level=0)
            run = h.add_run(text)
            run.font.size = Pt(28)
            run.font.bold = True
            h.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif level == 1:
            h = doc.add_heading(text, level=1)
        elif level == 2:
            h = doc.add_heading(text, level=2)
        else:
            h = doc.add_heading(text, level=3)
        # force east-asian font on heading runs
        for r in h.runs:
            r.font.name = "Calibri"
            rpr = r._element.get_or_add_rPr()
            rf = rpr.get_or_add_rFonts()
            rf.set(qn("w:eastAsia"), "微软雅黑")

    doc.save(OUT)
    print("saved:", OUT)
    print("top-level heading count:", sum(1 for l, _ in STRUCTURE if l >= 2))


if __name__ == "__main__":
    main()
