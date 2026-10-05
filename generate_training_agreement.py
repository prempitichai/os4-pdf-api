#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: v9-layout
"""
generate_training_agreement.py — สัญญาเข้าศึกษา / ฝึกอบรม / สอบ
═══════════════════════════════════════════════════════════════════

★ v9 (2026-10): จัดหน้าใหม่ด้วย hr_doc_layout
  - ข้อความไม่ชิดเส้นกรอบ (เดิมระยะขอบในกรอบถูกกฎ CSS อื่นทับเป็น 0)
  - ไม่บังคับขึ้นหน้า 2 ก่อนข้อ 7 — กรอบไหลต่อเนื่อง ข้อสัญญาไม่ถูกบีบจนชิดแถบท้ายกระดาษ
  - เลขที่หนังสือ + หน้า x / y ทุกหน้า, ช่องลงนามไม่มีเส้นตาราง
  - ถ้อยคำของสัญญาคงเดิมทุกตัวอักษร

★ S48.5 v8 (2026-04-27): _fmt_money() + รหัสพนักงาน
"""

import base64
import logging
from flask import request, jsonify
from template_utils import html_to_pdf
from hr_doc_layout import (
    esc as _esc, document, fields, nowrap, signatures, merge_multi_page
)

logger = logging.getLogger(__name__)

# ขนาดตัวอักษรเนื้อหา (pt) — สัญญา 9 ข้อ + ช่องลงนาม ต้องลงใน 2 หน้า
_BASE_PT = 10


def _fmt_money(v):
    """
    Format ตัวเลขเงิน → "1,234,567.89" (มี comma คั่นพัน + 2 ทศนิยม)

    Examples:
        _fmt_money("3177.57")    → "3,177.57"
        _fmt_money(1234567.89)   → "1,234,567.89"
        _fmt_money("3,177.57")   → "3,177.57"  (handle existing commas)
        _fmt_money("")           → ""
        _fmt_money(None)         → ""
        _fmt_money("abc")        → "abc"  (defensive — return ค่าเดิม ไม่แตก PDF)
    """
    if v is None or v == '':
        return ''
    try:
        clean = str(v).replace(',', '').strip()
        if not clean:
            return ''
        n = float(clean)
        if n == 0:
            return ''
        return f"{n:,.2f}"
    except (ValueError, TypeError):
        return str(v)


# ══════════════════════════════════════════════════════════════════════
# HTML BUILDER
# ══════════════════════════════════════════════════════════════════════

def _build_training_html(data):
    """
    Build complete HTML สำหรับ Training Agreement PDF

    Args:
        data: dict จาก request.get_json() — มี keys ตาม payload จาก GAS
              (entityKey, docNumber, companyName, employeeName, employeeCode,
               employeeIdCard, courseName, trainingCost, trainingCostText, ฯลฯ)
    """
    e = _esc
    g = lambda k: str(data.get(k, '') or '').strip()

    company, company_addr = nowrap(g('companyName')), nowrap(g('companyAddress'))
    emp_name = g('employeeName')
    t_date, t_month, t_year = e(g('trainingDate')), e(g('trainingMonth')), e(g('trainingYear'))
    t_cost     = e(_fmt_money(data.get('trainingCost', '')))
    t_cost_txt = e(g('trainingCostText'))
    c_date, c_month, c_year = e(g('contractDate')), e(g('contractMonth')), e(g('contractYear'))
    co2 = g('companySignerName2')

    body = f"""
<p class="flush lead"><b>หลักสูตร :</b> {e(g('courseName'))}</p>
<p>สัญญาฉบับนี้ทำขึ้นเมื่อวันที่ {c_date} เดือน {c_month} พ.ศ. {c_year} ระหว่าง {company} {company_addr} ซึ่งต่อไปนี้เรียกว่า <b>"บริษัทฯ"</b> ฝ่ายหนึ่งกับ</p>
{fields([
    [('นาย / นาง / นางสาว', emp_name)],
    [('ตำแหน่ง', g('employeePosition')), ('แผนก', g('employeeDepartment'))],
    [('อายุ', g('employeeAge'), '14mm'), ('เลขประจำตัวประชาชน', g('employeeIdCard')), ('รหัสพนักงาน', g('employeeCode'))],
    [('ที่อยู่', g('employeeAddress'))],
])}
<p>ซึ่งต่อไปในสัญญาจะเรียกว่า <b>"พนักงาน"</b> อีกฝ่ายหนึ่ง</p>
<div class="sec">ทั้งสองฝ่ายจึงได้ตกลงกันดังต่อไปนี้</div>
<p class="cl"><b>ข้อ 1.</b> บริษัทฯ จะส่งพนักงานไปศึกษา / ฝึกอบรม / สอบตามหลักสูตร ในวันที่ {t_date} เดือน {t_month} พ.ศ. {t_year} โดยบริษัทฯ จะรับผิดชอบค่าใช้จ่ายเกี่ยวกับการฝึกอบรมในครั้งนี้เป็นจำนวนเงิน {t_cost} บาท ({t_cost_txt}) ทั้งนี้ ค่าใช้จ่ายดังกล่าวไม่เกี่ยวข้องกับเงินเดือนที่พนักงานได้รับจากบริษัทฯ</p>
<p class="cl"><b>ข้อ 2.</b> พนักงานยินยอมที่จะเข้ารับการศึกษา / ฝึกอบรม / สอบตามหลักสูตร ดังที่ระบุไว้ในข้อ 1. โดยจะไม่ใช้เวลาทำงานของบริษัทฯ เพื่อกิจธุระแห่งการศึกษา / ฝึกอบรมนั้น ยกเว้นกรณีที่หัวข้อฝึกอบรมนั้นๆ ถูกจัดขึ้นแค่ตรงกับเวลาทำงานของพนักงานตามที่บริษัทฯ จัดไว้ ทั้งนี้พนักงานจะต้องได้รับการอนุมัติจากบริษัทฯ แล้วเท่านั้น</p>
<p class="cl"><b>ข้อ 3.</b> พนักงานยอมรับว่าเมื่อจบการศึกษาหรือการฝึกอบรมดังกล่าวแล้ว พนักงานจะอยู่ปฏิบัติงานให้แก่บริษัทฯ และจะนำความรู้ ความสามารถ และประสบการณ์ที่ได้จากการฝึกอบรมมาใช้เพื่อให้เกิดประโยชน์แก่บริษัทฯ พร้อมทั้งถ่ายทอดความรู้ ความสามารถ และประสบการณ์ที่ได้รับมาให้แก่พนักงานอื่นของบริษัทฯ นับแต่วันที่จบหลักสูตร</p>
<p class="cl"><b>ข้อ 4.</b> พนักงานยอมรับว่าหากบริษัทฯ ส่งพนักงานไปศึกษา / ฝึกอบรม / สอบตามหลักสูตร ตามที่ระบุไว้ในข้อ 1. แล้วพนักงานไม่สามารถเข้ารับการศึกษา / ฝึกอบรมได้จนจบหลักสูตร หรือไม่สามารถอยู่ปฏิบัติงานกับบริษัทฯ ตามระยะเวลาที่กำหนดได้ ไม่ว่าด้วยเหตุใดๆ อันเนื่องมาจากตัวพนักงานเอง พนักงานยินยอมชดใช้ค่าใช้จ่ายหรือค่าตอบแทนให้แก่บริษัทฯ ตามเงื่อนไขดังต่อไปนี้</p>
<p class="sub"><b>(1)</b>&nbsp;&nbsp;สำหรับหลักสูตรที่มีค่าใช้จ่ายไม่เกิน 60,000.00 (หกหมื่น) บาทต่อ 1 (หนึ่ง) หลักสูตร พนักงานจะต้องอยู่ปฏิบัติงานกับบริษัทฯ เป็นระยะเวลาอย่างน้อย 6 (หก) เดือน นับตั้งแต่วันที่จบหลักสูตร หากไม่สามารถอยู่ปฏิบัติงานกับบริษัทฯ ได้ครบกำหนด 6 (หก) เดือน พนักงานยินยอมชดเชยค่าใช้จ่ายคิดเป็น 100 (หนึ่งร้อย) % ของค่าใช้จ่ายที่เกิดขึ้น</p>
<p class="sub"><b>(2)</b>&nbsp;&nbsp;สำหรับหลักสูตรที่มีค่าใช้จ่ายตั้งแต่ 60,000.00 (หกหมื่น) บาทขึ้นไปต่อ 1 (หนึ่ง) หลักสูตร พนักงานจะต้องอยู่ปฏิบัติงานกับบริษัทฯ เป็นระยะเวลาอย่างน้อย 1 (หนึ่ง) ปี นับตั้งแต่วันที่จบหลักสูตร หากไม่สามารถอยู่ปฏิบัติงานกับบริษัทฯ ได้ครบ 1 (หนึ่ง) ปี พนักงานยินยอมชดเชยค่าใช้จ่ายคิดเป็น 100 (หนึ่งร้อย) % ของค่าใช้จ่ายที่เกิดขึ้น</p>
<p class="cl"><b>ข้อ 5.</b> ในช่วงระหว่างที่ยังศึกษา / ฝึกอบรม / สอบ ไม่จบหลักสูตร หากพนักงานกระทำความผิดใดๆ เป็นเหตุให้ได้รับโทษจำคุกหรือถูกเนรเทศ หรือได้รับโทษอื่นใดตามกฎหมาย ทำให้พนักงานไม่สามารถเข้ารับการศึกษา / ฝึกอบรมครบตามกำหนดระยะเวลาได้ พนักงานยินยอมชดใช้ค่าเสียหายให้แก่บริษัทฯ เท่ากับจำนวนที่ระบุไว้ในข้อ 4.</p>
<p class="cl"><b>ข้อ 6.</b> ในระหว่างที่พนักงานทำงานให้แก่บริษัทฯ ตามกำหนดระยะเวลาในข้อ 3. หากพนักงานกระทำการใดๆ อันฝ่าฝืนกฎระเบียบ ประกาศ คำสั่ง หรือข้อบังคับของบริษัทฯ อันเป็นผลให้พนักงานถูกลงโทษทางวินัยถึงขั้นให้ออก ปลดออก แล้วแต่กรณี ให้ถือว่าพนักงานไม่สามารถทำงานให้แก่บริษัทฯ ได้และยินยอมชดใช้ค่าเสียหายหรือค่าตอบแทนให้แก่บริษัทฯ ตามจำนวนที่ระบุไว้ในข้อ 4.</p>
<p class="cl"><b>ข้อ 7.</b> บริษัทฯ จะจ่ายเงินเดือนให้แก่พนักงานในช่วงระหว่างระยะเวลาที่พนักงานศึกษา / ฝึกอบรม / สอบ ตามที่ได้ตกลงกันและตามระเบียบของบริษัทฯ</p>
<p class="cl"><b>ข้อ 8.</b> ในกรณีที่บริษัทฯ ได้ส่งพนักงานไปศึกษา / ฝึกอบรม / สอบตามหลักสูตร หรือค่าใช้จ่ายใดๆ ที่เกิดขึ้นก็ตาม หากพนักงานไม่ดำเนินการไปศึกษา / ฝึกอบรม / สอบ ตามหลักสูตร ที่ตกลงไว้ ไม่ว่าด้วยเหตุใดๆ ก็ตาม พนักงานยินยอมชดใช้ค่าใช้จ่ายต่างๆ ทั้งหมดที่ได้ระบุไว้ในสัญญานี้ โดยพนักงานตกลงชำระให้แก่บริษัทฯ ภายใน 30 (สามสิบ) วัน นับตั้งแต่วันที่พนักงานไม่ได้ปฏิบัติตามที่ตกลงไว้</p>
<p class="cl"><b>ข้อ 9.</b> พนักงานยินยอมให้บริษัทฯ หักค่าชดใช้ใดๆ ที่พนักงานทำผิดสัญญาและจากจำนวนเงินใดๆ ที่พนักงานได้ผิดนัดชำระกับบริษัทฯ จากค่าจ้างที่พนักงานได้รับจากบริษัทฯ</p>
<p>อนึ่งการที่บริษัทฯ ไม่ใช้สิทธิหรือประวิงการใช้สิทธิ หรืออำนาจใดๆ ตามที่ระบุไว้ในสัญญานี้ในครั้งหนึ่งครั้งใด ไม่ถือว่าเป็นการที่บริษัทฯ สละสิทธิในเรื่องดังกล่าวต่อไป</p>
<div class="keep">
<p>สัญญานี้ทำขึ้น 2 (สอง) ฉบับ คู่สัญญาทั้งสองฝ่ายได้อ่านและเข้าใจข้อความและเงื่อนไขต่างๆ แห่งสัญญาฉบับนี้โดยละเอียดตลอดครบถ้วนแล้ว เห็นว่าถูกต้องตามเจตนาทุกประการเพื่อเป็นหลักฐานจึงได้ลงลายมือชื่อ และประทับตรา (ถ้ามี) ไว้เป็นสำคัญและคู่สัญญาต่างยึดถือไว้ฝ่ายละหนึ่งฉบับ</p>
{signatures([
    ('นายจ้าง/บริษัทฯ', g('companySignerName')),
    ('นายจ้าง/บริษัทฯ (คนที่ 2)', co2) if co2 else None,
    ('พนักงาน', str(data.get('employeeSignerName', emp_name) or '').strip()),
    ('หัวหน้างาน', g('supervisorName')),
    ('พยาน', g('witness1Name')),
    ('พยาน', g('witness2Name')),
])}
</div>
"""
    return document('สัญญาเข้าศึกษา / ฝึกอบรม / สอบ', body, g('docNumber'), _BASE_PT, compact=True)


# เดิมฟังก์ชันซ้อนหัวกระดาษเขียนซ้ำอยู่ในไฟล์นี้และไฟล์หนังสือตักเตือน — ย้ายไป hr_doc_layout
_merge_multi_page = merge_multi_page


# ══════════════════════════════════════════════════════════════════════
# FLASK ROUTE
# ══════════════════════════════════════════════════════════════════════

def register_training_agreement_routes(app):
    """
    Register Flask route สำหรับ Training Agreement endpoint

    Endpoint: POST /generate_training_agreement
    Headers: X-API-Key (required ถ้าตั้งใน Render env)
    Body: JSON payload จาก GAS — ดู _build_training_html() สำหรับ keys ที่ใช้

    Returns:
        success: { success: True, pdfBase64, fileName }
        failure: { success: False, message } + HTTP 400/500
    """
    @app.route('/generate_training_agreement', methods=['POST'])
    def api_generate_training_agreement():
        try:
            from app import _check_key, _safe_error
            err = _check_key()
            if err: return err

            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'No JSON body'}), 400

            html = _build_training_html(data)
            content_bytes = html_to_pdf(html)
            entity_key = data.get('entityKey', '')
            pdf_bytes = merge_multi_page(content_bytes, entity_key)
            pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

            # Sanitize filename — keep ASCII + Thai + safe chars only
            emp = (data.get('employeeName', '') or 'training')[:30]
            safe_name = ''.join(
                ch for ch in emp
                if ch.isalnum() or ch in '_- ' or '฀' <= ch <= '๿'
            ).strip() or 'training'

            return jsonify({
                'success': True,
                'pdfBase64': pdf_b64,
                'fileName': f'สัญญาฝึกอบรม_{safe_name}.pdf',
            })
        except Exception as e:
            logger.error(f'generate_training_agreement error: {e}')
            from app import _safe_error
            return jsonify(_safe_error(e, 'generate_training_agreement')), 500
