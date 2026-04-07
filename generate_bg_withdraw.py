#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: weasyprint-overlay-v2-final-fix
"""
generate_bg_withdraw.py
=======================
Render API — สร้าง PDF 2 แบบ overlay บน bg_template.pdf
  1. POST /generate_bg_withdraw — หนังสือแจ้งขอถอนหลักประกันสัญญา
  2. POST /generate_bg_poa      — หนังสือมอบอำนาจขอคืนหนังสือค้ำประกัน

★ FIX: _fmt() format string bug — comma เกินทำให้ fallback เป็น raw number
"""

import os, base64, logging
from io import BytesIO
from flask import request, jsonify
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

# ── Number formatter ───────────────────────────────────────────────────
def _fmt(v):
    """แปลงตัวเลข → format xxx,xxx.xx"""
    if not v:
        return ''
    try:
        n = float(str(v).replace(',', ''))
        if n == 0:
            return ''
        return f'{n:,.2f}'
    except (ValueError, TypeError):
        return str(v)

# ── Thai Date formatter ────────────────────────────────────────────────
_TH_MONTHS = ['มกราคม','กุมภาพันธ์','มีนาคม','เมษายน','พฤษภาคม','มิถุนายน',
              'กรกฎาคม','สิงหาคม','กันยายน','ตุลาคม','พฤศจิกายน','ธันวาคม']

def _fmt_date_th(v):
    """แปลง dd/mm/yyyy (พ.ศ.) → '28 กุมภาพันธ์ 2568' (แบบเต็ม)
    ถ้า format ไม่ตรง → คืนค่าเดิม
    """
    if not v:
        return ''
    s = str(v).strip()
    parts = s.split('/')
    if len(parts) != 3:
        return s
    try:
        d = int(parts[0])
        m = int(parts[1])
        y = parts[2]
        if m < 1 or m > 12:
            return s
        return f'{d} {_TH_MONTHS[m-1]} พ.ศ.{y}'
    except (ValueError, IndexError):
        return s

# ── Font loader ────────────────────────────────────────────────────────
def _font_b64():
    """โหลด THSarabunNew เป็น base64 สำหรับ embed ใน CSS"""
    base = os.path.dirname(os.path.abspath(__file__))
    result = {}
    for fn in ['THSarabunNew.ttf', 'THSarabunNew-Bold.ttf']:
        p = os.path.join(base, 'fonts', fn)
        if os.path.exists(p):
            with open(p, 'rb') as f:
                result[fn] = base64.b64encode(f.read()).decode()
    return result

# ── CSS ────────────────────────────────────────────────────────────────
def _css(fonts):
    """CSS หลัก — TH Sarabun New + A4 + justify + signature layout"""
    reg  = fonts.get('THSarabunNew.ttf', '')
    bold = fonts.get('THSarabunNew-Bold.ttf', '')
    ff   = ''
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
    return f"""
    {ff}
    @page {{ size: A4; margin: 0; }}
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
    .doc-number  {{ font-size: 10pt; margin-bottom: 6mm; }}
    .title       {{ font-size: 12pt; font-weight: bold; text-align: center; margin-bottom: 8mm; }}
    .written-at  {{ font-size: 10pt; text-align: right; margin-bottom: 6mm; line-height: 1.6; }}
    .subject-line  {{ display: flex; margin-bottom: 4mm; }}
    .subject-label {{ font-weight: bold; min-width: 18mm; flex-shrink: 0; }}
    .subject-value {{ flex: 1; }}
    .para {{
        font-size: 10pt;
        text-align: justify;
        text-indent: 12mm;
        line-height: 1.6;
        margin-bottom: 4mm;
    }}
    .closing-area {{
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        margin-top: 8mm;
    }}
    .closing     {{ font-size: 10pt; margin-bottom: 4mm; text-align: center; width: 75mm; }}
    .sig-block   {{ text-align: center; width: 75mm; }}
    .sig-space   {{ height: 18mm; }}
    .sig-line    {{
        border-top: 0.5pt solid #000;
        width: 75mm;
        margin: 0 auto 2mm auto;
        padding-top: 2mm;
        font-size: 10pt;
    }}
    .sig-name    {{ font-size: 10pt; margin-bottom: 1mm; }}
    .sig-pos     {{ font-size: 10pt; }}
    .sig-col {{
        width: 50%;
        margin-left: auto;
        margin-top: 8mm;
    }}
    .sig-right {{
        margin-bottom: 6mm;
        width: 100%;
    }}
    .sig-right .sig-space {{ height: 10mm; }}
    .sig-right .sig-row1 {{
        display: flex;
        align-items: flex-end;
        width: 100%;
    }}
    .sig-right .sig-row1 .prefix {{
        font-size: 10pt;
        white-space: nowrap;
        flex-shrink: 0;
        padding-bottom: 0.5mm;
        padding-right: 1mm;
    }}
    .sig-right .sig-row1 .line-cell {{
        flex: 1;
        border-bottom: 0.5pt solid #000;
        height: 5mm;
        min-width: 0;
    }}
    .sig-right .sig-row1 .lbl {{
        font-size: 9pt;
        white-space: nowrap;
        flex-shrink: 0;
        flex-basis: 22mm;
        width: 22mm;
        text-align: left;
        padding-bottom: 0.5mm;
        padding-left: 1mm;
    }}
    .sig-right .sig-name {{
        font-size: 10pt;
        margin-top: 1mm;
        text-align: center;
        padding-left: 12mm;
        padding-right: 23mm;
    }}
    .stamp  {{ font-size: 9pt; color: #666; margin-top: 6mm; }}
    .clearfix {{ clear: both; }}
    """

# ── WeasyPrint HTML→PDF ────────────────────────────────────────────────
def _html_to_pdf(html):
    from weasyprint import HTML
    return HTML(string=html).write_pdf()

# ── Merge ทับ template ─────────────────────────────────────────────────
def _merge_on_template(content_bytes):
    """overlay content PDF บน bg_template.pdf"""
    base     = os.path.dirname(os.path.abspath(__file__))
    tpl_path = os.path.join(base, 'bg_template.pdf')
    reader   = PdfReader(tpl_path)
    page     = reader.pages[0]
    page.merge_page(PdfReader(BytesIO(content_bytes)).pages[0])
    writer = PdfWriter()
    writer.add_page(page)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()

# ══════════════════════════════════════════════════════════════════════
# FORM 1 — หนังสือแจ้งขอถอนหลักประกันสัญญา
# ══════════════════════════════════════════════════════════════════════
def generate_bg_withdraw():
    try:
        data     = request.get_json(force=True) or {}
        cid      = str(data.get('contractId','')    or '')
        cname    = str(data.get('contractName','')  or '')
        cdate    = str(data.get('signedDate','')    or '')
        co       = str(data.get('company','')       or '')
        bgn      = str(data.get('guaranteeNumber','') or '')
        bgd      = _fmt_date_th(str(data.get('guaranteeIssueDate','') or ''))
        bgv      = _fmt(data.get('guaranteeValue',''))
        signer   = str(data.get('signerName','')    or '')
        spos     = str(data.get('signerPosition','Corporate Lawyers') or 'Corporate Lawyers')
        docnum   = str(data.get('docNumber','')     or cid)
        doc_date = str(data.get('docDate','')       or '')
        entity   = data.get('entity') or {}
        ename    = entity.get('name', 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด')
        eshort   = 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด'

        fonts = _font_b64()
        css   = _css(fonts)

        p1 = (f'ตามที่{eshort} ได้ทำสัญญา{cname} '
              f'ฉบับเลขที่ {cid} ลงวันที่ {cdate} กับ {co} นั้น')
        p2 = (f'บัดนี้{eshort} ได้ทำงานสำเร็จเสร็จสิ้นเป็นที่เรียบร้อยแล้วตาม'
              f'สัญญาดังกล่าว บริษัทฯ จึงใคร่ขอคืนหนังสือค้ำประกันเลขที่ {bgn} '
              f'ลงวันที่ {bgd} มูลค่าค้ำประกัน {bgv} บาท')
        p3 = ('ทางบริษัทฯ หวังเป็นอย่างยิ่งว่าจะได้รับความกรุณาจากท่าน '
              'และขอบคุณล่วงหน้ามา ณ ที่นี้')

        # ★ ใช้ body text จาก popup ถ้ามี (user แก้ไขได้)
        custom_body = str(data.get('withdrawBody', '') or '').strip()
        if custom_body:
            # แยก paragraph ด้วย newline คู่
            paras = [p.strip() for p in custom_body.split('\n') if p.strip()]
        else:
            paras = [p1, p2, p3]

        body_html = '\n'.join(f'  <p class="para">{p}</p>' for p in paras)

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{css}</style></head>
<body><div class="page">
  <div class="doc-number">เลขที่ {docnum}</div>
  <div class="title">หนังสือแจ้งขอถอนหลักประกันสัญญา</div>
  <div class="written-at">เขียนที่ {ename}<br>วันที่ {doc_date}</div>
  <div class="subject-line">
    <span class="subject-label">เรื่อง</span>
    <span class="subject-value">ขอถอนหลักประกันสัญญา</span>
  </div>
  <div class="subject-line">
    <span class="subject-label">เรียน</span>
    <span class="subject-value">{co}</span>
  </div>
{body_html}
  <div class="closing-area">
    <div class="closing">ขอแสดงความนับถือ</div>
    <div class="sig-block">
      <div class="sig-space"></div>
      <div class="sig-line"></div>
      <div class="sig-name">({signer})</div>
      <div class="sig-pos">{spos}</div>
    </div>
  </div>
  <div class="clearfix"></div>
</div></body></html>"""

        final = _merge_on_template(_html_to_pdf(html))
        return jsonify({
            'success':   True,
            'pdfBase64': base64.b64encode(final).decode(),
            'fileName':  f'หนังสือขอถอนหลักประกัน_{cid.replace("/","-")}.pdf'
        })
    except Exception as e:
        logger.error(f'bg_withdraw error: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════════
# FORM 2 — หนังสือมอบอำนาจขอคืนหนังสือค้ำประกัน
# ══════════════════════════════════════════════════════════════════════
def generate_bg_poa():
    try:
        data      = request.get_json(force=True) or {}
        cid       = str(data.get('contractId','')       or '')
        docnum    = str(data.get('docNumber','')        or cid)
        bgn       = str(data.get('guaranteeNumber','')  or '')
        bgv       = _fmt(data.get('guaranteeValue',''))
        co        = str(data.get('company','')          or '')
        doc_date  = str(data.get('docDate','')          or '')
        entity    = data.get('entity')   or {}
        grantor   = data.get('grantor')  or {}
        grantee   = data.get('grantee')  or {}
        witnesses = data.get('witnesses') or [{}, {}]
        while len(witnesses) < 2:
            witnesses.append({})

        ename   = entity.get('name', 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด')
        eshort  = 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด'
        eaddr   = entity.get('address',
            'ตั้งอยู่เลขที่ 92/54-55 อาคารสาธรธานี 2 ชั้น 19 ถนนสาทรเหนือ '
            'แขวงสีลม เขตบางรัก กรุงเทพมหานคร')
        gr_name = str(grantor.get('name',   'นายบัณฑิต หมั้นทรัพย์') or '')
        gr_id   = str(grantor.get('idCard', '3101201187013')           or '')
        ge_name = str(grantee.get('name',   '')   or '')
        ge_id   = str(grantee.get('idCard', '')   or '')
        ge_addr = str(grantee.get('address','')   or '')
        w1      = str(witnesses[0].get('name', 'นายปิติชัย พัฒนกิจกุล')        or '')
        w2      = str(witnesses[1].get('name', 'นางสาวสิริกาญจนา จันทร์อ่อน') or '')

        fonts = _font_b64()
        css   = _css(fonts)

        addr_part = f'ที่อยู่ {ge_addr} ' if ge_addr else ''
        body_default = (f'โดยหนังสือฉบับนี้ ข้าพเจ้า {eshort} {eaddr} '
                f'โดย {gr_name} บัตรประชาชนเลขที่ {gr_id} '
                f'ผู้มีอำนาจกระทำนิติกรรมตามหนังสือรับรองของสำนักงานทะเบียน'
                f'หุ้นส่วนบริษัทกลางกรมพัฒนาธุรกิจการค้า กระทรวงพาณิชย์ '
                f'ขอมอบอำนาจให้ {ge_name} ผู้ถือบัตรประชาชนเลขที่ {ge_id} '
                f'{addr_part}'
                f'เป็นผู้มีอำนาจดำเนินการรับคืนหนังสือค้ำประกันเลขที่ {bgn} '
                f'มูลค่า {bgv} บาท กับ {co}')
        p2_default = ('การกระทำใดๆ ที่ผู้รับมอบอำนาจได้กระทำไป เปรียบเสมือนข้าพเจ้าได้กระทำทุกประการ '
              'จึงลงลายมือชื่อไว้ต่อหน้าพยานทั้ง 2 คน และให้พยานลงลายมือชื่อไว้เป็นหลักฐาน '
              'พร้อมทั้งแนบสำเนาบัตรประจำตัวประชาชนของข้าพเจ้าและผู้รับมอบอำนาจมานี้ด้วย')

        # ★ ใช้ body text จาก popup ถ้ามี (user แก้ไขได้)
        custom_poa = str(data.get('poaBody', '') or '').strip()
        if custom_poa:
            poa_paras = [p.strip() for p in custom_poa.split('\n') if p.strip()]
        else:
            poa_paras = [body_default, p2_default]

        poa_body_html = '\n'.join(f'  <p class="para">{p}</p>' for p in poa_paras)

        def sig_html(label, name):
            return f"""<div class="sig-right">
              <div class="sig-space"></div>
              <div class="sig-row1">
                <span class="prefix">ลงชื่อ</span>
                <span class="line-cell"></span>
                <span class="lbl">{label}</span>
              </div>
              <div class="sig-name">({name})</div>
            </div>"""

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{css}</style></head>
<body><div class="page">
  {'<div class="doc-number">เลขที่ ' + docnum + '</div>' if docnum else ''}
  <div class="title">หนังสือมอบอำนาจ</div>
  <div class="written-at">ทำที่ {ename}<br>วันที่ {doc_date}</div>
{poa_body_html}
  <div class="sig-col">
    {sig_html('ผู้มอบอำนาจ', gr_name)}
    {sig_html('ผู้รับมอบอำนาจ', ge_name)}
    {sig_html('พยาน', w1)}
    {sig_html('พยาน', w2)}
  </div>
  <div class="stamp">ติดอากรแสตมป์ 10 บาท</div>
</div></body></html>"""

        final = _merge_on_template(_html_to_pdf(html))
        return jsonify({
            'success':   True,
            'pdfBase64': base64.b64encode(final).decode(),
            'fileName':  f'หนังสือมอบอำนาจ_{cid.replace("/","-")}.pdf'
        })
    except Exception as e:
        logger.error(f'bg_poa error: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════════
# Registration
# ══════════════════════════════════════════════════════════════════════
def register_bg_withdraw_routes(app):
    """เรียกจาก app.py: register_bg_withdraw_routes(app)"""
    app.add_url_rule('/generate_bg_withdraw', 'generate_bg_withdraw',
                     generate_bg_withdraw, methods=['POST'])
    app.add_url_rule('/generate_bg_poa', 'generate_bg_poa',
                     generate_bg_poa, methods=['POST'])
