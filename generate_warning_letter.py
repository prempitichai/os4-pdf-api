#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: v2-s11
"""
generate_warning_letter.py — หนังสือตักเตือนพนักงาน (Warning Letter)
═══════════════════════════════════════════════════════════════════
ใช้ template_utils (WeasyPrint + entity template overlay) — 2 หน้า

★ S11 changes:
  [6] companySignerName2 — กรรมการลงนามคนที่ 2 (ถ้ามี)
  [7] employeeSignerName — ชื่อพนักงานแสดงในช่องลายเซ็น
  sig grid: 3 แถว (พนักงาน|นายจ้าง1, นายจ้าง2 ถ้ามี, พยาน1|พยาน2)
"""

import base64
import logging
from flask import request, jsonify
from template_utils import (
    merge_on_template, html_to_pdf, build_css, build_html,
    font_b64
)

logger = logging.getLogger(__name__)


def _esc(s):
    return (str(s or '')
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def _chk(checked):
    """สร้าง checkbox HTML — ☒ หรือ ☐"""
    return '☒' if checked else '☐'


def _build_warning_css():
    """CSS เพิ่มเติมสำหรับหนังสือตักเตือน (นอกเหนือจาก build_css)"""
    return """
    /* ── Warning Letter specific ── */
    .wl-header { font-size: 9pt; color: #555; margin-bottom: 4mm; line-height: 1.5; }
    .wl-title { font-size: 13pt; font-weight: bold; text-align: center; margin-bottom: 6mm; text-decoration: underline; }
    .wl-indent { text-indent: 12mm; }
    .wl-field-row { display: flex; gap: 2mm; margin-bottom: 2mm; font-size: 10pt; line-height: 1.6; }
    .wl-field-label { font-weight: bold; white-space: nowrap; }
    .wl-field-value { border-bottom: 0.5pt dotted #999; flex: 1; min-width: 20mm; }
    .wl-section-title { font-weight: bold; font-size: 10pt; margin-top: 4mm; margin-bottom: 2mm; text-decoration: underline; }
    .wl-body { font-size: 10pt; text-align: justify; line-height: 1.7; margin-bottom: 4mm; border: 0.5pt solid #bbb; padding: 3mm 4mm; min-height: 40mm; }
    .wl-checkbox-row { display: flex; align-items: center; gap: 3mm; font-size: 10pt; margin-bottom: 2mm; margin-left: 20mm; }
    .wl-checkbox { font-size: 12pt; }
    .wl-notice { font-size: 10pt; text-align: justify; line-height: 1.7; text-indent: 12mm; margin-bottom: 4mm; }
    .wl-note { font-size: 9pt; text-align: justify; line-height: 1.6; margin-bottom: 3mm; }
    .wl-note-title { font-weight: bold; }
    /* ── ลายเซ็น — flex row (2 ช่อง/แถว) ── */
    .wl-sig-row { display: flex; justify-content: space-between; margin-bottom: 4mm; }
    .wl-sig-row-right { display: flex; justify-content: flex-end; margin-bottom: 4mm; }
    .wl-sig-box { width: 48%; text-align: center; font-size: 10pt; }
    .wl-sig-line { border-bottom: 0.5pt solid #000; width: 60mm; margin: 0 auto 2mm auto; height: 12mm; }
    .wl-sig-label { font-size: 9pt; margin-bottom: 1mm; }
    .wl-sig-name { font-size: 10pt; }
    """


def _build_sig_html(data):
    """★ S11: สร้าง signature section — รองรับกรรมการ 2 + ชื่อพนักงานใน sig"""
    e = _esc
    emp_signer  = e(data.get('employeeSignerName', data.get('employeeName', '')))
    co_signer   = e(data.get('companySignerName', ''))
    co_signer2  = e(data.get('companySignerName2', ''))
    witness1    = e(data.get('witness1Name', ''))
    witness2    = e(data.get('witness2Name', ''))

    def _box(label, name):
        name_display = f'({name})' if name else '(..............................................)'
        return f'''<div class="wl-sig-box">
      <div style="font-size:9pt;margin-bottom:1mm">ลงชื่อ</div>
      <div class="wl-sig-line"></div>
      <div class="wl-sig-label">{label}</div>
      <div class="wl-sig-name">{name_display}</div>
    </div>'''

    html = '<div style="margin-top:10mm">'

    # แถว 1: พนักงาน | นายจ้าง/กรรมการ 1
    html += '<div class="wl-sig-row">'
    html += _box('พนักงาน', emp_signer)
    html += _box('นายจ้าง/บริษัท', co_signer)
    html += '</div>'

    # แถว 2: กรรมการ 2 (ถ้ามี) — แสดงฝั่งขวาเท่านั้น
    if co_signer2:
        html += '<div class="wl-sig-row-right">'
        html += _box('นายจ้าง/บริษัท (คนที่ 2)', co_signer2)
        html += '</div>'

    # แถว 3: พยาน 1 | พยาน 2
    html += '<div class="wl-sig-row">'
    html += _box('พยาน', witness1)
    html += _box('พยาน', witness2)
    html += '</div>'

    html += '</div>'
    return html


def _build_warning_html(data):
    """สร้าง HTML หนังสือตักเตือน 2 หน้า"""
    e = _esc

    doc_number  = e(data.get('docNumber', ''))
    doc_date    = e(data.get('docDate', ''))
    company     = e(data.get('companyName', 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด'))
    company_addr = e(data.get('companyAddress', ''))
    emp_name    = e(data.get('employeeName', ''))
    emp_id      = e(data.get('employeeIdCard', ''))
    emp_code    = e(data.get('employeeCode', ''))
    emp_pos     = e(data.get('employeePosition', ''))
    emp_dept    = e(data.get('employeeDepartment', ''))
    incident_date = e(data.get('incidentDate', ''))

    # เนื้อหาพฤติการณ์ — แบ่งย่อหน้า
    body_raw = str(data.get('violationDetails', '') or '').strip()
    if body_raw:
        body_paras = [p.strip() for p in body_raw.split('\n') if p.strip()]
    else:
        body_paras = ['(กรุณาระบุพฤติการณ์การกระทำผิด)']
    body_html = '\n'.join(f'<p style="margin:0 0 2mm 0;text-indent:12mm">{e(p)}</p>' for p in body_paras)

    punishment = data.get('punishmentType', 'written')
    notif_method = data.get('notificationMethod', 'read_aloud')

    css = build_css() + _build_warning_css()

    # ★ S11: สร้าง sig HTML จาก _build_sig_html
    sig_html = _build_sig_html(data)

    # ════════════════════════════════════════════
    # หน้า 1
    # ════════════════════════════════════════════
    page1 = f"""<div class="page">
  <div class="doc-number">{doc_number}</div>
  <div class="wl-title">หนังสือตักเตือนพนักงาน</div>

  <p class="wl-notice">หนังสือฉบับนี้ทำขึ้นเมื่อวันที่ {doc_date} ระหว่าง {company} {company_addr}</p>

  <div class="wl-field-row">
    <span class="wl-field-label">นาย / นาง / นางสาว</span>
    <span class="wl-field-value">{emp_name}</span>
    <span class="wl-field-label">เลขประจำตัวประชาชน</span>
    <span class="wl-field-value">{emp_id}</span>
  </div>
  <div class="wl-field-row">
    <span class="wl-field-label">รหัสพนักงาน</span>
    <span class="wl-field-value">{emp_code}</span>
    <span class="wl-field-label">ตำแหน่ง</span>
    <span class="wl-field-value">{emp_pos}</span>
    <span class="wl-field-label">แผนก</span>
    <span class="wl-field-value">{emp_dept}</span>
  </div>

  <p class="wl-section-title">พฤติการณ์การกระทำผิดที่เกิดขึ้น เมื่อวันที่ {incident_date}</p>
  <div class="wl-body">
    {body_html}
  </div>

  <p class="wl-notice">ดังนั้นการกระทำของท่านถือว่าไม่สอดคล้องกับระเบียบและข้อบังคับเกี่ยวกับการทำงานของบริษัท จึงถือเป็นการกระทำความผิดต่อบริษัทและทำให้บริษัทได้รับความเสียหายจากการกระทำของท่าน</p>

  <p class="wl-section-title">การลงโทษในครั้งนี้</p>
  <div class="wl-checkbox-row"><span class="wl-checkbox">{_chk(punishment == 'verbal')}</span> ตักเตือนด้วยวาจา</div>
  <div class="wl-checkbox-row"><span class="wl-checkbox">{_chk(punishment == 'written')}</span> ตักเตือนเป็นลายลักษณ์อักษร</div>
  <div class="wl-checkbox-row"><span class="wl-checkbox">{_chk(punishment == 'suspension')}</span> พักงานโดยไม่ได้รับค่าจ้างและตักเตือนเป็นลายลักษณ์อักษร</div>

  <p class="wl-notice">ขอตักเตือนผู้กระทำความผิดโดยห้ามมิให้กระทำความผิดเดิมซ้ำอีกมิฉะนั้นจะลงโทษในสถานหนักต่อไป แต่หากได้ลงโทษผู้กระทำความผิดโดยตักเตือนเป็นลายลักษณ์อักษรหรือพักงานโดยไม่ได้รับค่าจ้างและตักเตือนเป็นลายลักษณ์อักษรในครั้งนี้แล้ว ถ้าได้กระทำความผิดเดิมซ้ำอีกในคราวต่อไป <b>ภายในระยะเวลา 1 (หนึ่ง) ปี</b>นับแต่วันที่กระทำความผิดครั้งนี้ ผู้กระทำความผิดจะต้องถูกลงโทษด้วยการเลิกจ้างโดยไม่จ่ายค่าชดเชยใด ๆ ทั้งสิ้น เว้นแต่มีเหตุให้บรรเทาโทษซึ่งอาจจะลดโทษให้ได้ตามสมควร</p>
</div>"""

    # ════════════════════════════════════════════
    # หน้า 2
    # ════════════════════════════════════════════
    page2 = f"""<div class="page">
  <div class="doc-number">{doc_number}</div>

  <p class="wl-note"><span class="wl-note-title">หมายเหตุ</span> ในกรณีที่พนักงานที่ถูกลงโทษไม่ยินยอมลงนามในหนังสือตักเตือนดังกล่าวข้างต้นศาลฎีกาแผนกคดีแรงงานได้เคยวินิจฉัยว่าหากนายจ้างได้แจ้งพนักงานที่ถูกลงโทษโดยชอบด้วยกฎหมายแล้วให้ถือว่าหนังสือตักเตือนมีผลสมบูรณ์</p>

  <p class="wl-note">— หากพนักงานไม่รับหนังสือเตือน บริษัทจะจัดส่งหนังสือเตือนไปยังภูมิลำเนา และ/หรือ อีเมลและ/หรือ ไลน์แจ้งหนังสือเตือน และให้ถือว่าท่านรับหนังสือเตือนดังกล่าวโดยชอบแล้ว</p>

  <p class="wl-section-title">วิธีการแจ้ง</p>
  <p style="font-size:10pt;margin-bottom:2mm">ด้วยวิธีใดวิธีหนึ่ง ดังต่อไปนี้</p>
  <div class="wl-checkbox-row"><span class="wl-checkbox">{_chk(notif_method == 'posted')}</span> ติดประกาศให้ทราบในสถานประกอบการ</div>
  <div class="wl-checkbox-row"><span class="wl-checkbox">{_chk(notif_method == 'read_aloud')}</span> อ่านให้ผู้กระทำความผิดทราบ โดยมีพยานรับรู้การลงโทษในครั้งนี้และลงนามเป็นพยานอย่างน้อย 2 คน</div>
  <div class="wl-checkbox-row"><span class="wl-checkbox">{_chk(notif_method == 'mail')}</span> ส่งไปรษณีย์ลงทะเบียนตามที่อยู่ที่ติดต่อได้</div>

  {sig_html}
</div>"""

    return build_html(css, page1 + page2)


def _merge_multi_page(content_bytes, entity_key):
    """Overlay ทุกหน้าของ content บน entity template (ไม่ใช่แค่หน้าแรก)"""
    from io import BytesIO
    from pypdf import PdfReader, PdfWriter
    from template_utils import resolve_template
    import os

    base = os.path.dirname(os.path.abspath(__file__))
    tpl_name = resolve_template(entity_key)
    tpl_path = os.path.join(base, tpl_name)

    if not os.path.exists(tpl_path):
        tpl_path = os.path.join(base, 'bg_template_scmtech.pdf')
    if not os.path.exists(tpl_path):
        return content_bytes

    tpl_reader = PdfReader(tpl_path)
    tpl_page   = tpl_reader.pages[0]
    content_reader = PdfReader(BytesIO(content_bytes))
    writer = PdfWriter()

    for page in content_reader.pages:
        from copy import deepcopy
        bg = deepcopy(tpl_page)
        bg.merge_page(page)
        writer.add_page(bg)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()


# ══════════════════════════════════════════════════════════════════════
# FLASK ROUTE
# ══════════════════════════════════════════════════════════════════════

def register_warning_letter_routes(app):
    @app.route('/generate_warning_letter', methods=['POST'])
    def api_generate_warning_letter():
        try:
            from app import _check_key, _safe_error
            err = _check_key()
            if err:
                return err

            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'No JSON body'}), 400

            html = _build_warning_html(data)
            content_bytes = html_to_pdf(html)

            entity_key = data.get('entityKey', '')
            pdf_bytes = _merge_multi_page(content_bytes, entity_key)
            pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

            emp = (data.get('employeeName', '') or 'warning')[:30]
            safe_name = ''.join(
                ch for ch in emp
                if ch.isalnum() or ch in '_- ' or '\u0e00' <= ch <= '\u0e7f'
            ).strip() or 'warning'

            return jsonify({
                'success': True,
                'pdfBase64': pdf_b64,
                'fileName': f'หนังสือตักเตือน_{safe_name}.pdf',
            })
        except Exception as e:
            logger.error(f'generate_warning_letter error: {e}')
            from app import _safe_error
            return jsonify(_safe_error(e, 'generate_warning_letter')), 500
