#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: v1
"""
generate_training_agreement.py — สัญญาเข้าศึกษา / ฝึกอบรม / สอบ
═══════════════════════════════════════════════════════════════════
ใช้ template_utils (WeasyPrint + entity template overlay) — 2 หน้า

POST /generate_training_agreement
  Input: {
    entityKey,            — entity template (logo+watermark)
    docNumber,            — เลขที่สัญญา
    companyName,          — ชื่อบริษัท
    companyAddress,       — ที่อยู่บริษัท
    employeeName,         — ชื่อพนักงาน
    employeePosition,     — ตำแหน่ง
    employeeDepartment,   — แผนก
    employeeAge,          — อายุ
    employeeIdCard,       — เลขประจำตัวประชาชน
    employeeAddress,      — ที่อยู่พนักงาน
    courseName,           — หลักสูตร
    trainingDate,         — วันที่ฝึกอบรม
    trainingMonth,        — เดือน
    trainingYear,         — พ.ศ.
    trainingCost,         — ค่าใช้จ่าย (บาท)
    trainingCostText,     — ค่าใช้จ่าย (ตัวอักษร)
    contractDate,         — วันที่ทำสัญญา
    contractMonth,        — เดือนทำสัญญา
    contractYear,         — พ.ศ.ทำสัญญา
    employeeSignerName,   — ชื่อพนักงาน (ลงนาม)
    companySignerName,    — ชื่อนายจ้าง/บริษัท (ลงนาม)
    witness1Name,         — พยานคนที่ 1
    witness2Name,         — พยานคนที่ 2
  }
  Output: { success, pdfBase64, fileName }
"""

import base64
import logging
from flask import request, jsonify
from template_utils import (
    merge_on_template, html_to_pdf, build_css, build_html
)

logger = logging.getLogger(__name__)


def _esc(s):
    return (str(s or '')
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def _build_training_css():
    """CSS เพิ่มเติมสำหรับสัญญาฝึกอบรม"""
    return """
    /* ── Training Agreement specific ── */
    .ta-title { font-size: 13pt; font-weight: bold; text-align: center; margin-bottom: 6mm; text-decoration: underline; }
    .ta-course { font-size: 10pt; margin-bottom: 4mm; }
    .ta-course-label { font-weight: bold; }
    .ta-intro { font-size: 10pt; text-align: justify; line-height: 1.7; text-indent: 12mm; margin-bottom: 4mm; }
    .ta-field-row { display: flex; gap: 2mm; font-size: 10pt; line-height: 1.7; flex-wrap: wrap; margin-bottom: 1mm; }
    .ta-field-label { white-space: nowrap; }
    .ta-field-value { border-bottom: 0.5pt dotted #999; min-width: 15mm; flex: 1; }
    .ta-clause { font-size: 10pt; text-align: justify; line-height: 1.7; margin-bottom: 4mm; }
    .ta-clause-title { font-weight: bold; text-indent: 12mm; }
    .ta-sub { margin-left: 16mm; margin-bottom: 3mm; font-size: 10pt; line-height: 1.7; text-align: justify; }
    .ta-sub-num { display: flex; gap: 2mm; margin-bottom: 2mm; }
    .ta-sub-num .num { flex-shrink: 0; width: 8mm; text-align: center; }
    .ta-sub-num .chk { flex-shrink: 0; width: 8mm; text-align: center; font-size: 12pt; }
    .ta-sub-num .txt { flex: 1; }
    /* ── ลายเซ็น 2x2 grid ── */
    .ta-sig-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8mm; margin-top: 12mm; }
    .ta-sig-box { text-align: center; font-size: 10pt; }
    .ta-sig-line { border-bottom: 0.5pt solid #000; width: 55mm; margin: 0 auto 2mm auto; height: 12mm; }
    .ta-sig-label { font-size: 9pt; margin-bottom: 1mm; }
    .ta-sig-name { font-size: 10pt; }
    """


def _build_training_html(data):
    """สร้าง HTML สัญญาฝึกอบรม 2 หน้า"""
    e = _esc

    doc_number = e(data.get('docNumber', ''))
    company    = e(data.get('companyName', 'บริษัท เอสซีเอ็ม เอส เทคโนโลจีส์ จำกัด'))
    company_addr = e(data.get('companyAddress', ''))
    emp_name   = e(data.get('employeeName', ''))
    emp_pos    = e(data.get('employeePosition', ''))
    emp_dept   = e(data.get('employeeDepartment', ''))
    emp_age    = e(data.get('employeeAge', ''))
    emp_id     = e(data.get('employeeIdCard', ''))
    emp_addr   = e(data.get('employeeAddress', ''))
    course     = e(data.get('courseName', ''))
    t_date     = e(data.get('trainingDate', ''))
    t_month    = e(data.get('trainingMonth', ''))
    t_year     = e(data.get('trainingYear', ''))
    t_cost     = e(data.get('trainingCost', ''))
    t_cost_txt = e(data.get('trainingCostText', ''))
    c_date     = e(data.get('contractDate', ''))
    c_month    = e(data.get('contractMonth', ''))
    c_year     = e(data.get('contractYear', ''))

    emp_signer = e(data.get('employeeSignerName', emp_name))
    co_signer  = e(data.get('companySignerName', ''))
    witness1   = e(data.get('witness1Name', ''))
    witness2   = e(data.get('witness2Name', ''))

    css = build_css() + _build_training_css()

    # ════════════════════════════════════════════
    # หน้า 1
    # ════════════════════════════════════════════
    page1 = f"""<div class="page">
  <div class="doc-number">{doc_number}</div>
  <div class="ta-title">สัญญาเข้าศึกษา / ฝึกอบรม / สอบ</div>

  <div class="ta-course"><span class="ta-course-label">หลักสูตร :</span> {course}</div>

  <p class="ta-intro">สัญญาฉบับนี้ทำขึ้นเมื่อวันที่ {c_date} เดือน {c_month} พ.ศ. {c_year} ระหว่าง {company} {company_addr} ซึ่งต่อไปนี้เรียกว่า <b>"บริษัทฯ"</b> ฝ่ายหนึ่งกับ</p>

  <div class="ta-field-row">
    <span class="ta-field-label">นาย / นาง / นางสาว</span>
    <span class="ta-field-value">{emp_name}</span>
    <span class="ta-field-label">ตำแหน่ง</span>
    <span class="ta-field-value">{emp_pos}</span>
    <span class="ta-field-label">แผนก</span>
    <span class="ta-field-value">{emp_dept}</span>
  </div>
  <div class="ta-field-row">
    <span class="ta-field-label">อายุ</span>
    <span class="ta-field-value" style="max-width:15mm">{emp_age}</span>
    <span class="ta-field-label">ปี เลขประจำตัวประชาชน</span>
    <span class="ta-field-value">{emp_id}</span>
  </div>
  <div class="ta-field-row">
    <span class="ta-field-label">ที่อยู่</span>
    <span class="ta-field-value">{emp_addr}</span>
  </div>
  <p class="ta-intro" style="margin-top:2mm">ซึ่งต่อไปในสัญญาจะเรียกว่า <b>"พนักงาน"</b> อีกฝ่ายหนึ่ง</p>
  <p class="ta-intro" style="font-weight:bold;text-indent:0;text-decoration:underline;margin-top:4mm">ทั้งสองฝ่ายจึงได้ตกลงกันดังต่อไปนี้</p>

  <p class="ta-clause"><span class="ta-clause-title">ข้อ 1.</span> บริษัทฯ จะส่งพนักงานไปศึกษา / ฝึกอบรม / สอบตามหลักสูตร ในวันที่ {t_date} เดือน {t_month} พ.ศ. {t_year} โดยบริษัทฯ จะรับผิดชอบค่าใช้จ่ายเกี่ยวกับการฝึกอบรมในครั้งนี้เป็นจำนวนเงิน {t_cost} บาท ({t_cost_txt}) ทั้งนี้ ค่าใช้จ่ายดังกล่าวไม่เกี่ยวข้องกับเงินเดือนที่พนักงานได้รับจากบริษัทฯ</p>

  <p class="ta-clause"><span class="ta-clause-title">ข้อ 2.</span> พนักงานยินยอมที่จะเข้ารับการศึกษา / ฝึกอบรม / สอบตามหลักสูตร ดังที่ระบุไว้ในข้อ 1. โดยจะไม่ใช้เวลาทำงานของบริษัทฯ เพื่อกิจธุระแห่งการศึกษา / ฝึกอบรมนั้น ยกเว้นกรณีที่หัวข้อฝึกอบรมนั้น ๆ ถูกจัดขึ้นแค่ตรงกับเวลาทำงานของพนักงานตามที่บริษัทฯ จัดไว้ ทั้งนี้พนักงานจะต้องได้รับการอนุมัติจากบริษัทฯ แล้วเท่านั้น</p>

  <p class="ta-clause"><span class="ta-clause-title">ข้อ 3.</span> พนักงานยอมรับว่าเมื่อจบการศึกษาหรือการฝึกอบรมดังกล่าวแล้ว พนักงานจะอยู่ปฏิบัติงานให้แก่บริษัทฯ และจะนำความรู้ ความสามารถ และประสบการณ์ที่ได้จากการฝึกอบรมมาใช้เพื่อให้เกิดประโยชน์แก่บริษัทฯ พร้อมทั้งถ่ายทอดความรู้ความสามารถ และประสบการณ์ที่ได้รับมาให้แก่พนักงานอื่นของบริษัทฯ นับแต่วันที่จบหลักสูตร</p>

  <p class="ta-clause"><span class="ta-clause-title">ข้อ 4.</span> พนักงานยอมรับว่าหากบริษัทฯ ส่งพนักงานไปศึกษา / ฝึกอบรม / สอบตามหลักสูตร ตามที่ระบุไว้ในข้อ 1. แล้วพนักงานไม่สามารถเข้ารับการศึกษา / ฝึกอบรมได้จนจบหลักสูตร หรือไม่สามารถอยู่ปฏิบัติงานกับบริษัทฯ ตามระยะเวลาที่กำหนดได้ ไม่ว่าด้วยเหตุใด ๆ อันเนื่องมาจากตัวพนักงานเอง พนักงานยินยอมชดใช้ค่าใช้จ่ายหรือค่าตอบแทนให้แก่บริษัทฯ ตามเงื่อนไขดังต่อไปนี้</p>

  <div class="ta-sub">
    <div class="ta-sub-num"><span class="num">(1)</span><span class="txt">สำหรับหลักสูตรที่มีค่าใช้จ่ายไม่เกิน 20,000.00 (สองหมื่น) บาทต่อ 1 (หนึ่ง) หลักสูตร พนักงานจะต้องอยู่ปฏิบัติงานกับบริษัทฯ เป็นระยะเวลาอย่างน้อย 6 (หก) เดือน นับตั้งแต่วันที่จบหลักสูตร หากไม่สามารถอยู่ปฏิบัติงานกับบริษัทฯ ได้ครบกำหนด 6 (หก) เดือน พนักงานยินยอมชดเชยค่าใช้จ่ายคิดเป็น 100 (หนึ่งร้อย) % ของค่าใช้จ่ายที่เกิดขึ้น</span></div>
    <div class="ta-sub-num"><span class="num">(2)</span><span class="txt">สำหรับหลักสูตรที่มีค่าใช้จ่ายตั้งแต่ 20,000 (สองหมื่น) บาทขึ้นไปต่อ 1 (หนึ่ง) หลักสูตร พนักงานจะต้องอยู่ปฏิบัติงานกับบริษัทฯ เป็นระยะเวลาอย่างน้อย 1 (หนึ่ง) ปี นับตั้งแต่วันที่จบหลักสูตร หากไม่สามารถอยู่ปฏิบัติงานกับบริษัทฯ ได้ครบ 6 (หก) เดือน พนักงานยินยอมชดเชยค่าใช้จ่ายคิดเป็น 100 (หนึ่งร้อย) % ของค่าใช้จ่ายที่เกิดขึ้น หากอยู่ปฏิบัติงานเกิน 6 (หก) เดือนแต่ไม่ครบ 1 (หนึ่ง) ปี พนักงานยินยอมชดเชยค่าใช้จ่ายคิดเป็น 50 (ห้าสิบ) % ของค่าใช้จ่ายที่เกิดขึ้น</span></div>
    <div class="ta-sub-num"><span class="num">(3)</span><span class="txt">สำหรับหลักสูตรที่มีค่าใช้จ่ายตั้งแต่ 100,000 (หนึ่งแสน) บาทขึ้นไปต่อ 1 (หนึ่ง) หลักสูตร การปฏิบัติตามสัญญานี้ของพนักงานจะต้องมีผู้ค้ำประกัน และอยู่ปฏิบัติงานกับบริษัทฯ เป็นระยะเวลาอย่างน้อย 2 (สอง) ปี นับตั้งแต่วันที่จบหลักสูตร หากไม่สามารถอยู่ปฏิบัติงานได้ครบ 2 (สอง) ปี พนักงานยินยอมชดเชยค่าใช้จ่ายคิดเป็น 100 (หนึ่งร้อย) % ของค่าใช้จ่ายที่เกิดขึ้น</span></div>
  </div>
</div>"""

    # ════════════════════════════════════════════
    # หน้า 2
    # ════════════════════════════════════════════
    page2 = f"""<div class="page">
  <div class="doc-number">{doc_number}</div>

  <p class="ta-clause"><span class="ta-clause-title">ข้อ 5.</span> ในช่วงระหว่างที่ยังศึกษา / ฝึกอบรม / สอบ ไม่จบหลักสูตร หากพนักงานกระทำความผิดใด ๆ เป็นเหตุให้ได้รับโทษจำคุกหรือถูกเนรเทศ หรือได้รับโทษอื่นใดตามกฎหมาย ทำให้พนักงานไม่สามารถเข้ารับการศึกษา / ฝึกอบรมครบตามกำหนดระยะเวลาได้ พนักงานยินยอมชดใช้ค่าเสียหายให้แก่บริษัทฯ เท่ากับจำนวนที่ระบุไว้ในข้อ 4.</p>

  <p class="ta-clause"><span class="ta-clause-title">ข้อ 6.</span> ในระหว่างที่พนักงานทำงานให้แก่บริษัทฯ ตามกำหนดระยะเวลาในข้อ 3. หากพนักงานกระทำการใด ๆ อันฝ่าฝืนกฎระเบียบ ประกาศ คำสั่ง หรือข้อบังคับของบริษัทฯ อันเป็นผลให้พนักงานถูกลงโทษทางวินัยถึงขั้นให้ออก ปลดออก แล้วแต่กรณี ให้ถือว่าพนักงานไม่สามารถทำงานให้แก่บริษัทฯ ได้และยินยอมชดใช้ค่าเสียหายหรือค่าตอบแทนให้แก่บริษัทฯ ตามจำนวนที่ระบุไว้ในข้อ 4.</p>

  <p class="ta-clause"><span class="ta-clause-title">ข้อ 7.</span> บริษัทฯ จะจ่ายเงินเดือนให้แก่พนักงานในช่วงระหว่างระยะเวลาที่พนักงานศึกษา / ฝึกอบรม / สอบ ตามที่ได้ตกลงกันและตามระเบียบของบริษัทฯ</p>

  <p class="ta-clause"><span class="ta-clause-title">ข้อ 8.</span> ในกรณีที่บริษัทฯ ได้ส่งพนักงานไปศึกษา / ฝึกอบรม / สอบตามหลักสูตร หรือค่าใช้จ่ายใด ๆ ที่เกิดขึ้นก็ตาม หากพนักงานไม่ดำเนินการไปศึกษา / ฝึกอบรม / สอบ ตามหลักสูตร ที่ตกลงไว้ ไม่ว่าด้วยเหตุใดๆก็ตาม พนักงานยินยอมชดใช้ค่าใช้จ่ายต่าง ๆ ทั้งหมดที่ได้ระบุไว้ในสัญญานี้ โดยพนักงานตกลงชำระให้แก่บริษัทฯ ภายใน 30 (สามสิบ) วัน นับตั้งแต่วันที่พนักงานไม่ได้ปฏิบัติตามที่ตกลงไว้</p>

  <p class="ta-clause"><span class="ta-clause-title">ข้อ 9.</span> พนักงานยินยอมให้บริษัทฯ หักค่าชดใช้ใด ๆ ที่พนักงานทำผิดสัญญาและจากจำนวนเงินใด ๆ ที่พนักงานได้ผิดนัดชำระกับบริษัทฯ จากค่าจ้างที่พนักงานได้รับจากบริษัทฯ</p>

  <p class="ta-clause" style="text-indent:12mm">อนึ่งการที่บริษัทฯ ไม่ใช้สิทธิหรือประวิงการใช้สิทธิ หรืออำนาจใด ๆ ตามที่ระบุไว้ในสัญญานี้ในครั้งหนึ่งครั้งใด ไม่ถือว่าเป็นการที่บริษัทฯ สละสิทธิในเรื่องดังกล่าวต่อไป</p>

  <p class="ta-clause" style="text-indent:12mm">สัญญานี้ทำขึ้น 2 (สอง) ฉบับ คู่สัญญาทั้งสองฝ่ายได้อ่านและเข้าใจข้อความและเงื่อนไขต่างๆแห่งสัญญาฉบับนี้โดยละเอียดตลอดครบถ้วนแล้ว เห็นว่าถูกต้องตามเจตนาทุกประการเพื่อเป็นหลักฐานจึงได้ลงลายมือชื่อ และประทับตรา (ถ้ามี) ไว้เป็นสำคัญและคู่สัญญาต่างยึดถือไว้ฝ่ายละหนึ่งฉบับ</p>

  <div class="ta-sig-grid">
    <div class="ta-sig-box">
      <div style="font-size:9pt;margin-bottom:1mm">ลงชื่อ</div>
      <div class="ta-sig-line"></div>
      <div class="ta-sig-label">พนักงาน</div>
      <div class="ta-sig-name">({emp_signer})</div>
    </div>
    <div class="ta-sig-box">
      <div style="font-size:9pt;margin-bottom:1mm">ลงชื่อ</div>
      <div class="ta-sig-line"></div>
      <div class="ta-sig-label">นายจ้าง/บริษัทฯ</div>
      <div class="ta-sig-name">({co_signer})</div>
    </div>
    <div class="ta-sig-box">
      <div style="font-size:9pt;margin-bottom:1mm">ลงชื่อ</div>
      <div class="ta-sig-line"></div>
      <div class="ta-sig-label">พยาน</div>
      <div class="ta-sig-name">({witness1})</div>
    </div>
    <div class="ta-sig-box">
      <div style="font-size:9pt;margin-bottom:1mm">ลงชื่อ</div>
      <div class="ta-sig-line"></div>
      <div class="ta-sig-label">พยาน</div>
      <div class="ta-sig-name">({witness2})</div>
    </div>
  </div>
</div>"""

    return build_html(css, page1 + page2)


def _merge_multi_page(content_bytes, entity_key):
    """Overlay ทุกหน้าของ content บน entity template"""
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
    tpl_page = tpl_reader.pages[0]
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

def register_training_agreement_routes(app):
    @app.route('/generate_training_agreement', methods=['POST'])
    def api_generate_training_agreement():
        try:
            from app import _check_key, _safe_error
            err = _check_key()
            if err:
                return err

            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'No JSON body'}), 400

            html = _build_training_html(data)
            content_bytes = html_to_pdf(html)

            entity_key = data.get('entityKey', '')
            pdf_bytes = _merge_multi_page(content_bytes, entity_key)
            pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

            emp = (data.get('employeeName', '') or 'training')[:30]
            safe_name = ''.join(
                ch for ch in emp
                if ch.isalnum() or ch in '_- ' or '\u0e00' <= ch <= '\u0e7f'
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
