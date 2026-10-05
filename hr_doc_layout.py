#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hr_doc_layout.py — โครงหน้าร่วมของ "หนังสือตักเตือนพนักงาน" และ "สัญญาฝึกอบรม"
═══════════════════════════════════════════════════════════════════════════════
เดิมสองไฟล์เขียน CSS / ช่องลงนาม / ตัวซ้อนหัวกระดาษ แยกกันคนละชุด และมีปัญหาเดียวกัน:

  • ระยะขอบในกรอบไม่ทำงาน — กฎ `.xx-tbl td { padding: 0 }` ชนะ `.xx-content { padding: … }`
    ข้อความจึงชิดเส้นกรอบทั้งซ้ายและขวา และแถบหัวเรื่องแคบ
  • บังคับขึ้นหน้า 2 ที่ตำแหน่งตายตัว — หน้าแรกแน่นหรือโหว่ตามความยาวเนื้อหา
    และถ้าเนื้อหายาวเกินหน้า กรอบจะขาดกลางหน้า
  • ช่องลงนามเป็นตารางมีเส้นทุกช่อง รวมช่องว่างของผู้ลงนามคนที่ 2

ที่นี่:
  • กรอบเดียวไหลต่อเนื่องข้ามหน้า (box-decoration-break: clone — ทุกหน้ามีกรอบและระยะขอบครบ)
  • เลขที่หนังสือ + "หน้า x / y" อยู่ที่ขอบบนทุกหน้า (@page margin box)
  • หัวข้อไม่ถูกทิ้งไว้ท้ายหน้า และช่องลงนามไม่ถูกตัดข้ามหน้า
  • ช่องลงนามไม่มีเส้นตาราง: "ลงชื่อ ........ " / (ชื่อ) / ฐานะ

ถ้อยคำของเอกสารอยู่ในไฟล์ generate_*.py ตามเดิม — ไฟล์นี้มีเฉพาะการจัดหน้า
"""

import os
from io import BytesIO

from template_utils import font_b64, resolve_template


def esc(s):
    """HTML-escape"""
    return (str('' if s is None else s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def _css_str(s):
    """ข้อความสำหรับใส่ใน content: "…" ของ CSS"""
    return (str('' if s is None else s).replace('\\', '\\\\').replace('"', '\\"')
            .replace('\n', ' ').replace('\r', ' '))


# ══════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════

def build_css(doc_number='', base_pt=11.5, compact=False):
    """CSS ของเอกสาร — base_pt = ขนาดตัวอักษรเนื้อหา ; compact = ระยะบรรทัด/ย่อหน้าแน่นขึ้น (เอกสารที่ต้องลงใน 2 หน้า)"""
    fonts = font_b64()
    ff = ''
    for weight, fn in (('normal', 'THSarabunNew.ttf'), ('bold', 'THSarabunNew-Bold.ttf')):
        if fonts.get(fn):
            ff += ("@font-face { font-family: 'THSarabunNew'; font-weight: %s; "
                   "src: url('data:font/truetype;base64,%s') format('truetype'); }\n" % (weight, fonts[fn]))

    # หัวกระดาษทุกหน้า: เลขที่ … · หน้า x / y
    head = ('"เลขที่ %s    ·    หน้า " counter(page) " / " counter(pages)' % _css_str(doc_number)) if str(doc_number or '').strip() \
        else '"หน้า " counter(page) " / " counter(pages)'
    return ff + """
    /* ขอบกระดาษเว้นที่ให้หัวกระดาษ (โลโก้บนขวา) และแถบที่อยู่ด้านล่างของ template */
    @page {
        size: A4;
        margin: 27mm 18mm 24mm 22mm;
        @top-left {
            content: %(head)s;
            font-family: 'THSarabunNew', 'TH Sarabun New', sans-serif; font-size: 10.5pt; color: #333;
            white-space: pre; vertical-align: bottom; padding-bottom: 2.5mm;
        }
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'THSarabunNew', 'TH Sarabun New', sans-serif; font-size: %(pt)spt; line-height: %(lh)s; color: #000; }

    /* กรอบเอกสาร — ไหลข้ามหน้าได้ ทุกหน้ามีเส้นกรอบและระยะขอบในครบ */
    .frame { border: 1pt solid #262626; padding: 5mm 8mm 6mm; box-decoration-break: clone; }
    .band  { margin: -5mm -8mm 5mm; padding: 4.5mm 8mm 4mm; background: #eef1f5; border-bottom: 0.8pt solid #262626;
             text-align: center; font-size: 1.35em; font-weight: bold; letter-spacing: 0.3pt; page-break-after: avoid; }

    p        { margin: 0 0 %(gap)s; text-indent: 10mm; text-align: left; word-wrap: break-word; orphans: 2; widows: 2; }
    .nw      { white-space: nowrap; }                 /* ชื่อบริษัท / ชื่อบุคคล ไม่ถูกตัดกลางคำ */
    .keep    { page-break-inside: avoid; }            /* ย่อหน้าท้าย + ช่องลงนาม อยู่หน้าเดียวกัน (ไม่มีหน้าลายเซ็นที่ไม่มีข้อความสัญญา) */
    p.flush  { text-indent: 0; }
    .lead    { margin: 0 0 3mm; padding-bottom: 2.5mm; border-bottom: 0.5pt solid #c9ced6; }
    .sec     { font-weight: bold; text-decoration: underline; margin: 4mm 0 2mm; page-break-after: avoid; }
    .ul      { text-decoration: underline; }

    /* ช่องข้อมูล: ป้าย + ค่าบนเส้นประ */
    .fieldset { margin: 1mm 0 3mm; page-break-inside: avoid; }
    table.fields { width: 100%%; border-collapse: collapse; }
    table.fields td { padding: 1.3mm 2mm 0.6mm; vertical-align: bottom; }
    table.fields td.lbl { font-weight: bold; white-space: nowrap; width: 1%%; padding-right: 3mm; }   /* ป้ายกว้างเท่าข้อความ ไม่ล้นทับค่า */
    table.fields td.val + td.lbl { padding-left: 6mm; }
    table.fields td.val { border-bottom: 0.6pt dotted #777; word-wrap: break-word; }

    /* กล่องข้อความ */
    .box  { border: 0.8pt solid #9aa0a8; border-radius: 1.5pt; background: #fafafa; padding: 3.5mm 5mm 1.5mm; margin: 0 0 4mm; min-height: 22mm;
            box-decoration-break: clone; }   /* ข้อความยาวข้ามหน้า → กล่องปิดเส้นครบทั้งสองหน้า */
    .note { border-left: 2pt solid #9aa0a8; background: #f5f6f8; padding: 3mm 5mm 1mm; margin: 0 0 4mm; font-size: 0.93em; page-break-inside: avoid; }
    .note p { text-indent: 0; margin-bottom: 2mm; }

    /* ตัวเลือก ☐/☒ — วาดด้วย SVG ไม่ขึ้นกับฟอนต์ */
    .opt { margin: 1.2mm 0 1.2mm 12mm; padding-left: 7mm; text-indent: -7mm; page-break-inside: avoid; }
    .opt svg { width: 3.7mm; height: 3.7mm; vertical-align: -0.6mm; margin-right: 3.3mm; }

    /* ข้อสัญญา */
    .cl   { margin: 0 0 %(gap)s; text-indent: 0; }
    .cl b { margin-right: 1.5mm; }
    .sub  { margin: 0 0 %(gap)s 12mm; padding-left: 6.8mm; text-indent: -6.8mm; }

    /* ช่องลงนาม */
    /* ช่องลงนาม: เว้นที่เหนือเส้นให้ลงลายมือชื่อ ; สองคอลัมน์ห่างกันชัดเจน */
    table.sign { width: 100%%; border-collapse: collapse; margin-top: 2mm; page-break-inside: avoid; }
    table.sign td { width: 50%%; padding: %(sgtop)s 0 0; vertical-align: top; }
    table.sign td[colspan] { width: 100%%; }
    .sg      { width: 64mm; margin: 0 auto; }
    .sg-row  { white-space: nowrap; }
    .sg-pre  { display: inline-block; width: 10mm; }
    .sg-line { display: inline-block; width: 54mm; border-bottom: 0.6pt dotted #333; height: 5mm; }
    .sg-name { margin-left: 10mm; width: 54mm; text-align: center; padding-top: 0.6mm; }
    .sg-role { margin-left: 10mm; width: 54mm; text-align: center; color: #333; font-size: 0.95em; }
    """ % {'head': head, 'pt': base_pt, 'lh': '1.42' if compact else '1.5', 'gap': '1.9mm' if compact else '2.4mm',
           'sgtop': '9.5mm' if compact else '10mm'}


# ══════════════════════════════════════════════════════════════════════
# HTML helpers
# ══════════════════════════════════════════════════════════════════════

def checkbox(checked):
    """ช่องตัวเลือก (SVG) — เดิมใช้อักขระ ☐/☒ ซึ่งขึ้นกับฟอนต์สำรองของเครื่อง"""
    mark = '<path d="M3 3 L9 9 M9 3 L3 9" stroke="#000" stroke-width="1.5" stroke-linecap="round"/>' if checked else ''
    return ('<svg viewBox="0 0 12 12" xmlns="http://www.w3.org/2000/svg">'
            '<rect x="0.7" y="0.7" width="10.6" height="10.6" fill="#fff" stroke="#000" stroke-width="1.1"/>' + mark + '</svg>')


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


def document(title, body_html, doc_number='', base_pt=11.5, compact=False):
    """เอกสารเต็ม: กรอบ + แถบหัวเรื่อง + เนื้อหา"""
    return ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>%s</style></head><body>'
            '<div class="frame"><div class="band">%s</div>%s</div></body></html>'
            % (build_css(doc_number, base_pt, compact), esc(title), body_html))


# ══════════════════════════════════════════════════════════════════════
# ซ้อนเนื้อหาทุกหน้าบนหัวกระดาษของบริษัท
# ══════════════════════════════════════════════════════════════════════

def merge_multi_page(content_bytes, entity_key):
    """Overlay ทุกหน้าของ content บน entity template (logo + watermark)

    เปลี่ยนชื่อฟอนต์ THSarabunNew ของ "เนื้อหา" เป็น THSarabunNewCTN ก่อนซ้อน — template ฝังฟอนต์ชื่อเดียวกัน
    แบบ subset ถ้าชื่อชนกันตัวอักษรจะเพี้ยน
    """
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject

    base = os.path.dirname(os.path.abspath(__file__))
    tpl_path = os.path.join(base, resolve_template(entity_key))
    if not os.path.exists(tpl_path):
        tpl_path = os.path.join(base, 'bg_template_scmtech.pdf')
    if not os.path.exists(tpl_path):
        return content_bytes

    def rename(obj, key):
        val = str(obj.get(key, ''))
        if 'THSarabunNew' in val and 'CTN' not in val:
            obj[NameObject(key)] = NameObject('/' + val.replace('THSarabunNew', 'THSarabunNewCTN').lstrip('/'))

    writer = PdfWriter()
    for page in PdfReader(BytesIO(content_bytes)).pages:
        bg = PdfReader(tpl_path).pages[0]
        content_fonts = page.get('/Resources', {}).get('/Font', {})
        for key in list(content_fonts.keys()):
            try:
                font_obj = content_fonts[key].get_object()
                rename(font_obj, '/BaseFont')
                for desc_ref in font_obj.get('/DescendantFonts', []):
                    desc = desc_ref.get_object()
                    rename(desc, '/BaseFont')
                    if '/FontDescriptor' in desc:
                        rename(desc['/FontDescriptor'].get_object(), '/FontName')
                if '/FontDescriptor' in font_obj:
                    rename(font_obj['/FontDescriptor'].get_object(), '/FontName')
            except Exception:
                pass
        bg.merge_page(page)
        writer.add_page(bg)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()
