#!/usr/bin/env python3
"""生成短期活动版设计 docx（完整版：17章标题 + 全部正文）。"""
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

import content_part1 as c1
import content_part2 as c2
import content_part3 as c3

OUT = "/Users/ycc/workspace/E3DP/校园3D打印平台设计-短期活动版.docx"

# 章节标题顺序（与 content_part*.py 对齐）
CHAPTERS = [
    ("1. 项目概述", c1.CH1),
    ("2. 系统总体架构", c1.CH2),
    ("3. 核心业务对象", c1.CH3),
    ("4. 打印业务流程", c1.CH4),
    ("5. Val1 模型审核", c1.CH5),
    ("6. 切片", c1.CH6),
    ("7. Val2 切片审核", c2.CH7),
    ("8. 打印执行", c2.CH8),
    ("9. Val3 实物验收", c2.CH9),
    ("10. Val3异常处理", c2.CH10),
    ("11. 费用核算", c2.CH11),
    ("12. 订单状态管理（两级状态机）", c3.CH12),
    ("13. 系统安全与可追溯性", c3.CH13),
    ("14. AI辅助建模", c3.CH14),
    ("15. 站娘问答与三层帮助", c3.CH15),
    ("16. 配套运营与线下保障", c3.CH16),
    ("17. 总结", c3.CH17),
]

PARTS = [
    ("第一部分 · 平台概述与架构", [0, 1]),
    ("第二部分 · 核心业务对象", [2]),
    ("第三部分 · 打印主链（含成本核算终点）", [3, 4, 5, 6, 7, 8, 9, 10]),
    ("第四部分 · 系统级", [11, 12]),
    ("第五部分 · 独立功能模块", [13, 14, 15]),
    ("第六部分 · 收尾", [16]),
]


def _set_eastasia(run, name="微软雅黑"):
    run.font.name = "Calibri"
    rpr = run._element.get_or_add_rPr()
    rf = rpr.get_or_add_rFonts()
    rf.set(qn("w:eastAsia"), name)


def _set_heading_eastasia(para):
    for r in para.runs:
        _set_eastasia(r)


def main():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(2.54)
    sec.left_margin = sec.right_margin = Cm(3.18)

    # Title
    title = doc.add_heading("", level=0)
    tr = title.add_run("校园3D打印平台 设计说明（短期活动版）")
    tr.font.size = Pt(28)
    tr.font.bold = True
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_heading_eastasia(title)

    idx = 0
    for part_title, chapter_indexes in PARTS:
        doc.add_heading(part_title, level=1)
        _set_heading_eastasia(doc.paragraphs[-1])
        for ci in chapter_indexes:
            ch_title, content = CHAPTERS[ci]
            doc.add_heading(ch_title, level=2)
            _set_heading_eastasia(doc.paragraphs[-1])
            for kind, text in content:
                if kind == "h3":
                    h = doc.add_heading(text, level=3)
                    _set_heading_eastasia(h)
                elif kind == "para":
                    doc.add_paragraph(text)
                elif kind == "bullet":
                    doc.add_paragraph(text, style="List Bullet")

    doc.save(OUT)
    print("saved (full):", OUT)
    # stats
    d2 = Document(OUT)
    print("paragraphs:", len(d2.paragraphs))
    h1 = h2 = h3 = 0
    for p in d2.paragraphs:
        s = p.style.name
        if s == "Heading 1":
            h1 += 1
        elif s == "Heading 2":
            h2 += 1
        elif s == "Heading 3":
            h3 += 1
    print("Heading1:%d Heading2:%d Heading3:%d" % (h1, h2, h3))


if __name__ == "__main__":
    main()
