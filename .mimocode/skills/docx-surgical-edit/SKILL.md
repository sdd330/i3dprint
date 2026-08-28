---
name: docx-surgical-edit
description: Performs precise, surgical, text-level edits on .docx design/spec documents using python-docx — scattered find-and-replace across paragraphs (e.g. unifying an old terminology like "P1/P2" into "Val1/Val2/Val3"), inserting a new numbered section, and renaming section titles. Use when the user says things like "把这个 docx 里的 P1 改成 Val1", "在总结前加一节", "全文统一术语", "编辑/改一下这个 .docx", or points at any .docx that needs targeted text changes while preserving existing fonts, bold headings, and tables. Does NOT do heavy layout/design work from scratch (use docx-official create flow for that).
---

# docx-surgical-edit

Edit existing `.docx` files precisely and safely without losing their existing formatting (fonts, bold headings, tables, numbering). Built around `python-docx`; keeps changes minimal and verifiable.

## Important ground rules

- **Always back up first.** Copy `X.docx` to `X.bak.docx` before any write.
- **Text lives in runs inside paragraphs.** Reuse an existing run's `.text` to inherit its font/style; do not delete and rebuild runs unless necessary.
- **Multi-run paragraphs are a trap.** A paragraph's text may be split across several runs (e.g. `"建立"` + `"了"` + `"打印前..."`). If you set the whole sentence on the last run while earlier runs still hold prefix text, you get duplicated text (`建立了建立了打印前...`). Inspect `len(p.runs)` before editing; clear all runs, then write the full sentence into one run.
- **New paragraphs: preserve style.** Call `p = anchor.insert_paragraph_before()` then `p.add_run(text)`. For headings, set `run.bold = True`; leave body runs bold unset. Match the document's existing heading convention (many Chinese design docs use **bold Normal** paragraphs as headings, not Word Heading styles — mirror that).
- Keep edits **surgical**: only touch the paragraphs/terms requested.

## Required tooling

- `python3` with `python-docx` installed: `python3 -m pip install --user --upgrade python-docx lxml`
- Optional QA: `pandoc` (re-extract text), `xelatex` (render PDF preview).

## Workflow

### Step 1: Back up + inspect
```bash
python3 -c "import docx; print('ok')"   # confirm python-docx present
cp 目标.docx 目标.bak.docx
```
Open and map the document:
```python
from docx import Document
d = Document('目标.docx')
print(len(d.paragraphs), len(d.tables))
for i, p in enumerate(d.paragraphs):
    print(i, "|", repr(p.text[:80]))
```
If your edit is find-and-replace over specific terms, list every paragraph containing them (with the index and exact text) BEFORE changing anything. This is your edit map.

### Step 2: Record the edit map
For each target occurrence, note: paragraph index, exact current text, exact replacement. Preserve surrounding punctuation and whitespace. Estimate runs with a probe:
```python
for i in [5, 16, 30]:
    p = d.paragraphs[i]
    print(i, "nruns", len(p.runs), "text", repr(p.text))
```

### Step 3: Apply edits
Single-run paragraph (most common):
```python
run = d.paragraphs[idx].runs[-1]
run.text = run.text.replace('旧', '新')
```
Multi-run paragraph (split text) — clear then rewrite one run:
```python
p = d.paragraphs[idx]
full = '整段替换后的完整文本'
for r in p.runs:
    r.text = ''
p.runs[0].text = full
```
Scope the replacement string tightly (include unique context) so `replace` only matches the intended occurrence. Verify each expected change printed a value (no silent no-op).

### Step 4: Insert a new section (before an anchor)
```python
# find the heading paragraph to insert BEFORE
anchor = next(p for p in d.paragraphs if p.text.strip() == '17. 总结')
anchor.runs[-1].text = '18. 总结'   # renumber if needed, clearing other runs
for r in anchor.runs[:-1]:
    r.text = ''
def add(text, bold=False):
    np = anchor.insert_paragraph_before()
    np.add_run(text).bold = bold
add('17. 配套运营与线下保障机制', bold=True)
add('正文内容...')
d.save('目标.docx')
```
`insert_paragraph_before` keeps insertion anchored to the object, so subsequent calls don't shift indices.

### Step 5: QA (always)
1. **Opens cleanly**: `python3 -c "import docx; Document('目标.docx')"`
2. **Terminology check**: re-scan for any stale term left over:
```python
from docx import Document, re
d = Document('目标.docx')
txt = "\n".join(p.text for p in d.paragraphs)
for term in ['P1','P2']:
    print(term, len(re.findall(term, txt)))
```
   Must be 0 for terms you eliminated.
3. **No placeholder residue**: grep the re-extracted text for `TODO|TBD|{{|lorem|xxxx`.
   ```bash
   pandoc 目标.docx -t gfm -o /tmp/chk.md && grep -nEi "TODO|TBD|\{\{|lorem|xxxx|建立了建立了" /tmp/chk.md || echo clean
   ```
4. **Structure intact**: pandoc re-extract and confirm section headings + ordering.
5. **Visual sanity (optional)**: render PDF and spot-check pagination:
   ```bash
   pandoc 目标.docx -o /tmp/qa.pdf --pdf-engine=xelatex -V CJKmainfont="PingFang SC" -V mainfont="PingFang SC"
   ```

## Examples

**User**: "把这个 docx 全文的 P1 改成 Val1、P2 改成 Val3"
→ Inspect-index every P1/P2 paragraph → replace run text each → QA confirms P1=0 P2=0, ValN counts up. Note: terminology substitutions that are part of larger tokens (only replace standalone terms, keep `Val1`/`Val2` untouched — they don't contain standalone `P1`).

**User**: "在总结章节前面加一节《配套运营机制》"
→ Anchor on `17. 总结`, renumber it to `18. 总结`, insert `17. ...` bold heading + body paragraphs before it.

## Troubleshooting

- **Duplicated text ("建立了建立了…")** → multi-run paragraph; the prefix runs were left intact while you overwrote the last run. Clear all runs, write full text into one run.
- **Paragraph not found / replace no-op** → document text may use different whitespace or full-width punctuation. Print `repr(paragraph.text)` and copy exact bytes.
- **Text missing from Chinese PDF preview** → the PDF engine lacks a CJK font. Add `-V CJKmainfont`/`-V mainfont`. This is a rendering-only issue; the docx itself is fine.
- **Headings lost bold** → you rebuilt a run without setting `.bold`. Match the doc's convention (bold Normal paragraphs).
