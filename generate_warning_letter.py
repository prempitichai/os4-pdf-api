#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: v3-s12
"""
generate_warning_letter.py — หนังสือตักเตือนพนักงาน (Warning Letter)
═══════════════════════════════════════════════════════════════════
ใช้ template_utils (WeasyPrint + entity template overlay)

★ S12 v3 changes (จากต้นฉบับ SCMCB.docx):
  - Single page flow → ให้ WeasyPrint ตัดหน้าเอง (ไม่ hardcode 2 page)
  - เนื้อหาทั้งหมดอยู่ใน flow เดียว (เหมือนต้นฉบับ)
  - ลายเซ็น 3 แถว:
    แถว 1: กรรมการ/นายจ้าง 1 | กรรมการ/นายจ้าง 2 (ถ้ามี)
    แถว 2: พนักงาน | หัวหน้างาน
    แถว 3: พยาน 1 | พยาน 2
  - กรอบพฤติการณ์มี border
  - checkbox ใช้ ☒/☐
  - หมายเหตุ + วิธีแจ้ง อยู่ต่อจากข้อความตักเตือน (ไม่แยกหน้า)
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
    """CSS สำหรับหนังสือตักเตือน — ตรงกับต้นฉบับ"""
    return """
    /* ── Warning Letter v3 — single flow ── */
    .wl-title { font-size: 14pt; font-weight: bold; text-align: center;
                margin: 4mm 0 6mm; text-decoration: underline; }
    .wl-intro { font-size: 10.5pt; text-align: justify; line-height: 1.7;
                text-indent: 12mm; margin-bottom: 3mm; }
    .wl-field-row { display: flex; gap: 2mm; margin-bottom: 2mm;
                    font-size: 10.5pt; line-height: 1.6; flex-wrap: wrap; }
    .wl-field-label { font-weight: bold; white-space: nowrap; }
    .wl-field-value { border-bottom: 0.5pt dotted #999; flex: 1; min-width: 20mm; }
    .wl-section-title { font-weight: bold; font-size: 10.5pt;
                        margin-top: 5mm; margin-bottom: 2mm; text-decoration: underline; }
    .wl-body { font-size: 10.5pt; text-align: justify; line-height: 1.7;
               margin-bottom: 4mm; border: 0.5pt solid #999;
               padding: 3mm 4mm; min-height: 30mm; }
    .wl-body p { margin: 0 0 2mm 0; text-indent: 12mm; }
    .wl-notice { font-size: 10.5pt; text-align: justify; line-height: 1.7;
                 text-indent: 12mm; margin-bottom: 3mm; }
    .wl-note { font-size: 9.5pt; text-align: justify; line-height: 1.6;
               margin-bottom: 3mm; }
    .wl-note-title { font-weight: bold; text-decoration: underline; }
    .wl-checkbox-row { display: flex; align-items: flex-start; gap: 3mm;
                       font-size: 10.5pt; margin-bottom: 2mm; margin-left: 20mm; }
    .wl-checkbox { font-size: 13pt; line-height: 1; }
    /* ── ลายเซ็น grid — 2 ช่อง/แถว ── */
    .wl-sig-grid { margin-top: 10mm; }
    .wl-sig-row { display: flex; justify-content: space-between;
                  margin-bottom: 6mm; }
    .wl-sig-box { width: 48%; text-align: center; font-size: 10pt; }
    .wl-sig-dots { border-bottom: 0.5pt dotted #333;
                   width: 55mm; margin: 0 auto 1mm auto; height: 10mm; }
    .wl-sig-label { font-size: 9.5pt; margin-bottom: 1mm; }
    .wl-sig-name { font-size: 10pt; }
    """


def _build_sig_html(data):
    """ลายเซ็น 3 แถว ตามต้นฉบับ:
    แถว 1: กรรมการ/นายจ้าง 1 | กรรมการ/นายจ้าง 2 (ถ้ามี, ไม่มีก็ว่าง)
    แถว 2: พนักงาน | หัวหน้างาน
    แถว 3: พยาน 1 | พยาน 2
    """
    e = _esc
    co_signer1  = e(data.get('companySignerName', ''))
    co_signer2  = e(data.get('companySignerName2', ''))
    emp_signer  = e(data.get('employeeSignerName', data.get('employeeName', '')))
    supervisor  = e(data.get('supervisorName', ''))
    witness1    = e(data.get('witness1Name', ''))
    witness2    = e(data.get('witness2Name', ''))

    def _box(label, name):
        name_display = f'({name})' if name else '(....................................................................)'
        return f'''<div class="wl-sig-box">
      <div style="font-size:9pt;margin-bottom:1mm">ลงชื่อ</div>
      <div class="wl-sig-dots"></div>
      <div class="wl-sig-label">{label}</div>
      <div class="wl-sig-name">{name_display}</div>
    </div>'''

    def _empty_box():
        return '<div class="wl-sig-box"></div>'

    html = '<div class="wl-sig-grid">'

    # แถว 1: กรรมการ/นายจ้าง 1 | กรรมการ/นายจ้าง 2
    html += '<div class="wl-sig-row">'
    html += _box('นายจ้าง/บริษัท', co_signer1)
    if co_signer2:
        html += _box('นายจ้าง/บริษัท (คนที่ 2)', co_signer2)
    else:
        html += _empty_box()
    html += '</div>'

    # แถว 2: พนักงาน | หัวหน้างาน
    html += '<div class="wl-sig-row">'
    html += _box('พนักงาน', emp_signer)
    html += _box('หัวหน้างาน', supervisor)
    html += '</div>'

    # แถว 3: พยาน 1 | พยาน 2
    html += '<div class="wl-sig-row">'
    html += _box('พยาน', witness1)
    html += _box('พยาน', witness2)
    html += '</div>'

    html += '</div>'
    return html


def _build_warning_html(data):
    """สร้าง HTML หนังสือตักเตือน — single flow ตามต้นฉบับ"""
    e = _esc

    doc_number    = e(data.get('docNumber', ''))
    doc_date      = e(data.get('docDate', ''))
    doc_month     = e(data.get('docMonth', ''))
    doc_year      = e(data.get('docYear', ''))
    company       = e(data.get('companyName', ''))
    company_addr  = e(data.get('companyAddress', ''))
    emp_name      = e(data.get('employeeName', ''))
    emp_id        = e(data.get('employeeIdCard', ''))
    emp_code      = e(data.get('employeeCode', ''))
    emp_pos       = e(data.get('employeePosition', ''))
    emp_dept      = e(data.get('employeeDepartment', ''))
    incident_date = e(data.get('incidentDate', ''))

    # วันที่: รองรับทั้ง docDate เป็น string เดียว หรือแยก date/month/year
    if doc_date and not doc_month:
        date_text = doc_date
    else:
        date_text = f"{doc_date} เดือน {doc_month} พ.ศ. {doc_year}"

    # เนื้อหาพฤติการณ์
    body_raw = str(data.get('violationDetails', '') or '').strip()
    if body_raw:
        body_paras = [p.strip() for p in body_raw.split('\n') if p.strip()]
    else:
        body_paras = ['']
    body_html = '\n'.join(f'<p>{e(p)}</p>' for p in body_paras)

    punishment   = data.get('punishmentType', 'written')
    notif_method = data.get('notificationMethod', 'read_aloud')

    css = build_css() + _build_warning_css()
    sig_html = _build_sig_html(data)

    # ════════════════════════════════════════════
    # Single flow — ไม่แยก page div
    # ════════════════════════════════════════════
    content = f"""<div class="page">
  <div class="doc-number">{doc_number}</div>
  <div class="wl-title">หนังสือตักเตือนพนักงาน</div>

  <p class="wl-intro">หนังสือฉบับนี้ทำขึ้นเมื่อวันที่ {date_text} ระหว่าง {company} {company_addr}</p>

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

  <p class="wl-notice" style="margin-top:4mm"><b>ขอตักเตือน</b>ผู้กระทำความผิดโดยห้ามมิให้กระทำความผิดเดิมซ้ำอีกมิฉะนั้นจะลงโทษในสถานหนักต่อไป แต่หากได้ลงโทษผู้กระทำความผิดโดยตักเตือนเป็นลายลักษณ์อักษรหรือพักงานโดยไม่ได้รับค่าจ้างและตักเตือนเป็นลายลักษณ์อักษรในครั้งนี้แล้ว ถ้าได้กระทำความผิดเดิมซ้ำอีกในคราวต่อไป <b>ภายในระยะเวลา 1 (หนึ่ง) ปี</b> นับแต่วันที่กระทำความผิดครั้งนี้ ผู้กระทำความผิดจะต้องถูกลงโทษด้วยการเลิกจ้างโดยไม่จ่ายค่าชดเชยใด ๆ ทั้งสิ้น เว้นแต่มีเหตุให้บรรเทาโทษซึ่งอาจจะลดโทษให้ได้ตามสมควร</p>

  <p class="wl-note"><span class="wl-note-title">หมายเหตุ</span> ในกรณีที่พนักงานที่ถูกลงโทษไม่ยินยอมลงนามในหนังสือตักเตือนดังกล่าวข้างต้นศาลฎีกาแผนกคดีแรงงานได้เคยวินิจฉัยว่าหากนายจ้างได้แจ้งพนักงานที่ถูกลงโทษโดยชอบด้วยกฎหมายแล้วให้ถือว่าหนังสือตักเตือนมีผลสมบูรณ์</p>

  <p class="wl-note">หากพนักงานไม่รับหนังสือเตือน บริษัทจะจัดส่งหนังสือเตือนไปยังภูมิลำเนา และ/หรือ อีเมล และ/หรือ ไลน์แจ้งหนังสือเตือน และให้ถือว่าท่านรับหนังสือเตือนดังกล่าวโดยชอบแล้ว</p>

  <p class="wl-section-title">วิธีการแจ้ง</p>
  <p style="font-size:10.5pt;margin-bottom:2mm">ด้วยวิธีใดวิธีหนึ่ง ดังต่อไปนี้</p>
  <div class="wl-checkbox-row"><span class="wl-checkbox">{_chk(notif_method == 'posted')}</span> ติดประกาศให้ทราบในสถานประกอบการ</div>
  <div class="wl-checkbox-row"><span class="wl-checkbox">{_chk(notif_method == 'read_aloud')}</span> อ่านให้ผู้กระทำความผิดทราบ โดยมีพยานรับรู้การลงโทษในครั้งนี้และลงนามเป็นพยานอย่างน้อย 2 คน</div>
  <div class="wl-checkbox-row"><span class="wl-checkbox">{_chk(notif_method == 'mail')}</span> ส่งไปรษณีย์ลงทะเบียนตามที่อยู่ที่ติดต่อได้</div>

  {sig_html}
</div>"""

    return build_html(css, content)


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
