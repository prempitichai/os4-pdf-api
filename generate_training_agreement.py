#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: v4-s12
"""
generate_training_agreement.py — สัญญาเข้าศึกษา / ฝึกอบรม / สอบ
═══════════════════════════════════════════════════════════════════
ใช้ template_utils (WeasyPrint + entity template overlay)

★ S12 v4 changes (จากต้นฉบับ SCM Technologies):
  - Layout มีกรอบ outer frame (border 1.2pt)
  - Font 9.5pt (ลดจาก 10.5pt) — เนื้อหาพอดี 2 หน้า
  - ข้อ 4 เงื่อนไข (1)(2) ใช้ 60,000 ตามต้นฉบับ
  - ลายเซ็น 3 แถว ใน sig box (border + rounded + พื้นสี):
    แถว 1: กรรมการ/นายจ้าง 1 | กรรมการ/นายจ้าง 2 (ถ้ามี)
    แถว 2: พนักงาน | หัวหน้างาน
    แถว 3: พยาน 1 | พยาน 2
  - Field table จัด 4 คอลัมน์สวย
  - ข้อสัญญา numbered list ชัดเจน
  - @page margin override ให้ WeasyPrint ตัดหน้าถูกต้อง
"""

import base64
import logging
from flask import request, jsonify
from template_utils import (
    merge_on_template, html_to_pdf, build_css, build_html
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


# ══════════════════════════════════════════════════════════════════════
# CSS — กรอบ outer frame + font 9.5pt
# ══════════════════════════════════════════════════════════════════════

def _build_training_css():
    """CSS สำหรับสัญญาฝึกอบรม — มีกรอบ + font เล็กลง"""
    return """
    /* ── Override page layout จาก build_css() ── */
    @page { size: A4; margin: 30mm 18mm 20mm 22mm; }
    .page { width: auto; min-height: auto; padding: 0; }

    /* ── Outer frame — กรอบรอบเอกสาร ── */
    .ta-frame { border: 1.2pt solid #1a1a1a; padding: 5mm 6mm; }

    /* ── Title ── */
    .ta-title {
        font-size: 13pt;
        font-weight: bold;
        text-align: center;
        margin: 0 0 4mm;
        text-decoration: underline;
        letter-spacing: 0.5pt;
    }

    /* ── หลักสูตร ── */
    .ta-course {
        font-size: 9.5pt;
        margin-bottom: 3mm;
        padding: 2mm 0;
        border-bottom: 0.5pt solid #ddd;
    }
    .ta-course b { color: #222; }

    /* ── Intro paragraph ── */
    .ta-intro {
        font-size: 9.5pt;
        text-align: justify;
        line-height: 1.6;
        text-indent: 10mm;
        margin-bottom: 2.5mm;
    }

    /* ── Field table (ข้อมูลพนักงาน) ── */
    .ta-fields { width: 100%; border-collapse: collapse; margin-bottom: 2.5mm; font-size: 9.5pt; }
    .ta-fields td { padding: 1mm 2mm; border: none; vertical-align: bottom; }
    .ta-fields .lbl { font-weight: bold; white-space: nowrap; color: #222; }
    .ta-fields .val { border-bottom: 0.5pt dotted #888; min-width: 15mm; }

    /* ── "ทั้งสองฝ่าย..." ── */
    .ta-parties {
        font-weight: bold;
        text-decoration: underline;
        font-size: 9.5pt;
        margin: 3mm 0 2mm;
    }

    /* ── ข้อสัญญา (Clause) ── */
    .ta-cl {
        font-size: 9.5pt;
        text-align: justify;
        line-height: 1.6;
        margin-bottom: 2.5mm;
    }
    .ta-cl-t { font-weight: bold; text-indent: 10mm; }

    /* ── Sub items (เงื่อนไขข้อ 4) ── */
    .ta-sub {
        margin-left: 14mm;
        margin-bottom: 2mm;
        font-size: 9.5pt;
        line-height: 1.6;
        text-align: justify;
    }
    .ta-sub-item { display: flex; gap: 2mm; margin-bottom: 1.5mm; }
    .ta-sub-item .n { flex-shrink: 0; width: 8mm; text-align: center; font-weight: bold; }
    .ta-sub-item .t { flex: 1; }

    /* ── ข้อความปิดท้าย ── */
    .ta-closing {
        font-size: 9.5pt;
        text-align: justify;
        line-height: 1.6;
        text-indent: 10mm;
        margin-bottom: 2.5mm;
    }

    /* ── ลายเซ็น (sig box มี border + rounded) ── */
    .ta-sig-area { margin-top: 8mm; border-top: 0.5pt solid #ccc; padding-top: 4mm; }
    .ta-sig-row { display: flex; justify-content: space-between; margin-bottom: 5mm; }
    .ta-sig-box {
        width: 47%;
        text-align: center;
        padding: 3mm 2mm;
        border: 0.5pt solid #ddd;
        border-radius: 3pt;
        background: #fafafa;
    }
    .ta-sig-pre { font-size: 9pt; color: #666; margin-bottom: 0.5mm; }
    .ta-sig-dots {
        border-bottom: 0.5pt dotted #333;
        width: 45mm;
        margin: 0 auto 1mm;
        height: 9mm;
    }
    .ta-sig-lbl { font-size: 9pt; color: #444; }
    .ta-sig-nm { font-size: 10pt; }
    """


# ══════════════════════════════════════════════════════════════════════
# SIGNATURE BUILDER
# ══════════════════════════════════════════════════════════════════════

def _sig_box(label, name):
    """สร้าง sig box 1 ช่อง (มี border + rounded)"""
    e = _esc
    name_display = f'({e(name)})' if name else '(....................................................................)'
    return f'''<div class="ta-sig-box">
      <div class="ta-sig-pre">ลงชื่อ</div>
      <div class="ta-sig-dots"></div>
      <div class="ta-sig-lbl">{label}</div>
      <div class="ta-sig-nm">{name_display}</div>
    </div>'''


def _sig_empty():
    """สร้าง sig box ว่าง (ไม่มี border)"""
    return '<div class="ta-sig-box" style="border:none;background:transparent"></div>'


def _build_sig_html(data):
    """สร้าง signature section — 3 แถว
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

    html = '<div class="ta-sig-area">'

    # แถว 1: กรรมการ 1 | กรรมการ 2
    html += '<div class="ta-sig-row">'
    html += _sig_box('นายจ้าง/บริษัทฯ', co_signer1)
    if co_signer2:
        html += _sig_box('นายจ้าง/บริษัทฯ (คนที่ 2)', co_signer2)
    else:
        html += _sig_empty()
    html += '</div>'

    # แถว 2: พนักงาน | หัวหน้างาน
    html += '<div class="ta-sig-row">'
    html += _sig_box('พนักงาน', emp_signer)
    html += _sig_box('หัวหน้างาน', supervisor)
    html += '</div>'

    # แถว 3: พยาน 1 | พยาน 2
    html += '<div class="ta-sig-row">'
    html += _sig_box('พยาน', witness1)
    html += _sig_box('พยาน', witness2)
    html += '</div>'

    html += '</div>'
    return html


# ══════════════════════════════════════════════════════════════════════
# HTML BUILDER
# ══════════════════════════════════════════════════════════════════════

def _build_training_html(data):
    """สร้าง HTML สัญญาฝึกอบรม — single flow + กรอบ outer frame"""
    e = _esc

    # ── ดึงข้อมูลจาก data ──
    doc_number = e(data.get('docNumber', ''))
    company    = e(data.get('companyName', ''))
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

    # ── สร้าง CSS + sig HTML ──
    css = build_css() + _build_training_css()
    sig_html = _build_sig_html(data)

    # ════════════════════════════════════════════
    # HTML Content — single flow + outer frame
    # ════════════════════════════════════════════
    content = f"""<div class="page">
  <div class="doc-number" style="margin-bottom:4mm">{doc_number}</div>
  <div class="ta-frame">
    <div class="ta-title">สัญญาเข้าศึกษา / ฝึกอบรม / สอบ</div>
    <div class="ta-course"><b>หลักสูตร :</b> {course}</div>

    <p class="ta-intro">สัญญาฉบับนี้ทำขึ้นเมื่อวันที่ {c_date} เดือน {c_month} พ.ศ. {c_year} ระหว่าง {company} {company_addr} ซึ่งต่อไปนี้เรียกว่า <b>"บริษัทฯ"</b> ฝ่ายหนึ่งกับ</p>

    <table class="ta-fields">
      <tr>
        <td class="lbl">นาย / นาง / นางสาว</td>
        <td class="val">{emp_name}</td>
        <td class="lbl">ตำแหน่ง</td>
        <td class="val">{emp_pos}</td>
      </tr>
      <tr>
        <td class="lbl">แผนก</td>
        <td class="val">{emp_dept}</td>
        <td class="lbl">อายุ</td>
        <td class="val" style="max-width:12mm">{emp_age}</td>
      </tr>
      <tr>
        <td class="lbl">เลขประจำตัวประชาชน</td>
        <td class="val" colspan="3">{emp_id}</td>
      </tr>
      <tr>
        <td class="lbl">ที่อยู่</td>
        <td class="val" colspan="3">{emp_addr}</td>
      </tr>
    </table>

    <p class="ta-intro" style="margin-top:1mm">ซึ่งต่อไปในสัญญาจะเรียกว่า <b>"พนักงาน"</b> อีกฝ่ายหนึ่ง</p>
    <div class="ta-parties">ทั้งสองฝ่ายจึงได้ตกลงกันดังต่อไปนี้</div>

    <p class="ta-cl"><span class="ta-cl-t">ข้อ 1.</span> บริษัทฯ จะส่งพนักงานไปศึกษา / ฝึกอบรม / สอบตามหลักสูตร ในวันที่ {t_date} เดือน {t_month} พ.ศ. {t_year} โดยบริษัทฯ จะรับผิดชอบค่าใช้จ่ายเกี่ยวกับการฝึกอบรมในครั้งนี้เป็นจำนวนเงิน {t_cost} บาท ({t_cost_txt}) ทั้งนี้ ค่าใช้จ่ายดังกล่าวไม่เกี่ยวข้องกับเงินเดือนที่พนักงานได้รับจากบริษัทฯ</p>

    <p class="ta-cl"><span class="ta-cl-t">ข้อ 2.</span> พนักงานยินยอมที่จะเข้ารับการศึกษา / ฝึกอบรม / สอบตามหลักสูตร ดังที่ระบุไว้ในข้อ 1. โดยจะไม่ใช้เวลาทำงานของบริษัทฯ เพื่อกิจธุระแห่งการศึกษา / ฝึกอบรมนั้น ยกเว้นกรณีที่หัวข้อฝึกอบรมนั้น ๆ ถูกจัดขึ้นแค่ตรงกับเวลาทำงานของพนักงานตามที่บริษัทฯ จัดไว้ ทั้งนี้พนักงานจะต้องได้รับการอนุมัติจากบริษัทฯ แล้วเท่านั้น</p>

    <p class="ta-cl"><span class="ta-cl-t">ข้อ 3.</span> พนักงานยอมรับว่าเมื่อจบการศึกษาหรือการฝึกอบรมดังกล่าวแล้ว พนักงานจะอยู่ปฏิบัติงานให้แก่บริษัทฯ และจะนำความรู้ ความสามารถ และประสบการณ์ที่ได้จากการฝึกอบรมมาใช้เพื่อให้เกิดประโยชน์แก่บริษัทฯ พร้อมทั้งถ่ายทอดความรู้ ความสามารถ และประสบการณ์ที่ได้รับมาให้แก่พนักงานอื่นของบริษัทฯ นับแต่วันที่จบหลักสูตร</p>

    <p class="ta-cl"><span class="ta-cl-t">ข้อ 4.</span> พนักงานยอมรับว่าหากบริษัทฯ ส่งพนักงานไปศึกษา / ฝึกอบรม / สอบตามหลักสูตร ตามที่ระบุไว้ในข้อ 1. แล้วพนักงานไม่สามารถเข้ารับการศึกษา / ฝึกอบรมได้จนจบหลักสูตร หรือไม่สามารถอยู่ปฏิบัติงานกับบริษัทฯ ตามระยะเวลาที่กำหนดได้ ไม่ว่าด้วยเหตุใด ๆ อันเนื่องมาจากตัวพนักงานเอง พนักงานยินยอมชดใช้ค่าใช้จ่ายหรือค่าตอบแทนให้แก่บริษัทฯ ตามเงื่อนไขดังต่อไปนี้</p>
    <div class="ta-sub">
      <div class="ta-sub-item"><span class="n">(1)</span><span class="t">สำหรับหลักสูตรที่มีค่าใช้จ่ายไม่เกิน 60,000.00 (หกหมื่น) บาทต่อ 1 (หนึ่ง) หลักสูตร พนักงานจะต้องอยู่ปฏิบัติงานกับบริษัทฯ เป็นระยะเวลาอย่างน้อย 6 (หก) เดือน นับตั้งแต่วันที่จบหลักสูตร หากไม่สามารถอยู่ปฏิบัติงานกับบริษัทฯ ได้ครบกำหนด 6 (หก) เดือน พนักงานยินยอมชดเชยค่าใช้จ่ายคิดเป็น 100 (หนึ่งร้อย) % ของค่าใช้จ่ายที่เกิดขึ้น</span></div>
      <div class="ta-sub-item"><span class="n">(2)</span><span class="t">สำหรับหลักสูตรที่มีค่าใช้จ่ายตั้งแต่ 60,000 (หกหมื่น) บาทขึ้นไปต่อ 1 (หนึ่ง) หลักสูตร พนักงานจะต้องอยู่ปฏิบัติงานกับบริษัทฯ เป็นระยะเวลาอย่างน้อย 1 (หนึ่ง) ปี นับตั้งแต่วันที่จบหลักสูตร หากไม่สามารถอยู่ปฏิบัติงานกับบริษัทฯ ได้ครบ 1 (หนึ่ง) ปี พนักงานยินยอมชดเชยค่าใช้จ่ายคิดเป็น 100 (หนึ่งร้อย) % ของค่าใช้จ่ายที่เกิดขึ้น</span></div>
    </div>

    <p class="ta-cl"><span class="ta-cl-t">ข้อ 5.</span> ในช่วงระหว่างที่ยังศึกษา / ฝึกอบรม / สอบ ไม่จบหลักสูตร หากพนักงานกระทำความผิดใด ๆ เป็นเหตุให้ได้รับโทษจำคุกหรือถูกเนรเทศ หรือได้รับโทษอื่นใดตามกฎหมาย ทำให้พนักงานไม่สามารถเข้ารับการศึกษา / ฝึกอบรมครบตามกำหนดระยะเวลาได้ พนักงานยินยอมชดใช้ค่าเสียหายให้แก่บริษัทฯ เท่ากับจำนวนที่ระบุไว้ในข้อ 4.</p>

    <p class="ta-cl"><span class="ta-cl-t">ข้อ 6.</span> ในระหว่างที่พนักงานทำงานให้แก่บริษัทฯ ตามกำหนดระยะเวลาในข้อ 3. หากพนักงานกระทำการใด ๆ อันฝ่าฝืนกฎระเบียบ ประกาศ คำสั่ง หรือข้อบังคับของบริษัทฯ อันเป็นผลให้พนักงานถูกลงโทษทางวินัยถึงขั้นให้ออก ปลดออก แล้วแต่กรณี ให้ถือว่าพนักงานไม่สามารถทำงานให้แก่บริษัทฯ ได้และยินยอมชดใช้ค่าเสียหายหรือค่าตอบแทนให้แก่บริษัทฯ ตามจำนวนที่ระบุไว้ในข้อ 4.</p>

    <p class="ta-cl"><span class="ta-cl-t">ข้อ 7.</span> บริษัทฯ จะจ่ายเงินเดือนให้แก่พนักงานในช่วงระหว่างระยะเวลาที่พนักงานศึกษา / ฝึกอบรม / สอบ ตามที่ได้ตกลงกันและตามระเบียบของบริษัทฯ</p>

    <p class="ta-cl"><span class="ta-cl-t">ข้อ 8.</span> ในกรณีที่บริษัทฯ ได้ส่งพนักงานไปศึกษา / ฝึกอบรม / สอบตามหลักสูตร หรือค่าใช้จ่ายใด ๆ ที่เกิดขึ้นก็ตาม หากพนักงานไม่ดำเนินการไปศึกษา / ฝึกอบรม / สอบ ตามหลักสูตร ที่ตกลงไว้ ไม่ว่าด้วยเหตุใด ๆ ก็ตาม พนักงานยินยอมชดใช้ค่าใช้จ่ายต่าง ๆ ทั้งหมดที่ได้ระบุไว้ในสัญญานี้ โดยพนักงานตกลงชำระให้แก่บริษัทฯ ภายใน 30 (สามสิบ) วัน นับตั้งแต่วันที่พนักงานไม่ได้ปฏิบัติตามที่ตกลงไว้</p>

    <p class="ta-cl"><span class="ta-cl-t">ข้อ 9.</span> พนักงานยินยอมให้บริษัทฯ หักค่าชดใช้ใด ๆ ที่พนักงานทำผิดสัญญาและจากจำนวนเงินใด ๆ ที่พนักงานได้ผิดนัดชำระกับบริษัทฯ จากค่าจ้างที่พนักงานได้รับจากบริษัทฯ</p>

    <p class="ta-closing">อนึ่งการที่บริษัทฯ ไม่ใช้สิทธิหรือประวิงการใช้สิทธิ หรืออำนาจใด ๆ ตามที่ระบุไว้ในสัญญานี้ในครั้งหนึ่งครั้งใด ไม่ถือว่าเป็นการที่บริษัทฯ สละสิทธิในเรื่องดังกล่าวต่อไป</p>

    <p class="ta-closing">สัญญานี้ทำขึ้น 2 (สอง) ฉบับ คู่สัญญาทั้งสองฝ่ายได้อ่านและเข้าใจข้อความและเงื่อนไขต่าง ๆ แห่งสัญญาฉบับนี้โดยละเอียดตลอดครบถ้วนแล้ว เห็นว่าถูกต้องตามเจตนาทุกประการเพื่อเป็นหลักฐานจึงได้ลงลายมือชื่อ และประทับตรา (ถ้ามี) ไว้เป็นสำคัญและคู่สัญญาต่างยึดถือไว้ฝ่ายละหนึ่งฉบับ</p>

    {sig_html}
  </div>
</div>"""

    return build_html(css, content)


# ══════════════════════════════════════════════════════════════════════
# PDF MERGE — overlay ทุกหน้าบน entity template
# ══════════════════════════════════════════════════════════════════════

def _merge_multi_page(content_bytes, entity_key):
    """Overlay ทุกหน้าของ content บน entity template
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

def register_training_agreement_routes(app):
    """ลงทะเบียน route /generate_training_agreement"""

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

            # สร้าง HTML → PDF → overlay บน template
            html = _build_training_html(data)
            content_bytes = html_to_pdf(html)

            entity_key = data.get('entityKey', '')
            pdf_bytes = _merge_multi_page(content_bytes, entity_key)
            pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

            # สร้างชื่อไฟล์ปลอดภัย
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
