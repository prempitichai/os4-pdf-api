#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: v4-s12
"""
generate_warning_letter.py — หนังสือตักเตือนพนักงาน (Warning Letter)
═══════════════════════════════════════════════════════════════════
ใช้ template_utils (WeasyPrint + entity template overlay)

★ S12 v4 changes (จากต้นฉบับ SCMCB.docx):
  - Layout เป็น HTML table มีกรอบ border ตรงต้นฉบับ
  - แยก 2 table: หน้า 1 (เนื้อหาหลัก) + หน้า 2 (หมายเหตุ/วิธีแจ้ง/ลายเซ็น)
  - กรอบปิดสมบูรณ์ทั้ง 2 หน้า + เลขที่หนังสือแสดงทั้ง 2 หน้า
  - ลายเซ็น 3 แถว:
    แถว 1: กรรมการ/นายจ้าง 1 | กรรมการ/นายจ้าง 2 (ถ้ามี)
    แถว 2: พนักงาน | หัวหน้างาน
    แถว 3: พยาน 1 | พยาน 2
  - กรอบพฤติการณ์มี border + พื้นหลัง subtle
  - หมายเหตุเป็น note box (border-left สไตล์ blockquote)
  - หัวเรื่องมี background สีอ่อน
  - "ดังนั้น..." มี underline ตรงต้นฉบับ
  - "ขอตักเตือน" ไม่ bold + "ภายในระยะเวลา 1 ปี" bold+underline
  - checkbox ใช้ ☒/☐
  - @page margin override ให้ WeasyPrint ตัดหน้าถูกต้อง
"""

import base64
import logging
from flask import request, jsonify
from template_utils import (
    merge_on_template, html_to_pdf, build_css, build_html,
    font_b64
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════

def _esc(s):
    """Escape HTML special characters"""
    return (str(s or '')
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def _chk(checked):
    """สร้าง checkbox HTML — ☒ หรือ ☐"""
    return '☒' if checked else '☐'


# ══════════════════════════════════════════════════════════════════════
# CSS — table layout ตรงกับต้นฉบับ docx
# ══════════════════════════════════════════════════════════════════════

def _build_warning_css():
    """CSS สำหรับหนังสือตักเตือน — table border layout"""
    return """
    /* ── Override page layout จาก build_css() ── */
    @page { size: A4; margin: 30mm 18mm 20mm 22mm; }
    .page { width: auto; min-height: auto; padding: 0; }

    /* ── Table frame — กรอบหลัก ── */
    .wl-tbl { width: 100%; border-collapse: collapse; border: 1.2pt solid #1a1a1a; }
    .wl-tbl td { border: 0.8pt solid #444; padding: 0; vertical-align: top; }

    /* ── Row 0: หัวเรื่อง (พื้นหลังสีอ่อน) ── */
    .wl-hdr {
        background: #f0f4f8;
        text-align: center;
        padding: 4mm 5mm;
    }
    .wl-hdr-title {
        font-size: 14pt;
        font-weight: bold;
        text-decoration: underline;
        letter-spacing: 0.5pt;
        color: #1a1a1a;
    }

    /* ── Row 1: เนื้อหาหลัก ── */
    .wl-content {
        padding: 5mm 6mm 4mm;
        font-size: 10.5pt;
        line-height: 1.65;
    }

    /* ── Field table (ข้อมูลพนักงาน) ── */
    .wl-fields { width: 100%; border-collapse: collapse; margin-bottom: 3mm; font-size: 10.5pt; }
    .wl-fields td { padding: 1.5mm 2mm; border: none; vertical-align: bottom; }
    .wl-fields .lbl { font-weight: bold; white-space: nowrap; color: #222; }
    .wl-fields .val { border-bottom: 0.6pt dotted #888; min-width: 18mm; }

    /* ── Section titles (การลงโทษ, วิธีการแจ้ง ฯลฯ) ── */
    .wl-sec {
        font-weight: bold;
        text-decoration: underline;
        margin: 4mm 0 2mm;
        font-size: 10.5pt;
    }

    /* ── Violation box (กรอบพฤติการณ์) ── */
    .wl-vbox {
        border: 1pt solid #bbb;
        border-radius: 2pt;
        padding: 3mm 4mm;
        margin-bottom: 3mm;
        min-height: 22mm;
        background: #fafafa;
    }
    .wl-vbox p { margin: 0 0 2mm; text-indent: 10mm; text-align: justify; line-height: 1.7; }

    /* ── Paragraph styles ── */
    .wl-p {
        text-align: justify;
        text-indent: 10mm;
        line-height: 1.7;
        margin-bottom: 2.5mm;
        font-size: 10.5pt;
    }
    .wl-p-ul {
        text-align: justify;
        text-indent: 10mm;
        line-height: 1.7;
        margin-bottom: 2.5mm;
        text-decoration: underline;
        font-size: 10.5pt;
    }

    /* ── Note box (หมายเหตุ — สไตล์ blockquote) ── */
    .wl-note-box {
        background: #f7f7f7;
        border-left: 2pt solid #aaa;
        padding: 3mm 4mm;
        margin: 3mm 0;
        font-size: 9.5pt;
        line-height: 1.55;
    }
    .wl-note-title { font-weight: bold; text-decoration: underline; }

    /* ── Checkbox rows ── */
    .wl-chk {
        display: flex;
        align-items: flex-start;
        gap: 3mm;
        margin: 1.5mm 0 1.5mm 18mm;
        font-size: 10.5pt;
        line-height: 1.5;
    }
    .wl-chk-icon { font-size: 13pt; line-height: 1; flex-shrink: 0; }

    /* ── ลายเซ็น (ใน table row) ── */
    .wl-sig td {
        padding: 4mm 3mm;
        text-align: center;
        vertical-align: top;
        width: 50%;
    }
    .wl-sig-line {
        border-bottom: 0.5pt dotted #333;
        width: 48mm;
        margin: 0 auto 1mm;
        height: 9mm;
    }
    .wl-sig-lbl { font-size: 9pt; color: #444; margin-bottom: 0.5mm; }
    .wl-sig-nm { font-size: 10pt; }
    .wl-sig-pre { font-size: 9pt; color: #666; margin-bottom: 0.5mm; }
    """


# ══════════════════════════════════════════════════════════════════════
# SIGNATURE BUILDER
# ══════════════════════════════════════════════════════════════════════

def _sig_cell(label, name):
    """สร้าง <td> ลายเซ็น 1 ช่อง"""
    e = _esc
    name_display = f'({e(name)})' if name else '(....................................................................)'
    return f'''<td>
      <div class="wl-sig-pre">ลงชื่อ</div>
      <div class="wl-sig-line"></div>
      <div class="wl-sig-lbl">{label}</div>
      <div class="wl-sig-nm">{name_display}</div>
    </td>'''


def _build_sig_rows(data):
    """สร้าง signature rows (3 แถว) สำหรับ embed ใน table
    แถว 1: กรรมการ/นายจ้าง 1 | กรรมการ/นายจ้าง 2 (ถ้ามี)
    แถว 2: พนักงาน | หัวหน้างาน
    แถว 3: พยาน 1 | พยาน 2
    """
    co_signer1 = data.get('companySignerName', '')
    co_signer2 = data.get('companySignerName2', '')
    emp_signer = data.get('employeeSignerName', data.get('employeeName', ''))
    supervisor = data.get('supervisorName', '')
    witness1   = data.get('witness1Name', '')
    witness2   = data.get('witness2Name', '')

    html = ''

    # แถว 1: กรรมการ 1 | กรรมการ 2
    html += '<tr class="wl-sig">'
    html += _sig_cell('นายจ้าง/บริษัท', co_signer1)
    if co_signer2:
        html += _sig_cell('นายจ้าง/บริษัท (คนที่ 2)', co_signer2)
    else:
        html += '<td></td>'
    html += '</tr>'

    # แถว 2: พนักงาน | หัวหน้างาน
    html += '<tr class="wl-sig">'
    html += _sig_cell('พนักงาน', emp_signer)
    html += _sig_cell('หัวหน้างาน', supervisor)
    html += '</tr>'

    # แถว 3: พยาน 1 | พยาน 2
    html += '<tr class="wl-sig">'
    html += _sig_cell('พยาน', witness1)
    html += _sig_cell('พยาน', witness2)
    html += '</tr>'

    return html


# ══════════════════════════════════════════════════════════════════════
# HTML BUILDER
# ══════════════════════════════════════════════════════════════════════

def _build_warning_html(data):
    """สร้าง HTML หนังสือตักเตือน — 2 table (หน้า 1 + หน้า 2) มีกรอบปิดสมบูรณ์"""
    e = _esc

    # ── ดึงข้อมูลจาก data ──
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

    # ── วันที่: รองรับทั้ง string เดียว หรือแยก date/month/year ──
    if doc_date and not doc_month:
        date_text = doc_date
    else:
        date_text = f"{doc_date} เดือน {doc_month} พ.ศ. {doc_year}"

    # ── เนื้อหาพฤติการณ์ — แบ่งย่อหน้า ──
    body_raw = str(data.get('violationDetails', '') or '').strip()
    if body_raw:
        body_paras = [p.strip() for p in body_raw.split('\n') if p.strip()]
    else:
        body_paras = ['']
    body_html = '\n'.join(f'<p>{e(p)}</p>' for p in body_paras)

    # ── ประเภทการลงโทษ + วิธีแจ้ง ──
    punishment   = data.get('punishmentType', 'written')
    notif_method = data.get('notificationMethod', 'read_aloud')

    # ── สร้าง CSS + sig rows ──
    css = build_css() + _build_warning_css()
    sig_html = _build_sig_rows(data)

    # ════════════════════════════════════════════
    # HTML Content — 2 tables แยก page
    # Table 1 (หน้า 1): หัวเรื่อง + เนื้อหาหลัก
    # Table 2 (หน้า 2): หมายเหตุ + วิธีแจ้ง + ลายเซ็น
    # ════════════════════════════════════════════
    content = f"""<div class="page">
  <div class="doc-number" style="margin-bottom:4mm">{doc_number}</div>

  <!-- ═══ หน้า 1: เนื้อหาหลัก ═══ -->
  <table class="wl-tbl">
    <tr><td colspan="2" class="wl-hdr">
      <div class="wl-hdr-title">หนังสือตักเตือนพนักงาน</div>
    </td></tr>
    <tr><td colspan="2" class="wl-content">

      <p class="wl-p">หนังสือฉบับนี้ทำขึ้นเมื่อวันที่ {date_text} ระหว่าง {company} {company_addr}</p>

      <table class="wl-fields">
        <tr>
          <td class="lbl">นาย / นาง / นางสาว</td>
          <td class="val">{emp_name}</td>
          <td class="lbl">เลขประจำตัวประชาชน</td>
          <td class="val">{emp_id}</td>
        </tr>
        <tr>
          <td class="lbl">รหัสพนักงาน</td>
          <td class="val">{emp_code}</td>
          <td class="lbl">ตำแหน่ง</td>
          <td class="val">{emp_pos}</td>
        </tr>
        <tr>
          <td class="lbl">แผนก</td>
          <td class="val" colspan="3">{emp_dept}</td>
        </tr>
      </table>

      <div class="wl-sec">พฤติการณ์การกระทำผิดที่เกิดขึ้น เมื่อวันที่ {incident_date}</div>
      <div class="wl-vbox">
        {body_html}
      </div>

      <p class="wl-p-ul">ดังนั้นการกระทำของท่านถือว่าไม่สอดคล้องกับระเบียบและข้อบังคับเกี่ยวกับการทำงานของบริษัท จึงถือเป็นการกระทำความผิดต่อบริษัทและทำให้บริษัทได้รับความเสียหายจากการกระทำของท่าน</p>

      <div class="wl-sec">การลงโทษในครั้งนี้</div>
      <div class="wl-chk"><span class="wl-chk-icon">{_chk(punishment == 'verbal')}</span> ตักเตือนด้วยวาจา</div>
      <div class="wl-chk"><span class="wl-chk-icon">{_chk(punishment == 'written')}</span> ตักเตือนเป็นลายลักษณ์อักษร</div>
      <div class="wl-chk"><span class="wl-chk-icon">{_chk(punishment == 'suspension')}</span> พักงานโดยไม่ได้รับค่าจ้างและตักเตือนเป็นลายลักษณ์อักษร</div>

      <p class="wl-p" style="margin-top:3mm">ขอตักเตือนผู้กระทำความผิดโดยห้ามมิให้กระทำความผิดเดิมซ้ำอีกมิฉะนั้นจะลงโทษในสถานหนักต่อไป แต่หากได้ลงโทษผู้กระทำความผิดโดยตักเตือนเป็นลายลักษณ์อักษรหรือพักงานโดยไม่ได้รับค่าจ้างและตักเตือนเป็นลายลักษณ์อักษรในครั้งนี้แล้ว ถ้าได้กระทำความผิดเดิมซ้ำอีกในคราวต่อไป <b><u>ภายในระยะเวลา 1 (หนึ่ง) ปี</u></b> นับแต่วันที่กระทำความผิดครั้งนี้ ผู้กระทำความผิดจะต้องถูกลงโทษด้วยการเลิกจ้างโดยไม่จ่ายค่าชดเชยใด ๆ ทั้งสิ้น เว้นแต่มีเหตุให้บรรเทาโทษซึ่งอาจจะลดโทษให้ได้ตามสมควร</p>

    </td></tr>
  </table>

  <!-- ═══ หน้า 2: หมายเหตุ + วิธีแจ้ง + ลายเซ็น ═══ -->
  <div style="page-break-before:always"></div>
  <div class="doc-number" style="margin-bottom:4mm">{doc_number}</div>

  <table class="wl-tbl">
    <tr><td colspan="2" class="wl-content">

      <div class="wl-note-box">
        <p><span class="wl-note-title">หมายเหตุ</span> ในกรณีที่พนักงานที่ถูกลงโทษไม่ยินยอมลงนามในหนังสือตักเตือนดังกล่าวข้างต้นศาลฎีกาแผนกคดีแรงงานได้เคยวินิจฉัยว่าหากนายจ้างได้แจ้งพนักงานที่ถูกลงโทษโดยชอบด้วยกฎหมายแล้วให้ถือว่าหนังสือตักเตือนมีผลสมบูรณ์</p>
        <p style="margin-top:2mm">— หากพนักงานไม่รับหนังสือเตือน บริษัทจะจัดส่งหนังสือเตือนไปยังภูมิลำเนา และ/หรือ อีเมล และ/หรือ ไลน์แจ้งหนังสือเตือน และให้ถือว่าท่านรับหนังสือเตือนดังกล่าวโดยชอบแล้ว</p>
      </div>

      <div class="wl-sec">วิธีการแจ้ง</div>
      <p style="margin-bottom:2mm;font-size:10.5pt">ด้วยวิธีใดวิธีหนึ่ง ดังต่อไปนี้</p>
      <div class="wl-chk"><span class="wl-chk-icon">{_chk(notif_method == 'posted')}</span> ติดประกาศให้ทราบในสถานประกอบการ</div>
      <div class="wl-chk"><span class="wl-chk-icon">{_chk(notif_method == 'read_aloud')}</span> อ่านให้ผู้กระทำความผิดทราบ โดยมีพยานรับรู้การลงโทษในครั้งนี้และลงนามเป็นพยานอย่างน้อย 2 คน</div>
      <div class="wl-chk"><span class="wl-chk-icon">{_chk(notif_method == 'mail')}</span> ส่งไปรษณีย์ลงทะเบียนตามที่อยู่ที่ติดต่อได้</div>

    </td></tr>
    {sig_html}
  </table>
</div>"""

    return build_html(css, content)


# ══════════════════════════════════════════════════════════════════════
# PDF MERGE — overlay ทุกหน้าบน entity template
# ══════════════════════════════════════════════════════════════════════

def _merge_multi_page(content_bytes, entity_key):
    """Overlay ทุกหน้าของ content บน entity template (ไม่ใช่แค่หน้าแรก)
    ใช้ deepcopy template page สำหรับแต่ละ content page
    """
    from io import BytesIO
    from copy import deepcopy
    from pypdf import PdfReader, PdfWriter
    from template_utils import resolve_template
    import os

    base = os.path.dirname(os.path.abspath(__file__))
    tpl_name = resolve_template(entity_key)
    tpl_path = os.path.join(base, tpl_name)

    # fallback ถ้า template ไม่พบ
    if not os.path.exists(tpl_path):
        tpl_path = os.path.join(base, 'bg_template_scmtech.pdf')
    if not os.path.exists(tpl_path):
        logger.warning(f'Template ไม่พบ: {tpl_name} — คืน content เปล่า')
        return content_bytes

    tpl_reader = PdfReader(tpl_path)
    tpl_page = tpl_reader.pages[0]
    content_reader = PdfReader(BytesIO(content_bytes))
    writer = PdfWriter()

    for page in content_reader.pages:
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
    """ลงทะเบียน route /generate_warning_letter"""

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

            # สร้าง HTML → PDF → overlay บน template
            html = _build_warning_html(data)
            content_bytes = html_to_pdf(html)

            entity_key = data.get('entityKey', '')
            pdf_bytes = _merge_multi_page(content_bytes, entity_key)
            pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

            # สร้างชื่อไฟล์ปลอดภัย
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
