#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
template_utils.py — Shared PDF Template Utilities
══════════════════════════════════════════════════
ใช้ร่วมกันทุกฟอร์ม PDF ที่ overlay บน entity template

Usage:
    from template_utils import merge_on_template, html_to_pdf, build_css, fmt, fmt_date_th

    html = f'<div class="page">...</div>'
    css  = build_css()
    full_html = f'<!DOCTYPE html><html><head><style>{css}</style></head><body>{html}</body></html>'
    final_pdf = merge_on_template(html_to_pdf(full_html), entity_key='SCM Tech')

Functions:
    merge_on_template(content_bytes, entity_key) → PDF bytes ที่ overlay บน template
    html_to_pdf(html_string) → PDF bytes จาก HTML (ใช้ WeasyPrint)
    build_css(fonts=None) → CSS string พร้อม font-face + page layout
    fmt(value) → format ตัวเลข comma + 2 decimal ("1,439,000.00")
    fmt_date_th(date_str) → format วันที่ Thai เต็ม ("28 กุมภาพันธ์ พ.ศ.2568")
    font_b64() → dict ของ font base64 สำหรับ embed ใน CSS
    resolve_template(entity_key) → template filename
"""

import os
import base64
import logging
from io import BytesIO
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# NUMBER & DATE FORMATTERS
# ══════════════════════════════════════════════════════════════════════

def fmt(v):
    """แปลงตัวเลข → format xxx,xxx.xx (comma + 2 decimal)
    ตัวอย่าง: 1439000 → '1,439,000.00' / 0 → '' / None → ''
    """
    if not v:
        return ''
    try:
        n = float(str(v).replace(',', ''))
        if n == 0:
            return ''
        return f'{n:,.2f}'
    except (ValueError, TypeError):
        return str(v)


_TH_MONTHS = [
    'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
    'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'
]

def fmt_date_th(v):
    """แปลง dd/mm/yyyy (พ.ศ.) → 'd เดือน พ.ศ.yyyy'
    ตัวอย่าง: '28/02/2568' → '28 กุมภาพันธ์ พ.ศ.2568'
    ถ้า format ไม่ตรง → คืนค่าเดิม (ไม่ crash)
    """
    if not v:
        return ''
    s = str(v).strip()
    parts = s.split('/')
    if len(parts) != 3:
        return s  # อาจเป็นแบบเต็มอยู่แล้ว
    try:
        d = int(parts[0])
        m = int(parts[1])
        y = parts[2]
        if m < 1 or m > 12:
            return s
        return f'{d} {_TH_MONTHS[m-1]} พ.ศ.{y}'
    except (ValueError, IndexError):
        return s


# ══════════════════════════════════════════════════════════════════════
# FONT UTILITIES
# ══════════════════════════════════════════════════════════════════════

def font_b64():
    """โหลด THSarabunNew เป็น base64 สำหรับ embed ใน CSS @font-face"""
    base = os.path.dirname(os.path.abspath(__file__))
    result = {}
    for fn in ['THSarabunNew.ttf', 'THSarabunNew-Bold.ttf']:
        p = os.path.join(base, 'fonts', fn)
        if os.path.exists(p):
            with open(p, 'rb') as f:
                result[fn] = base64.b64encode(f.read()).decode()
    return result


# ══════════════════════════════════════════════════════════════════════
# CSS BUILDER
# ══════════════════════════════════════════════════════════════════════

def build_css(fonts=None):
    """สร้าง CSS สำหรับ A4 PDF — TH Sarabun New + justify + signature layout
    
    รองรับ class ที่ทุกฟอร์มใช้ร่วมกัน:
        .page          — A4 container พร้อม padding
        .doc-number    — เลขที่หนังสือ (บนซ้าย)
        .title         — ชื่อหนังสือ (กลาง, bold)
        .written-at    — ทำที่/วันที่ (ขวา)
        .subject-line  — เรื่อง/เรียน (flex)
        .para          — เนื้อหา (justify, indent)
        .closing-area  — ขอแสดงความนับถือ (ขวา)
        .sig-block     — ลายเซ็น (กลาง)
        .sig-col       — ลายเซ็นแบบ column (มอบอำนาจ)
        .sig-right     — ลายเซ็นแต่ละบรรทัด
    """
    if fonts is None:
        fonts = font_b64()
    
    reg  = fonts.get('THSarabunNew.ttf', '')
    bold = fonts.get('THSarabunNew-Bold.ttf', '')
    ff   = ''
    if reg:
        ff += f"""
        @font-face {{
            font-family: 'THSarabunNew';
            font-weight: normal;
            src: url('data:font/truetype;base64,{reg}') format('truetype');
        }}"""
    if bold:
        ff += f"""
        @font-face {{
            font-family: 'THSarabunNew';
            font-weight: bold;
            src: url('data:font/truetype;base64,{bold}') format('truetype');
        }}"""
    
    return f"""
    {ff}
    @page {{ size: A4; margin: 0; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
        font-family: 'THSarabunNew', 'TH Sarabun New', serif;
        font-size: 10pt;
        color: #000;
        background: transparent;
    }}
    .page {{
        width: 210mm;
        min-height: 297mm;
        padding: 32mm 20mm 25mm 25mm;
    }}
    /* ── หัวหนังสือ ── */
    .doc-number  {{ font-size: 10pt; margin-bottom: 6mm; }}
    .title       {{ font-size: 12pt; font-weight: bold; text-align: center; margin-bottom: 8mm; }}
    .written-at  {{ font-size: 10pt; text-align: right; margin-bottom: 6mm; line-height: 1.6; }}
    /* ── เรื่อง/เรียน ── */
    .subject-line  {{ display: flex; margin-bottom: 4mm; }}
    .subject-label {{ font-weight: bold; min-width: 18mm; flex-shrink: 0; }}
    .subject-value {{ flex: 1; }}
    /* ── ย่อหน้า ── */
    .para {{
        font-size: 10pt;
        text-align: justify;
        text-indent: 12mm;
        line-height: 1.6;
        margin-bottom: 4mm;
    }}
    /* ── ลายเซ็น (ขอถอน — ขวา) ── */
    .closing-area {{
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        margin-top: 8mm;
    }}
    .closing     {{ font-size: 10pt; margin-bottom: 4mm; text-align: center; width: 75mm; }}
    .sig-block   {{ text-align: center; width: 75mm; }}
    .sig-space   {{ height: 18mm; }}
    .sig-line    {{
        border-top: 0.5pt solid #000;
        width: 75mm;
        margin: 0 auto 2mm auto;
        padding-top: 2mm;
        font-size: 10pt;
    }}
    .sig-name    {{ font-size: 10pt; margin-bottom: 1mm; }}
    .sig-pos     {{ font-size: 10pt; }}
    /* ── ลายเซ็น (มอบอำนาจ — column ขวา) ── */
    .sig-col {{
        width: 50%;
        margin-left: auto;
        margin-top: 8mm;
    }}
    .sig-right {{
        margin-bottom: 6mm;
        width: 100%;
    }}
    .sig-right .sig-space {{ height: 10mm; }}
    .sig-right .sig-row1 {{
        display: flex;
        align-items: flex-end;
        width: 100%;
    }}
    .sig-right .sig-row1 .prefix {{
        font-size: 10pt;
        white-space: nowrap;
        flex-shrink: 0;
        padding-bottom: 0.5mm;
        padding-right: 1mm;
    }}
    .sig-right .sig-row1 .line-cell {{
        flex: 1;
        border-bottom: 0.5pt solid #000;
        height: 5mm;
        min-width: 0;
    }}
    .sig-right .sig-row1 .lbl {{
        font-size: 9pt;
        white-space: nowrap;
        flex-shrink: 0;
        flex-basis: 22mm;
        width: 22mm;
        text-align: left;
        padding-bottom: 0.5mm;
        padding-left: 1mm;
    }}
    .sig-right .sig-name {{
        font-size: 10pt;
        margin-top: 1mm;
        text-align: center;
        padding-left: 12mm;
        padding-right: 23mm;
    }}
    /* ── อื่นๆ ── */
    .stamp  {{ font-size: 9pt; color: #666; margin-top: 6mm; }}
    .clearfix {{ clear: both; }}
    """


# ══════════════════════════════════════════════════════════════════════
# HTML → PDF (WeasyPrint)
# ══════════════════════════════════════════════════════════════════════

def html_to_pdf(html):
    """แปลง HTML string → PDF bytes ด้วย WeasyPrint"""
    from weasyprint import HTML
    return HTML(string=html).write_pdf()


def build_html(css, body_html):
    """สร้าง full HTML document จาก CSS + body content
    ตัวอย่าง:
        css = build_css()
        body = '<div class="page"><div class="title">ทดสอบ</div></div>'
        html = build_html(css, body)
        pdf  = html_to_pdf(html)
    """
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{css}</style></head>
<body>{body_html}</body></html>"""


# ══════════════════════════════════════════════════════════════════════
# ENTITY TEMPLATE MAPPING
# ══════════════════════════════════════════════════════════════════════

# แต่ละ entity มี template PDF แยก (logo + watermark + header/footer)
# ชื่อไฟล์: bg_template_{key}.pdf — วางที่ root ของ repo
# Fallback: bg_template.pdf (SCM Tech เดิม)

_ENTITY_TEMPLATE_MAP = {
    # SCM Technologies (หลัก)
    'scm tech':     'bg_template_scmtech.pdf',
    'scmtech':      'bg_template_scmtech.pdf',
    'scm t':        'bg_template_scmtech.pdf',
    # SCM S
    'scm s':        'bg_template_scms.pdf',
    'scms':         'bg_template_scms.pdf',
    # SCM C
    'scm c':        'bg_template_scmc.pdf',
    'scmc':         'bg_template_scmc.pdf',
    # SCM Cyber
    'cyber':        'bg_template_cyber.pdf',
    'scm cyber':    'bg_template_cyber.pdf',
    # SCM Business Connect
    'bc':           'bg_template_bc.pdf',
    'scm bc':       'bg_template_bc.pdf',
    'business connect': 'bg_template_bc.pdf',
    'scm business connect': 'bg_template_bc.pdf',
    # SCM B2B
    'b2b':          'bg_template_b2b.pdf',
    'scm b2b':      'bg_template_b2b.pdf',
    # SCM Group / Holding
    'group':        'bg_template_group.pdf',
    'scm group':    'bg_template_group.pdf',
    'holding':      'bg_template_group.pdf',
    'scm holding':  'bg_template_group.pdf',
    # Fahcloud — ใช้ SCM Tech เป็น fallback (ยังไม่มี template เฉพาะ)
    'fahcloud':     'bg_template_scmtech.pdf',
}

_DEFAULT_TEMPLATE = 'bg_template.pdf'


def resolve_template(entity_key):
    """แปลง entity key → template filename
    รองรับ: 'SCM Tech', 'scmtech', 'SCM C', 'cyber' ฯลฯ (case-insensitive)
    Fallback: bg_template.pdf
    """
    key = str(entity_key or '').lower().strip()
    return _ENTITY_TEMPLATE_MAP.get(key, _DEFAULT_TEMPLATE)


def merge_on_template(content_bytes, entity_key=''):
    """overlay content PDF บน entity template
    
    Args:
        content_bytes: PDF bytes ที่ WeasyPrint สร้าง (เนื้อหาหนังสือ)
        entity_key: sheet name หรือ entity key (เช่น 'SCM Tech', 'SCM C')
    
    Returns:
        PDF bytes ที่ merge แล้ว (template + content overlay)
    
    Fallback: ถ้า template ไม่พบ → ใช้ bg_template.pdf เดิม
    """
    base     = os.path.dirname(os.path.abspath(__file__))
    tpl_name = resolve_template(entity_key)
    tpl_path = os.path.join(base, tpl_name)
    
    # fallback ถ้าไฟล์ไม่พบ
    if not os.path.exists(tpl_path):
        logger.warning(f'Template ไม่พบ: {tpl_name} — ใช้ {_DEFAULT_TEMPLATE} แทน')
        tpl_path = os.path.join(base, _DEFAULT_TEMPLATE)
    
    if not os.path.exists(tpl_path):
        logger.error(f'Default template ไม่พบ: {tpl_path}')
        return content_bytes  # คืน content เดิมไม่มี template
    
    reader = PdfReader(tpl_path)
    page   = reader.pages[0]
    page.merge_page(PdfReader(BytesIO(content_bytes)).pages[0])
    writer = PdfWriter()
    writer.add_page(page)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


# ══════════════════════════════════════════════════════════════════════
# HELPER: สร้าง signature HTML
# ══════════════════════════════════════════════════════════════════════

def sig_closing(signer_name, signer_position='Corporate Lawyers'):
    """สร้าง HTML ลายเซ็นแบบ 'ขอแสดงความนับถือ' (หนังสือขอถอน)"""
    return f"""<div class="closing-area">
    <div class="closing">ขอแสดงความนับถือ</div>
    <div class="sig-block">
      <div class="sig-space"></div>
      <div class="sig-line"></div>
      <div class="sig-name">({signer_name})</div>
      <div class="sig-pos">{signer_position}</div>
    </div>
  </div>"""


def sig_poa_line(label, name):
    """สร้าง HTML ลายเซ็นแบบ 'ลงชื่อ...ผู้มอบอำนาจ' (หนังสือมอบอำนาจ)"""
    return f"""<div class="sig-right">
      <div class="sig-space"></div>
      <div class="sig-row1">
        <span class="prefix">ลงชื่อ</span>
        <span class="line-cell"></span>
        <span class="lbl">{label}</span>
      </div>
      <div class="sig-name">({name})</div>
    </div>"""
