#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hr_doc_layout.py — โครงหน้าร่วมของ "หนังสือตักเตือนพนักงาน" และ "สัญญาฝึกอบรม"
═══════════════════════════════════════════════════════════════════════════════
  • ตัวอักษร TH Sarabun New 14 (ขนาดแบบ Word — ดู template_utils.th_pt) ชื่อเอกสาร 16 ตัวหนา
  • ไม่มีเส้นกรอบรอบเอกสาร (FRAME = False) — เปิดกรอบคืนได้ด้วยการตั้ง FRAME = True
  • เนื้อหาไหลต่อเนื่องข้ามหน้า ; เลขที่หนังสือ + "หน้า x / y" อยู่ที่ขอบบนทุกหน้า (@page margin box)
  • หัวข้อไม่ถูกทิ้งไว้ท้ายหน้า และช่องลงนามไม่ถูกตัดข้ามหน้า
  • ช่องข้อมูล: ป้าย + ค่าบนเส้นประ ; ช่องลงนาม: "ลงชื่อ ........ " / (ชื่อ) / ฐานะ

ถ้อยคำของเอกสารอยู่ในไฟล์ generate_*.py ตามเดิม — ไฟล์นี้มีเฉพาะการจัดหน้า
"""

from template_utils import (
    BODY_PT, TITLE_PT, SMALL_PT, font_face_css, page_head_css, merge_on_template, checkbox_svg
)

# เส้นกรอบรอบเอกสาร — ปิดไว้ (หัวกระดาษของบริษัทมีเส้นและลายน้ำอยู่แล้ว กรอบทำให้หน้าแน่นและเสียความกว้างบรรทัด)
FRAME = False

# ระยะบรรทัด (pt จริง): ปกติ ≈ บรรทัดเดี่ยวของ TH Sarabun New 14 ใน Word ; compact สำหรับสัญญาที่ข้อความยาว
_LINE_PT = {False: 18, True: 17.5}


def esc(s):
    """HTML-escape"""
    return (str('' if s is None else s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


# ══════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════

def build_css(doc_number='', compact=False, frame=None):
    """CSS ของเอกสาร — compact = ระยะบรรทัด/ย่อหน้าแน่นขึ้น (สัญญาที่ข้อความยาว) ; frame = มีเส้นกรอบ (ค่าเริ่มต้นตาม FRAME)"""
    frame = FRAME if frame is None else frame
    lh = round(_LINE_PT[bool(compact)] / BODY_PT, 3)
    if frame:
        page_margin = '27mm 18mm 24mm 22mm'
        frame_css = """
    .frame { border: 1pt solid #262626; padding: 5mm 8mm 6mm; box-decoration-break: clone; }
    .band  { margin: -5mm -8mm 5mm; padding: 3.5mm 8mm 3mm; background: #eef1f5; border-bottom: 0.8pt solid #262626;
             text-align: center; font-size: %(title)spt; font-weight: bold; page-break-after: avoid; }
    .lead  { margin: 0 0 3mm; padding-bottom: 2.5mm; border-bottom: 0.5pt solid #c9ced6; }
    .box   { border: 0.8pt solid #9aa0a8; border-radius: 1.5pt; background: #fafafa; padding: 3mm 5mm 1mm; margin: 0 0 4mm;
             min-height: 20mm; box-decoration-break: clone; }
    .note  { border-left: 2pt solid #9aa0a8; background: #f5f6f8; padding: 3mm 5mm 1mm; margin: 0 0 4mm; page-break-inside: avoid; }
    .note p { text-indent: 0; }
    """ % {'title': TITLE_PT}
    else:
        # ขอบกระดาษชุดเดียวกับหนังสือทั่วไป — เว้นที่ให้โลโก้บนขวาและแถบที่อยู่ด้านล่างของหัวกระดาษ
        page_margin = '30mm 20mm 25mm 25mm'
        frame_css = """
    .frame { }
    .band  { margin: 0 0 5mm; text-align: center; font-size: %(title)spt; font-weight: bold; page-break-after: avoid; }
    .lead  { margin: 0 0 3mm; }
    .box   { margin: 0 0 3mm; }
    .note  { margin: 0 0 3mm; page-break-inside: avoid; }
    """ % {'title': TITLE_PT}

    return font_face_css() + """
    @page {
        size: A4;
        margin: %(margin)s;
        @top-left {
            content: %(head)s;
            font-family: 'THSarabunNew', 'TH Sarabun New', sans-serif; font-size: %(small)spt; color: #333;
            white-space: pre; vertical-align: bottom; padding-bottom: 2.5mm;
        }
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'THSarabunNew', 'TH Sarabun New', sans-serif; font-size: %(pt)spt; line-height: %(lh)s; color: #000; }
    %(frame_css)s
    p        { margin: 0 0 %(gap)s; text-indent: 10mm; text-align: left; word-wrap: break-word; orphans: 2; widows: 2; }
    .nw      { white-space: nowrap; }                 /* ชื่อบริษัท / ที่อยู่ ไม่ถูกตัดกลางคำ */
    .keep    { page-break-inside: avoid; }            /* ย่อหน้าท้าย + ช่องลงนาม อยู่หน้าเดียวกัน (ไม่มีหน้าลายเซ็นที่ไม่มีข้อความ) */
    p.flush  { text-indent: 0; }
    .sec     { font-weight: bold; text-decoration: underline; margin: 3mm 0 1.5mm; page-break-after: avoid; }
    .ul      { text-decoration: underline; }

    /* ช่องข้อมูล: ป้าย + ค่าบนเส้นประ */
    .fieldset { margin: 0 0 2mm; page-break-inside: avoid; }
    table.fields { width: 100%%; border-collapse: collapse; }
    table.fields td { padding: 0.6mm 2mm 0; vertical-align: bottom; line-height: 1.6; }
    table.fields td.lbl { font-weight: bold; white-space: nowrap; width: 1%%; padding-left: 0; padding-right: 2.5mm; }   /* ป้ายกว้างเท่าข้อความ ไม่ล้นทับค่า */
    table.fields td.val + td.lbl { padding-left: 5mm; }
    table.fields td.val { border-bottom: 0.6pt dotted #777; word-wrap: break-word; }

    /* ตัวเลือก ☐/☒ — วาดด้วย SVG ไม่ขึ้นกับฟอนต์ */
    .opt { margin: 0.6mm 0 0.6mm 12mm; padding-left: 7mm; text-indent: -7mm; page-break-inside: avoid; }
    .opt svg { width: 3.6mm; height: 3.6mm; vertical-align: -0.5mm; margin-right: 3.4mm; }

    /* ข้อสัญญา */
    .cl   { margin: 0 0 %(gap)s; text-indent: 0; }
    .cl b { margin-right: 1.5mm; }
    .sub  { margin: 0 0 %(gap)s 12mm; padding-left: 6.8mm; text-indent: -6.8mm; }

    /* ช่องลงนาม: เว้นที่เหนือเส้นให้ลงลายมือชื่อ ; สองคอลัมน์ห่างกันชัดเจน */
    table.sign { width: 100%%; border-collapse: collapse; margin-top: 1mm; page-break-inside: avoid; }
    table.sign td { width: 50%%; padding: %(sgtop)s 0 0; vertical-align: top; line-height: 1.6; }
    table.sign td[colspan] { width: 100%%; }
    .sg      { width: 66mm; margin: 0 auto; }
    .sg-row  { white-space: nowrap; }
    .sg-pre  { display: inline-block; width: 11mm; }
    .sg-line { display: inline-block; width: 55mm; border-bottom: 0.6pt dotted #333; height: 5mm; }
    .sg-name { margin-left: 11mm; width: 55mm; text-align: center; padding-top: 0.3mm; }
    .sg-role { margin-left: 11mm; width: 55mm; text-align: center; }
    """ % {'head': page_head_css(doc_number), 'margin': page_margin, 'small': SMALL_PT, 'pt': BODY_PT, 'lh': lh,
           'frame_css': frame_css, 'gap': '1.6mm' if compact else '2.4mm', 'sgtop': '8.5mm' if compact else '9.5mm'}


# ══════════════════════════════════════════════════════════════════════
# HTML helpers
# ══════════════════════════════════════════════════════════════════════

def checkbox(checked):
    """ช่องตัวเลือก ☐/☒ (SVG) — เดิมใช้อักขระซึ่งขึ้นกับฟอนต์สำรองของเครื่อง"""
    return checkbox_svg(checked, mark='cross')


def option(checked, text):
    return '<div class="opt">' + checkbox(checked) + esc(text) + '</div>'


def paragraphs(text, cls=''):
    """ข้อความหลายบรรทัด → <p> ต่อบรรทัด (บรรทัดว่างถูกข้าม)"""
    lines = [ln.strip() for ln in str(text or '').split('\n') if ln.strip()]
    c = (' class="%s"' % cls) if cls else ''
    return '\n'.join('<p%s>%s</p>' % (c, esc(ln)) for ln in lines)


def fields(rows):
    """ช่องข้อมูล (ป้าย + ค่าบนเส้นประ) — rows = [[(ป้าย, ค่า), (ป้าย, ค่า, 'กว้าง')…], …] แถวละ 1–3 คู่
    แต่ละแถวจัดความกว้างของตัวเอง: ป้ายกว้างเท่าข้อความ ค่าได้ที่เหลือ (ระบุความกว้างของค่าเองได้ เช่น '16mm')
    เดิมทุกแถวใช้คอลัมน์ชุดเดียวกัน — ป้ายยาว ("เลขประจำตัวประชาชน") ทำให้ช่องชื่อ/ตำแหน่งแคบจนขึ้นบรรทัดใหม่"""
    h = '<div class="fieldset">'
    for row in rows:
        h += '<table class="fields"><tr>'
        for item in row:
            label, value = item[0], item[1]
            width = (' style="width:%s"' % item[2]) if len(item) > 2 and item[2] else ''
            h += '<td class="lbl">%s</td><td class="val"%s>%s</td>' % (esc(label), width, esc(value) or '&nbsp;')
        h += '</tr></table>'
    return h + '</div>'


def signatures(cells):
    """ช่องลงนาม 2 คอลัมน์ — cells = [(ฐานะ, ชื่อ) | None, …] เรียงซ้าย→ขวา บน→ล่าง ; None = เว้นช่อง
    แถวที่ว่างทั้งแถวถูกตัดออก"""
    def cell(c):
        if not c:
            return '<td></td>'
        role, name = c
        # มีชื่อ → (ชื่อ) ใต้เส้น ; ไม่มีชื่อ → ไม่ใส่วงเล็บว่าง (ตามที่ใช้มาเดิม)
        nm = '<div class="sg-name">(%s)</div>' % esc(name) if str(name or '').strip() else ''
        return ('<td><div class="sg"><div class="sg-row"><span class="sg-pre">ลงชื่อ</span><span class="sg-line"></span></div>'
                '%s<div class="sg-role">%s</div></div></td>' % (nm, esc(role)))
    h = '<table class="sign">'
    for i in range(0, len(cells), 2):
        pair = list(cells[i:i + 2]) + [None] * (2 - len(cells[i:i + 2]))
        if not any(pair):
            continue
        if pair[0] and pair[1]:
            h += '<tr>' + cell(pair[0]) + cell(pair[1]) + '</tr>'
        else:
            # แถวที่มีผู้ลงนามคนเดียว → อยู่กึ่งกลาง (ไม่ทิ้งช่องว่างครึ่งแถว)
            h += '<tr>' + cell(pair[0] or pair[1]).replace('<td>', '<td colspan="2">', 1) + '</tr>'
    return h + '</table>'


def nowrap(text):
    """ชื่อบริษัท / ที่อยู่ — ไม่ให้ตัวตัดบรรทัดภาษาไทยตัดกลางคำ (เช่น "เทคโน | โลจีส์", "เขตบาง | รัก")
    ขึ้นบรรทัดใหม่ได้เฉพาะตรงช่องว่างระหว่างคำ ; คำที่ยาวผิดปกติ (ไม่มีช่องว่างเลย) ปล่อยให้ตัดได้ตามเดิม กันล้นกรอบ"""
    return ' '.join(('<span class="nw">%s</span>' % esc(t)) if len(t) <= 40 else esc(t) for t in str(text or '').split())


def document(title, body_html, doc_number='', compact=False, frame=None):
    """เอกสารเต็ม: ชื่อเอกสาร + เนื้อหา (มี/ไม่มีเส้นกรอบตาม FRAME)"""
    return ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>%s</style></head><body>'
            '<div class="frame"><div class="band">%s</div>%s</div></body></html>'
            % (build_css(doc_number, compact, frame), esc(title), body_html))


# ซ้อนเนื้อหาทุกหน้าบนหัวกระดาษของบริษัท — ตัวเดียวกับที่หนังสืออื่นใช้ (template_utils.merge_on_template)
merge_multi_page = merge_on_template
