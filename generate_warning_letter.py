#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: v9-sarabun14
"""
generate_warning_letter.py — หนังสือตักเตือนพนักงาน (Warning Letter)
═══════════════════════════════════════════════════════════════════

★ v9 (2026-10): TH Sarabun New 14 (ขนาดแบบ Word) + ไม่มีเส้นกรอบ — กำหนดที่ hr_doc_layout / template_utils

★ v8 (2026-10): จัดหน้าใหม่ด้วย hr_doc_layout
  - ข้อความไม่ชิดเส้นกรอบ (เดิมระยะขอบในกรอบถูกกฎ CSS อื่นทับเป็น 0)
  - ไม่บังคับขึ้นหน้า 2 ที่ตำแหน่งตายตัว — กรอบไหลต่อเนื่องตามความยาวเนื้อหา
  - เลขที่หนังสือ + หน้า x / y ทุกหน้า, ช่องลงนามไม่มีเส้นตาราง
  - ถ้อยคำของหนังสือคงเดิมทุกตัวอักษร
"""

import base64
import logging
from flask import request, jsonify
from template_utils import html_to_pdf
from hr_doc_layout import (
    esc as _esc, document, fields, nowrap, option, paragraphs, signatures, merge_multi_page
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# HTML BUILDER
# ══════════════════════════════════════════════════════════════════════

def _build_warning_html(data):
    e = _esc
    g = lambda k: str(data.get(k, '') or '').strip()

    doc_date, doc_month, doc_year = g('docDate'), g('docMonth'), g('docYear')
    date_text = doc_date if (doc_date and not doc_month) else f"{doc_date} เดือน {doc_month} พ.ศ. {doc_year}"

    punishment   = data.get('punishmentType', 'written')
    notif_method = data.get('notificationMethod', 'read_aloud')

    emp_name = g('employeeName')
    co2      = g('companySignerName2')

    body = f"""
<p>หนังสือฉบับนี้ทำขึ้นเมื่อวันที่ {e(date_text)} ระหว่าง {nowrap(g('companyName'))} {nowrap(g('companyAddress'))}</p>
{fields([
    [('นาย / นาง / นางสาว', emp_name)],
    [('เลขประจำตัวประชาชน', g('employeeIdCard')), ('รหัสพนักงาน', g('employeeCode'))],
    [('ตำแหน่ง', g('employeePosition')), ('แผนก', g('employeeDepartment'))],
])}
<div class="sec">พฤติการณ์การกระทำผิดที่เกิดขึ้น เมื่อวันที่ {e(g('incidentDate'))}</div>
<div class="box">{paragraphs(data.get('violationDetails', '')) or '<p>&nbsp;</p>'}</div>
<p class="ul">ดังนั้นการกระทำของท่านถือว่าไม่สอดคล้องกับระเบียบและข้อบังคับเกี่ยวกับการทำงานของบริษัท จึงถือเป็นการกระทำความผิดต่อบริษัทและทำให้บริษัทได้รับความเสียหายจากการกระทำของท่าน</p>
<div class="sec">การลงโทษในครั้งนี้</div>
{option(punishment == 'verbal', 'ตักเตือนด้วยวาจา')}
{option(punishment == 'written', 'ตักเตือนเป็นลายลักษณ์อักษร')}
{option(punishment == 'suspension', 'พักงานโดยไม่ได้รับค่าจ้างและตักเตือนเป็นลายลักษณ์อักษร')}
<p style="margin-top:3mm">ขอตักเตือนผู้กระทำความผิดโดยห้ามมิให้กระทำความผิดเดิมซ้ำอีกมิฉะนั้นจะลงโทษในสถานหนักต่อไป แต่หากได้ลงโทษผู้กระทำความผิดโดยตักเตือนเป็นลายลักษณ์อักษรหรือพักงานโดยไม่ได้รับค่าจ้างและตักเตือนเป็นลายลักษณ์อักษรในครั้งนี้แล้ว ถ้าได้กระทำความผิดเดิมซ้ำอีกในคราวต่อไป <b class="ul">ภายในระยะเวลา 1 (หนึ่ง) ปี</b> นับแต่วันที่กระทำความผิดครั้งนี้ ผู้กระทำความผิดจะต้องถูกลงโทษด้วยการเลิกจ้างโดยไม่จ่ายค่าชดเชยใด ๆ ทั้งสิ้น เว้นแต่มีเหตุให้บรรเทาโทษซึ่งอาจจะลดโทษให้ได้ตามสมควร</p>
<div class="note">
  <p><b class="ul">หมายเหตุ</b> ในกรณีที่พนักงานที่ถูกลงโทษไม่ยินยอมลงนามในหนังสือตักเตือนดังกล่าวข้างต้นศาลฎีกาแผนกคดีแรงงานได้เคยวินิจฉัยว่าหากนายจ้างได้แจ้งพนักงานที่ถูกลงโทษโดยชอบด้วยกฎหมายแล้วให้ถือว่าหนังสือตักเตือนมีผลสมบูรณ์</p>
  <p>— หากพนักงานไม่รับหนังสือเตือน บริษัทจะจัดส่งหนังสือเตือนไปยังภูมิลำเนา และ/หรือ อีเมล และ/หรือ ไลน์แจ้งหนังสือเตือน และให้ถือว่าท่านรับหนังสือเตือนดังกล่าวโดยชอบแล้ว</p>
</div>
<div class="keep">
<div class="sec">วิธีการแจ้ง</div>
<p class="flush">ด้วยวิธีใดวิธีหนึ่ง ดังต่อไปนี้</p>
{option(notif_method == 'posted', 'ติดประกาศให้ทราบในสถานประกอบการ')}
{option(notif_method == 'read_aloud', 'อ่านให้ผู้กระทำความผิดทราบ โดยมีพยานรับรู้การลงโทษในครั้งนี้และลงนามเป็นพยานอย่างน้อย 2 คน')}
{option(notif_method == 'mail', 'ส่งไปรษณีย์ลงทะเบียนตามที่อยู่ที่ติดต่อได้')}
{signatures([
    ('นายจ้าง/บริษัท', g('companySignerName')),
    ('นายจ้าง/บริษัท (คนที่ 2)', co2) if co2 else None,
    ('พนักงาน', str(data.get('employeeSignerName', emp_name) or '').strip()),
    ('หัวหน้างาน', g('supervisorName')),
    ('พยาน', g('witness1Name')),
    ('พยาน', g('witness2Name')),
])}
</div>
"""
    return document('หนังสือตักเตือนพนักงาน', body, g('docNumber'))


# เดิมฟังก์ชันซ้อนหัวกระดาษเขียนซ้ำอยู่ในไฟล์นี้และไฟล์สัญญาฝึกอบรม — ย้ายไป hr_doc_layout
_merge_multi_page = merge_multi_page


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
            pdf_bytes = merge_multi_page(content_bytes, entity_key)
            pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

            emp = (data.get('employeeName', '') or 'warning')[:30]
            safe_name = ''.join(
                ch for ch in emp
                if ch.isalnum() or ch in '_- ' or '฀' <= ch <= '๿'
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
