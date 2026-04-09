#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: v6-s14
"""
generate_warning_letter.py — หนังสือตักเตือนพนักงาน (Warning Letter)
═══════════════════════════════════════════════════════════════════
ใช้ template_utils (WeasyPrint + entity template overlay)

★ S14 v6 changes:
  - [FIX] เพิ่ม @font-face embed THSarabunNew ใน CSS — แก้ body text garbled
    (v5 พึ่ง build_css() แต่ WL override @page ทำให้ WeasyPrint fallback font อื่น)
  - [FIX] ลด @page margin-top 30mm → 17mm — doc-number ชิด logo template
  - [FIX] ตรวจ word spacing, line-height, padding ทั้งฉบับ
  - [FIX] ไม่ใช้ build_css() แล้ว — ใช้ _build_warning_css() ที่มี @font-face ครบ
  - ไม่มี breaking changes กับ API / GAS frontend

★ S13 v5:  Font rename fix + page duplication fix
★ S12 v4:  Layout table border, 2 หน้า, sig 3 แถว
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
# UTILITY
# ══════════════════════════════════════════════════════════════════════

def _esc(s):
    return (str(s or '').replace('&','&amp;').replace('<','&lt;')
            .replace('>','&gt;').replace('"','&quot;'))

def _chk(checked):
    return '☒' if checked else '☐'


# ══════════════════════════════════════════════════════════════════════
# CSS — ★ v6: เพิ่ม @font-face embed + ลด margin-top 30→17mm
# ══════════════════════════════════════════════════════════════════════

def _build_warning_css():
    """CSS สำหรับหนังสือตักเตือน — รวม @font-face embed THSarabunNew"""
    fonts = font_b64()
    reg  = fonts.get('THSarabunNew.ttf', '')
    bold = fonts.get('THSarabunNew-Bold.ttf', '')
    ff = ''
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

    return ff + """
    @page { size: A4; margin: 17mm 18mm 18mm 22mm; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: 'THSarabunNew', 'TH Sarabun New', sans-serif;
        font-size: 10.5pt;
        color: #000;
        line-height: 1.6;
    }
    .page { width: auto; min-height: auto; padding: 0; }
    .doc-number { font-size: 10pt; margin-bottom: 3mm; }
    .wl-tbl { width: 100%; border-collapse: collapse; border: 1.2pt solid #1a1a1a; }
    .wl-tbl td { border: 0.8pt solid #444; padding: 0; vertical-align: top; }
    .wl-hdr { background: #f0f4f8; text-align: center; padding: 3.5mm 5mm; }
    .wl-hdr-title { font-size: 14pt; font-weight: bold; text-decoration: underline; letter-spacing: 0.5pt; color: #1a1a1a; }
    .wl-content { padding: 4mm 6mm 3.5mm; font-size: 10.5pt; line-height: 1.6; }
    .wl-fields { width: 100%; border-collapse: collapse; margin-bottom: 2.5mm; font-size: 10.5pt; }
    .wl-fields td { padding: 1.2mm 2mm; border: none; vertical-align: bottom; }
    .wl-fields .lbl { font-weight: bold; white-space: nowrap; color: #222; }
    .wl-fields .val { border-bottom: 0.6pt dotted #888; min-width: 18mm; }
    .wl-sec { font-weight: bold; text-decoration: underline; margin: 3mm 0 1.5mm; font-size: 10.5pt; }
    .wl-vbox { border: 1pt solid #bbb; border-radius: 2pt; padding: 2.5mm 4mm; margin-bottom: 2.5mm; min-height: 22mm; background: #fafafa; }
    .wl-vbox p { margin: 0 0 1.5mm; text-indent: 10mm; text-align: left; line-height: 1.65; font-size: 10.5pt; word-wrap: break-word; }
    .wl-p { text-align: left; text-indent: 10mm; line-height: 1.65; margin-bottom: 2mm; font-size: 10.5pt; word-wrap: break-word; }
    .wl-p-ul { text-align: left; text-indent: 10mm; line-height: 1.65; margin-bottom: 2mm; text-decoration: underline; font-size: 10.5pt; word-wrap: break-word; }
    .wl-note-box { background: #f7f7f7; border-left: 2pt solid #aaa; padding: 2.5mm 4mm; margin: 2.5mm 0; font-size: 9.5pt; line-height: 1.5; word-wrap: break-word; }
    .wl-note-title { font-weight: bold; text-decoration: underline; }
    .wl-chk { display: flex; align-items: flex-start; gap: 3mm; margin: 1.5mm 0 1.5mm 18mm; font-size: 10.5pt; line-height: 1.45; }
    .wl-chk-icon { font-size: 13pt; line-height: 1; flex-shrink: 0; }
    .wl-sig td { padding: 3.5mm 3mm; text-align: center; vertical-align: top; width: 50%; }
    .wl-sig-line { border-bottom: 0.5pt dotted #333; width: 48mm; margin: 0 auto 1mm; height: 9mm; }
    .wl-sig-lbl { font-size: 9pt; color: #444; margin-bottom: 0.5mm; }
    .wl-sig-nm { font-size: 10pt; }
    .wl-sig-pre { font-size: 9pt; color: #666; margin-bottom: 0.5mm; }
    """


# ══════════════════════════════════════════════════════════════════════
# SIGNATURE
# ══════════════════════════════════════════════════════════════════════

def _sig_cell(label, name):
    e = _esc
    nd = f'({e(name)})' if name else '(....................................................................)'
    return f'<td><div class="wl-sig-pre">ลงชื่อ</div><div class="wl-sig-line"></div><div class="wl-sig-lbl">{label}</div><div class="wl-sig-nm">{nd}</div></td>'

def _build_sig_rows(data):
    co1 = data.get('companySignerName', '')
    co2 = data.get('companySignerName2', '')
    emp = data.get('employeeSignerName', data.get('employeeName', ''))
    sup = data.get('supervisorName', '')
    w1  = data.get('witness1Name', '')
    w2  = data.get('witness2Name', '')
    h = '<tr class="wl-sig">' + _sig_cell('นายจ้าง/บริษัท', co1)
    h += _sig_cell('นายจ้าง/บริษัท (คนที่ 2)', co2) if co2 else '<td></td>'
    h += '</tr><tr class="wl-sig">' + _sig_cell('พนักงาน', emp) + _sig_cell('หัวหน้างาน', sup)
    h += '</tr><tr class="wl-sig">' + _sig_cell('พยาน', w1) + _sig_cell('พยาน', w2) + '</tr>'
    return h


# ══════════════════════════════════════════════════════════════════════
# HTML BUILDER — ★ v6: ใช้ _build_warning_css() เท่านั้น (มี @font-face ครบ)
# ══════════════════════════════════════════════════════════════════════

def _build_warning_html(data):
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

    date_text = doc_date if (doc_date and not doc_month) else f"{doc_date} เดือน {doc_month} พ.ศ. {doc_year}"

    body_raw = str(data.get('violationDetails', '') or '').strip()
    body_paras = [p.strip() for p in body_raw.split('\n') if p.strip()] if body_raw else ['']
    body_html = '\n'.join(f'<p>{e(p)}</p>' for p in body_paras)

    punishment   = data.get('punishmentType', 'written')
    notif_method = data.get('notificationMethod', 'read_aloud')

    # ★ v6: ใช้เฉพาะ _build_warning_css() ที่มี @font-face + margin ครบ
    css = _build_warning_css()
    sig_html = _build_sig_rows(data)

    content = f"""<div class="page">
  <div class="doc-number">{doc_number}</div>
  <table class="wl-tbl">
    <tr><td colspan="2" class="wl-hdr"><div class="wl-hdr-title">หนังสือตักเตือนพนักงาน</div></td></tr>
    <tr><td colspan="2" class="wl-content">
      <p class="wl-p">หนังสือฉบับนี้ทำขึ้นเมื่อวันที่ {date_text} ระหว่าง {company} {company_addr}</p>
      <table class="wl-fields">
        <tr><td class="lbl">นาย / นาง / นางสาว</td><td class="val">{emp_name}</td><td class="lbl">เลขประจำตัวประชาชน</td><td class="val">{emp_id}</td></tr>
        <tr><td class="lbl">รหัสพนักงาน</td><td class="val">{emp_code}</td><td class="lbl">ตำแหน่ง</td><td class="val">{emp_pos}</td></tr>
        <tr><td class="lbl">แผนก</td><td class="val" colspan="3">{emp_dept}</td></tr>
      </table>
      <div class="wl-sec">พฤติการณ์การกระทำผิดที่เกิดขึ้น เมื่อวันที่ {incident_date}</div>
      <div class="wl-vbox">{body_html}</div>
      <p class="wl-p-ul">ดังนั้นการกระทำของท่านถือว่าไม่สอดคล้องกับระเบียบและข้อบังคับเกี่ยวกับการทำงานของบริษัท จึงถือเป็นการกระทำความผิดต่อบริษัทและทำให้บริษัทได้รับความเสียหายจากการกระทำของท่าน</p>
      <div class="wl-sec">การลงโทษในครั้งนี้</div>
      <div class="wl-chk"><span class="wl-chk-icon">{_chk(punishment == 'verbal')}</span> ตักเตือนด้วยวาจา</div>
      <div class="wl-chk"><span class="wl-chk-icon">{_chk(punishment == 'written')}</span> ตักเตือนเป็นลายลักษณ์อักษร</div>
      <div class="wl-chk"><span class="wl-chk-icon">{_chk(punishment == 'suspension')}</span> พักงานโดยไม่ได้รับค่าจ้างและตักเตือนเป็นลายลักษณ์อักษร</div>
      <p class="wl-p" style="margin-top:2.5mm">ขอตักเตือนผู้กระทำความผิดโดยห้ามมิให้กระทำความผิดเดิมซ้ำอีกมิฉะนั้นจะลงโทษในสถานหนักต่อไป แต่หากได้ลงโทษผู้กระทำความผิดโดยตักเตือนเป็นลายลักษณ์อักษรหรือพักงานโดยไม่ได้รับค่าจ้างและตักเตือนเป็นลายลักษณ์อักษรในครั้งนี้แล้ว ถ้าได้กระทำความผิดเดิมซ้ำอีกในคราวต่อไป <b><u>ภายในระยะเวลา 1 (หนึ่ง) ปี</u></b> นับแต่วันที่กระทำความผิดครั้งนี้ ผู้กระทำความผิดจะต้องถูกลงโทษด้วยการเลิกจ้างโดยไม่จ่ายค่าชดเชยใด ๆ ทั้งสิ้น เว้นแต่มีเหตุให้บรรเทาโทษซึ่งอาจจะลดโทษให้ได้ตามสมควร</p>
    </td></tr>
  </table>
  <div style="page-break-before:always"></div>
  <div class="doc-number">{doc_number}</div>
  <table class="wl-tbl">
    <tr><td colspan="2" class="wl-content">
      <div class="wl-note-box">
        <p><span class="wl-note-title">หมายเหตุ</span> ในกรณีที่พนักงานที่ถูกลงโทษไม่ยินยอมลงนามในหนังสือตักเตือนดังกล่าวข้างต้นศาลฎีกาแผนกคดีแรงงานได้เคยวินิจฉัยว่าหากนายจ้างได้แจ้งพนักงานที่ถูกลงโทษโดยชอบด้วยกฎหมายแล้วให้ถือว่าหนังสือตักเตือนมีผลสมบูรณ์</p>
        <p style="margin-top:1.5mm">— หากพนักงานไม่รับหนังสือเตือน บริษัทจะจัดส่งหนังสือเตือนไปยังภูมิลำเนา และ/หรือ อีเมล และ/หรือ ไลน์แจ้งหนังสือเตือน และให้ถือว่าท่านรับหนังสือเตือนดังกล่าวโดยชอบแล้ว</p>
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
# PDF MERGE — rename font ก่อน merge ป้องกัน conflict
# ══════════════════════════════════════════════════════════════════════

def _merge_multi_page(content_bytes, entity_key):
    """Overlay ทุกหน้าของ content บน entity template

    ★ S13 FIX-1: rename THSarabunNew → THSarabunNewTPL ก่อน merge
    ★ S13 FIX-2: อ่าน template ใหม่ทุกหน้า (PdfReader) แทน deepcopy
    """
    from io import BytesIO
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject
    from template_utils import resolve_template
    import os

    base = os.path.dirname(os.path.abspath(__file__))
    tpl_name = resolve_template(entity_key)
    tpl_path = os.path.join(base, tpl_name)

    if not os.path.exists(tpl_path):
        tpl_path = os.path.join(base, 'bg_template_scmtech.pdf')
    if not os.path.exists(tpl_path):
        logger.warning(f'Template ไม่พบ: {tpl_name} — คืน content เปล่า')
        return content_bytes

    content_reader = PdfReader(BytesIO(content_bytes))
    writer = PdfWriter()

    for page in content_reader.pages:
        tpl_reader = PdfReader(tpl_path)
        bg = tpl_reader.pages[0]

        fonts = bg.get("/Resources", {}).get("/Font", {})
        for key in list(fonts.keys()):
            font_obj = fonts[key].get_object()
            base_font = str(font_obj.get("/BaseFont", ""))
            if "THSarabunNew" in base_font:
                new_bf = base_font.replace("THSarabunNew", "THSarabunNewTPL")
                font_obj[NameObject("/BaseFont")] = NameObject("/" + new_bf.lstrip("/"))
                if "/FontDescriptor" in font_obj:
                    fd = font_obj["/FontDescriptor"].get_object()
                    fd_name = str(fd.get("/FontName", ""))
                    if "THSarabunNew" in fd_name:
                        new_fn = fd_name.replace("THSarabunNew", "THSarabunNewTPL")
                        fd[NameObject("/FontName")] = NameObject("/" + new_fn.lstrip("/"))

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
            if err: return err

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
