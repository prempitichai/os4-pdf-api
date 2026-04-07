#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: v1
"""
generate_request_doc.py — Request Company Document PDF
═══════════════════════════════════════════════════════
ใช้ template_utils shared module (WeasyPrint + entity template overlay)

POST /generate_request_doc
  Input: { entityKey, contractName, company, contractId, deadline,
           documents: [{name, copies}], additional, selectedCompany }
  Output: { success, pdfBase64, fileName }
"""

import base64
import logging
from datetime import datetime
from flask import request, jsonify
from template_utils import (
    merge_on_template, html_to_pdf, build_css, build_html,
    fmt, fmt_date_th, font_b64
)

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# COMPANY LIST — รายชื่อบริษัทสำหรับ checkbox
# ══════════════════════════════════════════════════════════════════════
_LEFT_COMPANIES = [
    'S C M Technologies Co., Ltd.',
    'SCM S Technologies Co., Ltd.',
    'SCM C Technologies Co., Ltd.',
    'SCM Holding Co., Ltd.',
    'SCM B2B Co., Ltd.',
]
_RIGHT_COMPANIES = [
    'SCM Business Connect Co., Ltd.',
    'SCM Cyber Co., Ltd.',
    'Fahcloud Co., Ltd.',
]

# ══════════════════════════════════════════════════════════════════════
# DOCUMENT LIST — รายการเอกสารที่ขอได้
# ══════════════════════════════════════════════════════════════════════
_ALL_DOCUMENTS = [
    'หนังสือรับรองบริษัท', 'ภ.พ.20',
    'หนังสือบริคณห์สนธิ (บอจ.2)', 'รายการจดทะเบียนจัดตั้ง (บอจ.3)',
    'รายการจดทะเบียนแก้ไขเพิ่มเติม (บอจ.4)', 'Statement',
    'งบการเงิน', 'Book bank',
    'ใบทะเบียนพาณิชย์', 'ใบเสร็จ ภ.พ.30',
    'ภ.พ.30', 'SME-GP Register',
    'บัญชีรายชื่อผู้ถือหุ้นรายใหญ่ (บอจ.5)', 'ตัวอย่างตราบริษัท',
    'บัญชีรายชื่อกรรมการผู้จัดการ', 'ภาษีซื้อ',
    'EG-P Register', 'ภาษีขาย',
    'แผนที่บริษัท', 'backlog งานทั้งหมด (Work on Hand)',
    'company profile', 'งบการเงินภายใน หรือ P&L Budget',
    'หนังสือมอบอำนาจ', 'สำเนาทะเบียนบ้าน',
    'สำเนาบัตรประชาชนกรรมการบริหาร', 'สำเนาบัตรประชาชน',
    'ISO Certificate',
]

# ══════════════════════════════════════════════════════════════════════
# ENTITY → COMPANY NAME mapping (auto-detect)
# ══════════════════════════════════════════════════════════════════════
_ENTITY_TO_COMPANY = {
    'scmtech':  'S C M Technologies Co., Ltd.',
    'scm t':    'S C M Technologies Co., Ltd.',
    'scms':     'SCM S Technologies Co., Ltd.',
    'scm s':    'SCM S Technologies Co., Ltd.',
    'scmc':     'SCM C Technologies Co., Ltd.',
    'scm c':    'SCM C Technologies Co., Ltd.',
    'holding':  'SCM Holding Co., Ltd.',
    'b2b':      'SCM B2B Co., Ltd.',
    'bc':       'SCM Business Connect Co., Ltd.',
    'cyber':    'SCM Cyber Co., Ltd.',
    'fahcloud': 'Fahcloud Co., Ltd.',
}


def _resolve_company(entity_key, selected=''):
    """แปลง entity key → ชื่อบริษัท English"""
    if selected:
        return selected
    key = str(entity_key or '').lower().strip()
    return _ENTITY_TO_COMPANY.get(key, 'S C M Technologies Co., Ltd.')


def _today_be():
    """วันที่ปัจจุบัน format dd/mm/yyyy (พ.ศ.)"""
    now = datetime.now()
    return f'{now.day:02d}/{now.month:02d}/{now.year + 543}'


def _esc(s):
    """Escape HTML"""
    return (str(s or '')
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


# ══════════════════════════════════════════════════════════════════════
# BUILD HTML
# ══════════════════════════════════════════════════════════════════════

def _build_request_doc_html(data):
    """สร้าง HTML สำหรับ Request Company Document"""
    entity_key  = str(data.get('entityKey', '') or '')
    selected_co = _resolve_company(entity_key, data.get('selectedCompany', ''))
    
    contract_name = _esc(data.get('contractName', ''))
    company       = _esc(data.get('company', ''))
    contract_id   = _esc(data.get('contractId', ''))
    deadline      = _esc(data.get('deadline', ''))
    additional    = _esc(data.get('additional', ''))
    today         = _today_be()
    
    documents     = data.get('documents', [])
    if not isinstance(documents, list):
        documents = []
    
    # สร้าง set ของเอกสารที่เลือก
    selected_docs = {}
    for doc in documents:
        if isinstance(doc, dict):
            selected_docs[doc.get('name', '')] = doc.get('copies', 1)
        elif isinstance(doc, str):
            selected_docs[doc] = 1

    # ── CSS เฉพาะฟอร์มนี้ ──
    fonts = font_b64()
    reg  = fonts.get('THSarabunNew.ttf', '')
    bold = fonts.get('THSarabunNew-Bold.ttf', '')
    
    css = f"""
        @font-face {{
            font-family: 'THSarabunNew';
            font-weight: normal;
            src: url('data:font/truetype;base64,{reg}') format('truetype');
        }}
        @font-face {{
            font-family: 'THSarabunNew';
            font-weight: bold;
            src: url('data:font/truetype;base64,{bold}') format('truetype');
        }}
        @page {{ size: A4; margin: 20mm 18mm 15mm 18mm; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'THSarabunNew', sans-serif;
            font-size: 11pt;
            color: #1a202c;
            line-height: 1.6;
        }}
        .page {{ position: relative; }}
        
        /* ── Header ── */
        h1 {{
            font-size: 16pt;
            text-align: center;
            text-decoration: underline;
            text-underline-offset: 4px;
            margin: 8mm 0 4mm;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}
        .date-line {{
            text-align: right;
            font-size: 11pt;
            margin-bottom: 5mm;
            color: #4a5568;
        }}
        .date-val {{
            border-bottom: 1px dotted #4a5568;
            padding: 0 3mm 1px;
            min-width: 30mm;
            display: inline-block;
            text-align: center;
            font-weight: 600;
            color: #1a202c;
        }}
        
        /* ── Company grid ── */
        .section-label {{
            font-size: 12pt;
            font-weight: 700;
            margin-bottom: 2mm;
            padding-bottom: 1mm;
            border-bottom: 0.5pt solid #e2e8f0;
            display: inline-block;
        }}
        .company-grid {{
            display: flex;
            gap: 4mm;
            margin-bottom: 5mm;
        }}
        .company-col {{ flex: 1; }}
        .company-item {{
            display: flex;
            align-items: center;
            gap: 2mm;
            font-size: 10pt;
            margin: 1mm 0;
            line-height: 1.5;
        }}
        .cb {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 3.5mm;
            height: 3.5mm;
            border: 0.5pt solid #718096;
            border-radius: 0.5mm;
            font-size: 8pt;
            flex-shrink: 0;
            color: #2b6cb0;
        }}
        .cb-checked {{
            background: #ebf4ff;
            border-color: #2b6cb0;
        }}
        
        /* ── Info block ── */
        .info-block {{
            background: #f7fafc;
            border: 0.5pt solid #e2e8f0;
            border-radius: 2mm;
            padding: 3mm 4mm;
            margin-bottom: 4mm;
        }}
        .info-row {{
            font-size: 11pt;
            margin: 1.5mm 0;
            line-height: 1.8;
            display: flex;
            gap: 1mm;
            flex-wrap: wrap;
        }}
        .info-row strong {{
            white-space: nowrap;
        }}
        .info-row .val {{
            border-bottom: 1px dotted #a0aec0;
            padding: 0 2mm 0.5mm;
            flex: 1;
            min-width: 25mm;
            font-weight: 500;
        }}
        
        /* ── Document table ── */
        .doc-title {{
            font-size: 12pt;
            font-weight: 700;
            text-decoration: underline;
            text-underline-offset: 2px;
            margin-bottom: 3mm;
        }}
        .doc-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 10pt;
        }}
        .doc-table td {{
            border: 0.5pt solid #a0aec0;
            padding: 1mm 2mm;
            vertical-align: middle;
            line-height: 1.4;
        }}
        .doc-table tr:nth-child(even) td {{
            background: #f7fafc;
        }}
        .doc-table .cb-cell {{
            width: 5mm;
            text-align: center;
            padding: 0.5mm;
        }}
        .doc-table .qty-cell {{
            width: 7mm;
            text-align: center;
            font-weight: 700;
            color: #2b6cb0;
        }}
        .doc-table .unit-cell {{
            width: 7mm;
            text-align: center;
            color: #718096;
            font-size: 9pt;
        }}
        
        /* ── Extra / Footer ── */
        .extra {{
            font-size: 10pt;
            margin-top: 4mm;
            padding: 2mm 0;
        }}
        .extra .val {{
            border-bottom: 1px dotted #a0aec0;
            padding: 0 1mm 0.5mm;
            min-width: 70mm;
            display: inline-block;
        }}
        .footer-line {{
            border-top: 1pt solid #2d3748;
            margin-top: 6mm;
            padding-top: 2mm;
            text-align: center;
            font-size: 8pt;
            color: #718096;
            line-height: 1.5;
        }}
    """

    # ── Company checkboxes ──
    def _co_item(name, is_selected):
        cls = 'cb cb-checked' if is_selected else 'cb'
        tick = '✓' if is_selected else '&nbsp;'
        return f'<div class="company-item"><span class="{cls}">{tick}</span> {_esc(name)}</div>'

    left_html = ''.join(_co_item(co, co == selected_co) for co in _LEFT_COMPANIES)
    right_html = ''.join(_co_item(co, co == selected_co) for co in _RIGHT_COMPANIES)

    # ── Document table (2 columns) ──
    half = (len(_ALL_DOCUMENTS) + 1) // 2
    doc_rows = ''
    for i in range(half):
        doc_rows += '<tr>'
        for col_idx in [i, i + half]:
            if col_idx < len(_ALL_DOCUMENTS):
                doc_name = _ALL_DOCUMENTS[col_idx]
                is_sel = doc_name in selected_docs
                copies = selected_docs.get(doc_name, '')
                tick = '✓' if is_sel else '&nbsp;'
                cls = 'cb cb-checked' if is_sel else 'cb'
                doc_rows += f'<td class="cb-cell"><span class="{cls}">{tick}</span></td>'
                doc_rows += f'<td>{_esc(doc_name)}</td>'
                doc_rows += f'<td class="qty-cell">{copies if is_sel else ""}</td>'
                doc_rows += f'<td class="unit-cell">ชุด</td>'
            else:
                doc_rows += '<td colspan="4"></td>'
        doc_rows += '</tr>'

    # ── Build body ──
    body = f"""<div class="page">
    <h1>Request Company Document</h1>
    <div class="date-line">Request date : <span class="date-val">{today}</span></div>
    
    <div class="section-label">Company</div>
    <div class="company-grid">
        <div class="company-col">{left_html}</div>
        <div class="company-col">{right_html}</div>
    </div>
    
    <div class="info-block">
        <div class="info-row"><strong>ใช้สำหรับ</strong> <span class="val">{contract_name or '......'}</span></div>
        <div class="info-row"><strong>กับ</strong> <span class="val">{company or '......'}</span> <strong>เท่านั้น</strong></div>
        <div class="info-row"><strong>ใช้ภายในวันที่</strong> <span class="val" style="flex:none;min-width:30mm">{deadline or '......'}</span></div>
    </div>
    
    <div class="doc-title">รายการเอกสารที่ต้องการ</div>
    <table class="doc-table">
        {doc_rows}
    </table>
    
    <div class="extra"><strong>เพิ่มเติม :</strong> <span class="val">{additional}</span></div>
    
    <div class="footer-line">
        บริษัท เอส ซี เอ็ม เทคโนโลจีส จำกัด (สำนักงานใหญ่) เลขที่ 92/54-55 ชั้น 19 อาคารสาธรธานี 2 ถนน สาทรเหนือ แขวง สีลม<br>
        เขต บางรัก กรุงเทพฯ 10500 โทรศัพท์ : +66 (0) 2 116 4312
    </div>
</div>"""

    return f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>'


# ══════════════════════════════════════════════════════════════════════
# GENERATE PDF
# ══════════════════════════════════════════════════════════════════════

def generate_request_doc_pdf(data):
    """สร้าง Request Company Document PDF
    Returns: PDF bytes
    """
    html = _build_request_doc_html(data)
    content_bytes = html_to_pdf(html)
    
    # overlay บน entity template (logo + watermark)
    entity_key = data.get('entityKey', '')
    if entity_key:
        return merge_on_template(content_bytes, entity_key)
    
    return content_bytes


# ══════════════════════════════════════════════════════════════════════
# FLASK ROUTE REGISTRATION
# ══════════════════════════════════════════════════════════════════════

def register_request_doc_routes(app):
    """ลงทะเบียน route สำหรับ Request Company Document"""

    @app.route('/generate_request_doc', methods=['POST'])
    def api_generate_request_doc():
        try:
            # ★ API key check — ใช้ _check_key จาก app.py (import ผ่าน app context)
            from app import _check_key, _safe_error
            err = _check_key()
            if err:
                return err

            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'No JSON body'}), 400

            pdf_bytes = generate_request_doc_pdf(data)
            pdf_b64   = base64.b64encode(pdf_bytes).decode('utf-8')

            cn = _esc(data.get('contractName', 'doc')).replace(' ', '_')[:40]
            filename = f'Request_Document_{cn}.pdf'

            return jsonify({
                'success':   True,
                'pdfBase64': pdf_b64,
                'fileName':  filename,
            })
        except Exception as e:
            logger.error(f'generate_request_doc error: {e}')
            from app import _safe_error
            return jsonify(_safe_error(e, 'generate_request_doc')), 500
