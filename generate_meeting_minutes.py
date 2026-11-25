#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_meeting_minutes.py — รายงานการประชุม (PDF) [2026-11-25]
POST /generate_meeting_minutes  { html, entityKey, docNumber } → { success, pdfBase64, pages }

ผู้ใช้สั่ง: ตัวอักษร TH Sarabun New ขนาด 14 · ตรวจระยะห่าง / การตัดคำ / ตัดบรรทัดอย่างละเอียด
  - เนื้อรายงาน (HTML ฉบับ Google Docs จาก GAS: div.jt / h1 / h2 / table.at / .vt / .dt / .ag / .sig) จัดหน้าด้วย WeasyPrint
    ฟอนต์ / ขนาด / ระยะบรรทัดชุดเดียวกับหนังสืออื่นของระบบ (template_utils: BODY_PT 14, TITLE_PT 16, LINE_PT 18)
  - ย่อหน้า: ชิดขอบสองด้านแบบ "กระจายแบบไทย" ตัดบรรทัดเฉพาะรอยต่อคำ (libthai — justify_html)
  - ไม่ตัดกลาง: ชื่อบุคคล / ชื่อบริษัท (ทีละคำ) · ตัวเลขกับหน่วย (100,000 หุ้น) · วันที่ (16 พฤศจิกายน พ.ศ. 2569)
    · "ครั้งที่ / วาระที่ / ข้อ / มาตรา / เลขที่ / ร้อยละ / หุ้นละ" กับตัวเลข · คำนำหน้าชื่อกับชื่อ
  - หัวข้อไม่ค้างท้ายหน้า · แถวตารางไม่ขาดกลางแถว · หัวตารางซ้ำเมื่อขึ้นหน้าใหม่ · ช่องลงนามไม่แยกหน้า
  - วางบนหัวกระดาษบริษัท (โลโก้ / ลายน้ำ / ท้ายกระดาษ) — merge_on_template ; ตัดแท็ก / รูปที่โหลด URL ภายนอกได้ออกก่อนจัดหน้า
"""

import base64
import logging
import re
from io import BytesIO
from flask import request, jsonify
from pypdf import PdfReader
from template_utils import (font_face_css, justify_css, justify_html, page_head_css, merge_on_template,
                            BODY_PT, TITLE_PT, SMALL_PT, LINE_PT)

logger = logging.getLogger(__name__)
_MAX_HTML = 3 * 1024 * 1024
NB = ' '

_MONTHS = ('มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม|'
           'ม\\.ค\\.|ก\\.พ\\.|มี\\.ค\\.|เม\\.ย\\.|พ\\.ค\\.|มิ\\.ย\\.|ก\\.ค\\.|ส\\.ค\\.|ก\\.ย\\.|ต\\.ค\\.|พ\\.ย\\.|ธ\\.ค\\.')
_UNITS = 'หุ้น|บาท|ราย|คน|วัน|เสียง|น\\.|ฉบับ|ปี|เดือน|ครั้ง|สตางค์|ชั่วโมง|นาที'
# ช่องว่างที่ห้ามขึ้นบรรทัดใหม่ → NBSP (ยังเป็นจุดกระจายช่องไฟของ justify_html)
_GLUE = [
    re.compile(r'(\d[\d,.]*) +(?=(?:%s)(?![ก-๙]))' % _UNITS),                    # 100,000 หุ้น · 10 บาท
    re.compile(r'(\d{1,2}) +(?=(?:%s))' % _MONTHS),                               # 16 พฤศจิกายน
    re.compile(r'((?:%s)) +(?=(?:พ\.ศ\.|\d{4}))' % _MONTHS),                       # พฤศจิกายน พ.ศ.
    re.compile(r'(พ\.ศ\.|ค\.ศ\.) *(?=\d)'),                                         # พ.ศ. 2569
    re.compile(r'(ครั้งที่|วาระที่|ข้อ|มาตรา|เลขที่|ร้อยละ|หุ้นละ|ลำดับที่|เวลา|วันที่|จำนวน) +(?=\d)'),
    re.compile(r'(นางสาว|นาง|นาย|คุณ|ดร\.) +(?=[ก-๙A-Za-z])'),                      # คำนำหน้ากับชื่อ
]
_NAME = re.compile(r'((?:นางสาว|นาง|นาย|คุณ|ดร\.) )(\S{1,30})(?: (\S{1,30}))?')
_COMPANY = re.compile(r'(บริษัท) ((?:\S{1,30} ){0,6}?)(จำกัด(?: \(มหาชน\))?)')
_TOKEN = re.compile(r'(<[^>]+>|&[#\w]+;)')
_NB_RUN = re.compile('[^\\s\u00a0]+(?:\u00a0[^\\s\u00a0]+)+')
_JT = re.compile(r'(<div class="jt[^"]*">)(.*?)(</div>)', re.S)


def _nw(s):
    return '<span class="nw">%s</span>' % s


def _smart_text(t):
    """ข้อความล้วน (escape แล้ว) → ติดกาว NBSP + ห่อชื่อด้วย .nw (ขึ้นบรรทัดใหม่ได้เฉพาะระหว่างคำของชื่อ)"""
    for rx in _GLUE:
        t = rx.sub(lambda m: m.group(1) + NB, t)
    t = _COMPANY.sub(lambda m: _nw(m.group(1)) + ' ' + ' '.join(_nw(w) for w in m.group(2).split()) + (' ' if m.group(2) else '') + _nw(m.group(3)), t)
    t = _NAME.sub(lambda m: _nw(m.group(1) + m.group(2)) + ((' ' + _nw(m.group(3))) if m.group(3) else ''), t)
    # NBSP ในย่อหน้าที่จัดชิดขอบถูกหดเป็นศูนย์ (word-spacing ติดลบของ justify) → ใช้ช่องว่างปกติใน .nw แทน: ไม่ตัดบรรทัด + กว้างปกติ
    parts = re.split(r'(<span class="nw">.*?</span>)', t)
    for i, p in enumerate(parts):
        if p.startswith('<span class="nw">'):
            parts[i] = p.replace(NB, ' ')
        else:
            parts[i] = _NB_RUN.sub(lambda m: _nw(m.group(0).replace(NB, ' ')), p)
    return ''.join(parts)


def smart_breaks(html):
    """ใส่กติกาการตัดบรรทัดให้ทุกข้อความใน HTML (ไม่แตะแท็ก / entity / ข้อความใน .nw ที่มีอยู่แล้ว)"""
    out, keep = [], 0
    for part in _TOKEN.split(html):
        if not part:
            continue
        if part.startswith('<'):
            if part.startswith('<span class="nw"'):
                keep += 1
            elif part == '</span>' and keep:
                keep -= 1
            out.append(part)
        elif part.startswith('&') and part.endswith(';'):
            out.append(part)
        else:
            out.append(part if keep else _smart_text(part))
    return ''.join(out)


def _thead(html):
    """แถวหัวตาราง (แถวแรกที่มี <th>) → <thead> : WeasyPrint พิมพ์ซ้ำเมื่อตารางขึ้นหน้าใหม่"""
    return re.sub(r'(<table[^>]*>)\s*(<tr>(?:(?!</tr>).)*?<th[\s>].*?</tr>)', r'\1<thead>\2</thead>', html, flags=re.S)


def _css(doc_number):
    lh = round(LINE_PT / BODY_PT, 3)
    return font_face_css() + """
    @page { size: A4; margin: 30mm 20mm 25mm 25mm;
            @top-left { content: %(head)s; font-family: 'THSarabunNew'; font-size: %(small)spt; color: #333;
                        white-space: pre; vertical-align: bottom; padding-bottom: 2.5mm; } }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: 'THSarabunNew', 'TH Sarabun New', sans-serif; font-size: %(pt)spt; line-height: %(lh)s; color: #000; }
    h1 { font-size: %(title)spt; font-weight: bold; text-align: center; margin: 0; line-height: 1.25; page-break-after: avoid; }
    h2 { font-size: %(pt)spt; font-weight: bold; margin: 3.2mm 0 0.8mm; page-break-after: avoid; }
    h2 b, h2 { break-after: avoid; }
    .c { text-align: center; } .b, .b td { font-weight: bold; } .n { text-align: right; white-space: nowrap; }
    .ind { text-indent: 10mm; }
    .jt { margin: 0 0 1.2mm; orphans: 2; widows: 2; }
    %(justify)s
    .nw { white-space: nowrap; }
    .draft { color: #b91c1c; text-align: center; font-weight: bold; margin: 0 0 2mm; }
    .ag { margin-top: 3.2mm; }
    .ag .t { font-weight: bold; page-break-after: avoid; margin-bottom: 0.8mm; }
    table { border-collapse: collapse; margin: 1.6mm auto 2.4mm; font-size: %(pt)spt; line-height: 1.2; }
    thead { display: table-header-group; }
    tr { page-break-inside: avoid; }
    th, td { border: 0.6pt solid #000; padding: 0.8mm 2.4mm; vertical-align: top; }
    th { font-weight: bold; text-align: center; vertical-align: middle; }
    table.vt { page-break-inside: avoid; }
    .pg { page-break-before: always; }
    .wn th, .wn td { border-color: #888; font-size: %(small2)spt; padding: 0.6mm 1.6mm; }
    .sig { margin-top: 12mm; page-break-inside: avoid; }
    .sig div { text-align: center; margin: 7mm 0 0 45%%; }
    """ % {'head': page_head_css(doc_number), 'small': SMALL_PT, 'pt': BODY_PT, 'title': TITLE_PT, 'lh': lh,
           'small2': round(BODY_PT - 2, 2), 'justify': justify_css('.jt')}


def build_minutes_html(html, doc_number=''):
    m = re.search(r'<body[^>]*>(.*)</body>', html, re.S)
    body = m.group(1) if m else html
    body = re.sub(r'<script.*?</script>|<style.*?</style>', '', body, flags=re.S | re.I)
    # ไม่ให้เนื้อรายงานดึงอะไรจากภายนอก: ตัดแท็กที่โหลด URL ได้ และรูปที่ไม่ใช่ data:
    body = re.sub(r'<(?:link|iframe|object|embed|base|meta)\b[^>]*>', '', body, flags=re.I)
    body = re.sub(r'<img\b(?![^>]*\ssrc="data:)[^>]*>', '', body, flags=re.I)
    body = re.sub(r'\sstyle="[^"]*"', '', body)            # ระยะ / ขนาดของหน้าพิมพ์ใน GAS ไม่ใช้ — ใช้ CSS ชุดนี้
    body = _thead(smart_breaks(body))
    body = _JT.sub(lambda x: x.group(1) + justify_html(x.group(2)) + x.group(3), body)
    return ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>%s</style></head><body>%s</body></html>'
            % (_css(doc_number), body))


def render_minutes(html, entity_key='', doc_number=''):
    from weasyprint import HTML
    pdf = HTML(string=build_minutes_html(html, doc_number)).write_pdf()   # ฟอนต์ฝัง data: ใน CSS ; เนื้อหาไม่มี URL ภายนอก (build_minutes_html)
    out = merge_on_template(pdf, entity_key)
    return out, len(PdfReader(BytesIO(out)).pages)


def register_meeting_minutes_routes(app):
    @app.route('/generate_meeting_minutes', methods=['POST'])
    def api_generate_meeting_minutes():
        try:
            from app import _check_key
            err = _check_key()
            if err:
                return err
            data = request.get_json() or {}
            html = str(data.get('html') or '')
            if not html or len(html) > _MAX_HTML:
                return jsonify({'success': False, 'message': 'ไม่มีเนื้อรายงาน หรือใหญ่เกินไป'}), 400
            pdf, pages = render_minutes(html, str(data.get('entityKey') or ''), str(data.get('docNumber') or ''))
            return jsonify({'success': True, 'pdfBase64': base64.b64encode(pdf).decode('utf-8'), 'pages': pages})
        except Exception as e:
            logger.error('generate_meeting_minutes error: %s', e)
            from app import _safe_error
            return jsonify(_safe_error(e, 'generate_meeting_minutes')), 500
