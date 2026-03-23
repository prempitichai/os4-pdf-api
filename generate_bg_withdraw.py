#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: weasyprint-overlay-v1
"""
generate_bg_withdraw.py
=======================
Approach:
  1. สร้าง HTML พร้อม CSS justify
  2. WeasyPrint แปลง HTML → PDF (Thai justify สวยงาม)
  3. merge บน bg_template.pdf (header/watermark/footer)
  4. ส่ง PDF base64 กลับ GAS
"""

import os, base64, logging
from io import BytesIO
from flask import request, jsonify
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────────
def _fmt(v):
    if not v: return ''
    try: return f'{float(str(v).replace(",","")),:,.2f}'
    except: return str(v)

def _font_b64():
    """โหลด THSarabunNew เป็น base64 สำหรับ embed ใน CSS"""
    base = os.path.dirname(os.path.abspath(__file__))
    paths = [
        os.path.join(base, 'fonts', 'THSarabunNew.ttf'),
        os.path.join(base, 'fonts', 'THSarabunNew-Bold.ttf'),
    ]
    result = {}
    for p in paths:
        if os.path.exists(p):
            with open(p, 'rb') as f:
                result[os.path.basename(p)] = base64.b64encode(f.read()).decode()
    return result

def _css(fonts):
    """CSS หลัก — TH Sarabun New + A4 + justify"""
    reg_b64  = fonts.get('THSarabunNew.ttf', '')
    bold_b64 = fonts.get('THSarabunNew-Bold.ttf', '')
    font_face = ''
    if reg_b64:
        font_face += f'''
        @font-face {{
            font-family: 'THSarabunNew';
            font-weight: normal;
            src: url('data:font/truetype;base64,{reg_b64}') format('truetype');
        }}'''
    if bold_b64:
        font_face += f'''
        @font-face {{
            font-family: 'THSarabunNew';
            font-weight: bold;
            src: url('data:font/truetype;base64,{bold_b64}') format('truetype');
        }}'''
    return f'''
    {font_face}
    @page {{
        size: A4;
        margin: 0;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
        font-family: 'THSarabunNew', 'TH Sarabun New', serif;
        font-size: 10pt;
        color: #000;
        background: transparent;
    }}
    .page {{
        width: 210mm;
        min-height: 297mm;
        padding: 32mm 20mm 25mm 25mm;
    }}
    .doc-number {{
        font-size: 10pt;
        margin-bottom: 6mm;
    }}
    .title {{
        font-size: 12pt;
        font-weight: bold;
        text-align: center;
        margin-bottom: 8mm;
    }}
    .written-at {{
        font-size: 10pt;
        text-align: right;
        margin-bottom: 6mm;
    }}
    .subject-line {{
        display: flex;
        margin-bottom: 4mm;
    }}
    .subject-label {{
        font-weight: bold;
        min-width: 18mm;
        flex-shrink: 0;
    }}
    .subject-value {{ flex: 1; }}
    .para {{
        font-size: 10pt;
        text-align: justify;
        text-justify: inter-character;
        text-indent: 12mm;
        line-height: 1.6;
        margin-bottom: 4mm;
    }}
    .closing {{
        text-align: right;
        margin-top: 8mm;
        margin-bottom: 8mm;
        font-size: 10pt;
    }}
    .sig-block {{
        text-align: center;
        float: right;
        width: 80mm;
        margin-right: 0mm;
        margin-top: 4mm;
    }}
    .sig-space {{
        height: 20mm;
    }}
    .sig-line {{
        border-top: 0.5pt solid #000;
        width: 70mm;
        margin: 0 auto 2mm auto;
        padding-top: 2mm;
        font-size: 10pt;
    }}
    .sig-name {{ font-size: 10pt; margin-bottom: 1mm; }}
    .sig-pos  {{ font-size: 10pt; }}
    .clearfix {{ clear: both; }}

    /* หนังสือมอบอำนาจ */
    .sig-right {{
        float: right;
        width: 90mm;
        text-align: center;
        margin-bottom: 5mm;
    }}
    .sig-right .sig-line {{
        border-top: 0.5pt solid #000;
        width: 70mm;
        margin: 0 auto 1mm auto;
        padding-top: 2mm;
    }}
    .stamp {{
        font-size: 7pt;
        color: #666;
        margin-top: 6mm;
    }}
    '''

def _html_to_pdf(html):
    """แปลง HTML → PDF bytes ผ่าน WeasyPrint"""
    from weasyprint import HTML, CSS
    return HTML(string=html).write_pdf()

def _merge_on_template(content_pdf_bytes):
    """merge PDF ที่สร้างจาก HTML ทับบน bg_template.pdf"""
    base    = os.path.dirname(os.path.abspath(__file__))
    tpl     = os.path.join(base, 'bg_template.pdf')
    reader  = PdfReader(tpl)
    tpl_page = reader.pages[0]

    content_reader = PdfReader(BytesIO(content_pdf_bytes))
    content_page   = content_reader.pages[0]

    # merge: template เป็น base, content overlay ทับ
    tpl_page.merge_page(content_page)

    writer = PdfWriter()
    writer.add_page(tpl_page)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()

# ══════════════════════════════════════════════════════════════════════
# FORM 1: หนังสือขอถอนหลักประกัน
# ══════════════════════════════════════════════════════════════════════
def generate_bg_withdraw():
    try:
        data   = request.get_json(force=True) or {}
        cid    = str(data.get('contractId','') or '')
        cname  = str(data.get('contractName','') or '')
        cdate  = str(data.get('signedDate','') or '')
        co     = str(data.get('company','') or '')
        bgn    = str(data.get('guaranteeNumber','') or '')
        bgd    = str(data.get('guaranteeIssueDate','') or '')
        bgv    = _fmt(data.get('guaranteeValue',''))
        signer = str(data.get('signerName','') or '')
        spos   = str(data.get('signerPosition','Corporate Lawyers') or 'Corporate Lawyers')
        docnum = str(data.get('docNumber','') or cid)
        entity = data.get('entity') or {}
        ename  = entity.get('name','บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด')
        eshort = 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด'

        fonts  = _font_b64()
        css    = _css(fonts)

        p1 = (f'ตามที่{eshort} ได้ทำสัญญา{cname} '
              f'ฉบับเลขที่ {cid} ลงวันที่ {cdate} กับ {co} นั้น')
        p2 = (f'บัดนี้{eshort} ได้ทำงานสำเร็จเสร็จสิ้นเป็นที่เรียบร้อยแล้วตาม'
              f'สัญญาดังกล่าว บริษัทฯ จึงใคร่ขอคืนหนังสือค้ำประกันเลขที่ {bgn} '
              f'ลงวันที่ {bgd} มูลค่าค้ำประกัน {bgv} บาท')
        p3 = ('ทางบริษัทฯ หวังเป็นอย่างยิ่งว่าจะได้รับความกรุณาจากท่าน '
              'และขอบคุณล่วงหน้ามา ณ ที่นี้')

        html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{css}</style></head>
<body><div class="page">
  <div class="doc-number">เลขที่ {docnum}</div>
  <div class="title">หนังสือแจ้งขอถอนหลักประกันสัญญา</div>
  <div class="written-at">เขียนที่ {ename}</div>
  <div class="subject-line">
    <span class="subject-label">เรื่อง</span>
    <span class="subject-value">ขอถอนหลักประกันสัญญา</span>
  </div>
  <div class="subject-line">
    <span class="subject-label">เรียน</span>
    <span class="subject-value">{co}</span>
  </div>
  <p class="para">{p1}</p>
  <p class="para">{p2}</p>
  <p class="para">{p3}</p>
  <div class="closing">ขอแสดงความนับถือ</div>
  <div class="sig-block">
    <div class="sig-space"></div>
    <div class="sig-line"></div>
    <div class="sig-name">({signer})</div>
    <div class="sig-pos">{spos}</div>
  </div>
  <div class="clearfix"></div>
</div></body></html>'''

        content_pdf = _html_to_pdf(html)
        final_pdf   = _merge_on_template(content_pdf)

        return jsonify({
            'success':   True,
            'pdfBase64': base64.b64encode(final_pdf).decode(),
            'fileName':  f'หนังสือขอถอนหลักประกัน_{cid.replace("/","-")}.pdf'
        })
    except Exception as e:
        logger.error(f'bg_withdraw: {e}')
        return jsonify({'success':False,'message':str(e)}), 500


# ══════════════════════════════════════════════════════════════════════
# FORM 2: หนังสือมอบอำนาจ
# ══════════════════════════════════════════════════════════════════════
def generate_bg_poa():
    try:
        data     = request.get_json(force=True) or {}
        cid      = str(data.get('contractId','') or '')
        bgn      = str(data.get('guaranteeNumber','') or '')
        bgv      = _fmt(data.get('guaranteeValue',''))
        co       = str(data.get('company','') or '')
        doc_date = str(data.get('docDate','') or '')
        entity   = data.get('entity') or {}
        grantor  = data.get('grantor') or {}
        grantee  = data.get('grantee') or {}
        witnesses= data.get('witnesses') or [{},{}]
        while len(witnesses) < 2: witnesses.append({})

        ename  = entity.get('name','บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด')
        eshort = 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด'
        eaddr  = entity.get('address',
            'ตั้งอยู่เลขที่ 92/54-55 อาคารสาธรธานี 2 ชั้น 19 ถนนสาทรเหนือ แขวงสีลม เขตบางรัก กรุงเทพมหานคร')
        gr_name = str(grantor.get('name','นายบัณฑิต หมั้นทรัพย์') or '')
        gr_id   = str(grantor.get('idCard','3101201187013') or '')
        ge_name = str(grantee.get('name','') or '')
        ge_id   = str(grantee.get('idCard','') or '')
        ge_addr = str(grantee.get('address','') or '')
        w1      = str(witnesses[0].get('name','นายปิติชัย พัฒนกิจกุล') or '')
        w2      = str(witnesses[1].get('name','นางสาวสิริกาญจนา จันทร์อ่อน') or '')

        fonts = _font_b64()
        css   = _css(fonts)

        addr_part = f'ที่อยู่ {ge_addr} ' if ge_addr else ''
        body = (f'โดยหนังสือฉบับนี้ ข้าพเจ้า {eshort} {eaddr} '
                f'โดย {gr_name} บัตรประชาชนเลขที่ {gr_id} '
                f'ผู้มีอำนาจกระทำนิติกรรมตามหนังสือรับรองของสำนักงานทะเบียน'
                f'หุ้นส่วนบริษัทกลางกรมพัฒนาธุรกิจการค้า กระทรวงพาณิชย์ '
                f'ขอมอบอำนาจให้ {ge_name} ผู้ถือบัตรประชาชนเลขที่ {ge_id} '
                f'{addr_part}'
                f'เป็นผู้มีอำนาจดำเนินการรับคืนหนังสือค้ำประกันเลขที่ {bgn} '
                f'มูลค่า {bgv} บาท กับ {co}')
        p2 = ('การกระทำใดๆ ที่ผู้รับมอบอำนาจได้กระทำไป เปรียบเสมือนข้าพเจ้าได้กระทำทุกประการ '
              'จึงลงลายมือชื่อไว้ต่อหน้าพยานทั้ง 2 คน และให้พยานลงลายมือชื่อไว้เป็นหลักฐาน '
              'พร้อมทั้งแนบสำเนาบัตรประจำตัวประชาชนของข้าพเจ้าและผู้รับมอบอำนาจมานี้ด้วย')

        def sig_html(label, name):
            return f'''
            <div class="sig-right">
              <div class="sig-line"></div>
              <div>{label}</div>
              <div>({name})</div>
            </div>
            <div class="clearfix"></div>'''

        html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{css}</style></head>
<body><div class="page">
  <div class="doc-number">({cid})</div>
  <div class="title">หนังสือมอบอำนาจ</div>
  <div class="written-at">ทำที่ {ename}<br>วันที่ {doc_date}</div>
  <p class="para">{body}</p>
  <p class="para">{p2}</p>
  {sig_html('ผู้มอบอำนาจ', gr_name)}
  {sig_html('ผู้รับมอบอำนาจ', ge_name)}
  {sig_html('พยาน', w1)}
  {sig_html('พยาน', w2)}
  <div class="stamp">ติดอากรแสตมป์ 10 บาท</div>
</div></body></html>'''

        content_pdf = _html_to_pdf(html)
        final_pdf   = _merge_on_template(content_pdf)

        return jsonify({
            'success':   True,
            'pdfBase64': base64.b64encode(final_pdf).decode(),
            'fileName':  f'หนังสือมอบอำนาจ_{cid.replace("/","-")}.pdf'
        })
    except Exception as e:
        logger.error(f'bg_poa: {e}')
        return jsonify({'success':False,'message':str(e)}), 500


def register_bg_withdraw_routes(app):
    app.add_url_rule('/generate_bg_withdraw','generate_bg_withdraw',
                     generate_bg_withdraw, methods=['POST'])
    app.add_url_rule('/generate_bg_poa','generate_bg_poa',
                     generate_bg_poa, methods=['POST'])
