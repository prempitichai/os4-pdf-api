#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: v7-s15
"""
generate_training_agreement.py — สัญญาเข้าศึกษา / ฝึกอบรม / สอบ
═══════════════════════════════════════════════════════════════════

★ S15 v7 changes:
  - [FIX] doc-number แสดงทุกหน้า
  - [FIX] sig เปลี่ยนจาก flex div → table (เหมือน WL)
  - [FIX] sig: ไม่มีชื่อ → ไม่ใส่จุด (....), มีชื่อ → แสดงชื่อเลย
  - [FIX] หน้า 2 เพิ่ม margin-top ข้อ 7 ไม่ชิดบน
  - [FIX] layout ทั้งฉบับ — spacing, padding
  - @font-face embed THSarabunNew + margin-top 17mm
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
    return (str(s or '').replace('&','&amp;').replace('<','&lt;')
            .replace('>','&gt;').replace('"','&quot;'))


# ══════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════

def _build_training_css():
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
        font-size: 9.5pt;
        color: #000;
        line-height: 1.5;
    }
    .page { width: auto; min-height: auto; padding: 0; }
    .doc-number { font-size: 10pt; margin-bottom: 4mm; color: #333; }
    .ta-tbl { width: 100%; border-collapse: collapse; border: 1.2pt solid #1a1a1a; }
    .ta-tbl td { border: 0.8pt solid #444; padding: 0; vertical-align: top; }
    .ta-hdr { background: #f0f4f8; text-align: center; padding: 7mm 10mm 6mm; }
    .ta-content { padding: 6mm 10mm 6mm; font-size: 9.5pt; line-height: 1.5; }
    .ta-title { font-size: 13pt; font-weight: bold; text-decoration: underline; letter-spacing: 0.5pt; color: #1a1a1a; }
    .ta-course { font-size: 9.5pt; margin-bottom: 3mm; padding: 2mm 0; border-bottom: 0.5pt solid #ddd; }
    .ta-course b { color: #222; }
    .ta-intro { font-size: 9.5pt; text-align: left; line-height: 1.5; text-indent: 10mm; margin-bottom: 2.5mm; word-wrap: break-word; }
    .ta-fields { width: 100%; border-collapse: collapse; margin-bottom: 2.5mm; font-size: 9.5pt; }
    .ta-fields td { padding: 1mm 2mm; border: none; vertical-align: bottom; }
    .ta-fields .lbl { font-weight: bold; white-space: nowrap; color: #222; }
    .ta-fields .val { border-bottom: 0.5pt dotted #888; min-width: 15mm; }
    .ta-parties { font-weight: bold; text-decoration: underline; font-size: 9.5pt; margin: 3mm 0 2mm; }
    .ta-cl { font-size: 9.5pt; text-align: left; line-height: 1.5; margin-bottom: 3mm; word-wrap: break-word; }
    .ta-cl-t { font-weight: bold; text-indent: 10mm; }
    .ta-sub { margin-left: 14mm; margin-bottom: 3mm; font-size: 9.5pt; line-height: 1.5; text-align: left; word-wrap: break-word; }
    .ta-sub-item { display: flex; gap: 2mm; margin-bottom: 2mm; }
    .ta-sub-item .n { flex-shrink: 0; width: 8mm; text-align: center; font-weight: bold; }
    .ta-sub-item .t { flex: 1; }
    .ta-closing { font-size: 9.5pt; text-align: left; line-height: 1.5; text-indent: 10mm; margin-bottom: 3mm; word-wrap: break-word; }
    /* ★ v7: sig ใช้ tr rows ใน ta-tbl เหมือน WL */
    .ta-sig td { padding: 4mm 3mm; text-align: center; vertical-align: top; width: 50%; }
    .ta-sig-line { border-bottom: 0.5pt dotted #333; width: 50mm; margin: 0 auto 1.5mm; height: 10mm; }
    .ta-sig-lbl { font-size: 9.5pt; color: #333; }
    .ta-sig-nm { font-size: 10pt; }
    .ta-sig-pre { font-size: 9pt; color: #666; margin-bottom: 0.5mm; }
    """


# ══════════════════════════════════════════════════════════════════════
# SIGNATURE — ★ v7: table layout เหมือน WL + ไม่มีจุด
# ══════════════════════════════════════════════════════════════════════

def _sig_cell(label, name):
    e = _esc
    nm_html = f'<div class="ta-sig-nm">({e(name)})</div>' if name else ''
    return f'<td><div class="ta-sig-pre">ลงชื่อ</div><div class="ta-sig-line"></div><div class="ta-sig-lbl">{label}</div>{nm_html}</td>'

def _build_sig_html(data):
    co1 = data.get('companySignerName', '')
    co2 = data.get('companySignerName2', '')
    emp = data.get('employeeSignerName', data.get('employeeName', ''))
    sup = data.get('supervisorName', '')
    w1  = data.get('witness1Name', '')
    w2  = data.get('witness2Name', '')
    # ★ v7-s15: ใช้ <tr> rows ตรงๆ (อยู่ใน ta-tbl แล้ว)
    h = '<tr class="ta-sig">' + _sig_cell('นายจ้าง/บริษัทฯ', co1)
    h += _sig_cell('นายจ้าง/บริษัทฯ (คนที่ 2)', co2) if co2 else '<td></td>'
    h += '</tr><tr class="ta-sig">' + _sig_cell('พนักงาน', emp) + _sig_cell('หัวหน้างาน', sup)
    h += '</tr><tr class="ta-sig">' + _sig_cell('พยาน', w1) + _sig_cell('พยาน', w2) + '</tr>'
    return h


# ══════════════════════════════════════════════════════════════════════
# HTML BUILDER
# ══════════════════════════════════════════════════════════════════════

def _build_training_html(data):
    e = _esc
    doc_number   = e(data.get('docNumber', ''))
    company      = e(data.get('companyName', ''))
    company_addr = e(data.get('companyAddress', ''))
    emp_name     = e(data.get('employeeName', ''))
    emp_pos      = e(data.get('employeePosition', ''))
    emp_dept     = e(data.get('employeeDepartment', ''))
    emp_age      = e(data.get('employeeAge', ''))
    emp_id       = e(data.get('employeeIdCard', ''))
    emp_addr     = e(data.get('employeeAddress', ''))
    course       = e(data.get('courseName', ''))
    t_date       = e(data.get('trainingDate', ''))
    t_month      = e(data.get('trainingMonth', ''))
    t_year       = e(data.get('trainingYear', ''))
    t_cost       = e(data.get('trainingCost', ''))
    t_cost_txt   = e(data.get('trainingCostText', ''))
    c_date       = e(data.get('contractDate', ''))
    c_month      = e(data.get('contractMonth', ''))
    c_year       = e(data.get('contractYear', ''))

    css = _build_training_css()
    sig_html = _build_sig_html(data)

    content = f"""<div class="page">
  <div class="doc-number">{doc_number}</div>
  <table class="ta-tbl">
    <tr><td colspan="2" class="ta-hdr">
      <div class="ta-title">สัญญาเข้าศึกษา / ฝึกอบรม / สอบ</div>
    </td></tr>
    <tr><td colspan="2" class="ta-content">
    <div class="ta-course"><b>หลักสูตร :</b> {course}</div>
    <p class="ta-intro">สัญญาฉบับนี้ทำขึ้นเมื่อวันที่ {c_date} เดือน {c_month} พ.ศ. {c_year} ระหว่าง {company} {company_addr} ซึ่งต่อไปนี้เรียกว่า <b>"บริษัทฯ"</b> ฝ่ายหนึ่งกับ</p>
    <table class="ta-fields">
      <tr><td class="lbl">นาย / นาง / นางสาว</td><td class="val">{emp_name}</td><td class="lbl">ตำแหน่ง</td><td class="val">{emp_pos}</td></tr>
      <tr><td class="lbl">แผนก</td><td class="val">{emp_dept}</td><td class="lbl">อายุ</td><td class="val" style="max-width:12mm">{emp_age}</td></tr>
      <tr><td class="lbl">เลขประจำตัวประชาชน</td><td class="val" colspan="3">{emp_id}</td></tr>
      <tr><td class="lbl">ที่อยู่</td><td class="val" colspan="3">{emp_addr}</td></tr>
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
    </td></tr>
  </table>
  <div style="page-break-before:always"></div>
  <div class="doc-number">{doc_number}</div>
  <table class="ta-tbl">
    <tr><td colspan="2" class="ta-content" style="padding-top:10mm">
    <p class="ta-cl"><span class="ta-cl-t">ข้อ 7.</span> บริษัทฯ จะจ่ายเงินเดือนให้แก่พนักงานในช่วงระหว่างระยะเวลาที่พนักงานศึกษา / ฝึกอบรม / สอบ ตามที่ได้ตกลงกันและตามระเบียบของบริษัทฯ</p>
    <p class="ta-cl"><span class="ta-cl-t">ข้อ 8.</span> ในกรณีที่บริษัทฯ ได้ส่งพนักงานไปศึกษา / ฝึกอบรม / สอบตามหลักสูตร หรือค่าใช้จ่ายใด ๆ ที่เกิดขึ้นก็ตาม หากพนักงานไม่ดำเนินการไปศึกษา / ฝึกอบรม / สอบ ตามหลักสูตร ที่ตกลงไว้ ไม่ว่าด้วยเหตุใด ๆ ก็ตาม พนักงานยินยอมชดใช้ค่าใช้จ่ายต่าง ๆ ทั้งหมดที่ได้ระบุไว้ในสัญญานี้ โดยพนักงานตกลงชำระให้แก่บริษัทฯ ภายใน 30 (สามสิบ) วัน นับตั้งแต่วันที่พนักงานไม่ได้ปฏิบัติตามที่ตกลงไว้</p>
    <p class="ta-cl"><span class="ta-cl-t">ข้อ 9.</span> พนักงานยินยอมให้บริษัทฯ หักค่าชดใช้ใด ๆ ที่พนักงานทำผิดสัญญาและจากจำนวนเงินใด ๆ ที่พนักงานได้ผิดนัดชำระกับบริษัทฯ จากค่าจ้างที่พนักงานได้รับจากบริษัทฯ</p>
    <p class="ta-closing">อนึ่งการที่บริษัทฯ ไม่ใช้สิทธิหรือประวิงการใช้สิทธิ หรืออำนาจใด ๆ ตามที่ระบุไว้ในสัญญานี้ในครั้งหนึ่งครั้งใด ไม่ถือว่าเป็นการที่บริษัทฯ สละสิทธิในเรื่องดังกล่าวต่อไป</p>
    <p class="ta-closing">สัญญานี้ทำขึ้น 2 (สอง) ฉบับ คู่สัญญาทั้งสองฝ่ายได้อ่านและเข้าใจข้อความและเงื่อนไขต่าง ๆ แห่งสัญญาฉบับนี้โดยละเอียดตลอดครบถ้วนแล้ว เห็นว่าถูกต้องตามเจตนาทุกประการเพื่อเป็นหลักฐานจึงได้ลงลายมือชื่อ และประทับตรา (ถ้ามี) ไว้เป็นสำคัญและคู่สัญญาต่างยึดถือไว้ฝ่ายละหนึ่งฉบับ</p>
    </td></tr>
    {sig_html}
  </table>
</div>"""
    return build_html(css, content)


# ══════════════════════════════════════════════════════════════════════
# PDF MERGE
# ══════════════════════════════════════════════════════════════════════

def _merge_multi_page(content_bytes, entity_key):
    """Overlay ทุกหน้าของ content บน entity template"""
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
        return content_bytes

    content_reader = PdfReader(BytesIO(content_bytes))
    writer = PdfWriter()

    for page in content_reader.pages:
        tpl_reader = PdfReader(tpl_path)
        bg = tpl_reader.pages[0]

        # ★ v7-s15 FIX: rename font ใน CONTENT (ไม่ใช่ template)
        content_fonts = page.get("/Resources", {}).get("/Font", {})
        for key in list(content_fonts.keys()):
            try:
                font_obj = content_fonts[key].get_object()
                base_font = str(font_obj.get("/BaseFont", ""))
                if "THSarabunNew" in base_font and "CTN" not in base_font:
                    new_bf = base_font.replace("THSarabunNew", "THSarabunNewCTN")
                    font_obj[NameObject("/BaseFont")] = NameObject("/" + new_bf.lstrip("/"))
                    if "/DescendantFonts" in font_obj:
                        desc_arr = font_obj["/DescendantFonts"]
                        for desc_ref in desc_arr:
                            desc = desc_ref.get_object()
                            dbf = str(desc.get("/BaseFont", ""))
                            if "THSarabunNew" in dbf and "CTN" not in dbf:
                                desc[NameObject("/BaseFont")] = NameObject("/" + dbf.replace("THSarabunNew", "THSarabunNewCTN").lstrip("/"))
                            if "/FontDescriptor" in desc:
                                fd = desc["/FontDescriptor"].get_object()
                                fn = str(fd.get("/FontName", ""))
                                if "THSarabunNew" in fn and "CTN" not in fn:
                                    fd[NameObject("/FontName")] = NameObject("/" + fn.replace("THSarabunNew", "THSarabunNewCTN").lstrip("/"))
                    if "/FontDescriptor" in font_obj:
                        fd = font_obj["/FontDescriptor"].get_object()
                        fn = str(fd.get("/FontName", ""))
                        if "THSarabunNew" in fn and "CTN" not in fn:
                            fd[NameObject("/FontName")] = NameObject("/" + fn.replace("THSarabunNew", "THSarabunNewCTN").lstrip("/"))
            except Exception:
                pass

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
            if err: return err

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
