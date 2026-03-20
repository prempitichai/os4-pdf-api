"""
generate_bg_withdraw.py
=======================
Railway API endpoints สำหรับสร้าง PDF 2 แบบ:
  1. /generate_bg_withdraw  — หนังสือแจ้งขอถอนหลักประกันสัญญา
  2. /generate_bg_poa       — หนังสือมอบอำนาจขอคืนหนังสือค้ำประกัน

เพิ่มเข้า app.py ที่มีอยู่แล้ว (เพิ่ม import + register blueprint หรือ paste ฟังก์ชันตรงๆ)

Dependencies: reportlab, Pillow (เหมือน endpoint อื่น)
Font: TH Sarabun New (thsarabunnew.ttf / thsarabunnew-bold.ttf)
"""

# ── ตัวอย่าง import ที่ต้องมีใน app.py ──────────────────────────────────
# from flask import Flask, request, jsonify
# import base64, io, os, re
# from reportlab.lib.pagesizes import A4
# from reportlab.pdfgen import canvas
# from reportlab.lib.units import mm
# from reportlab.pdfbase import pdfmetrics
# from reportlab.pdfbase.ttfonts import TTFont
# ────────────────────────────────────────────────────────────────────────

import base64
import io
import os
import re

from flask import request, jsonify
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Constants ──────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4          # 595.28 x 841.89 pt
MARGIN_L  = 25 * mm          # ขอบซ้าย
MARGIN_R  = 20 * mm          # ขอบขวา
MARGIN_T  = 20 * mm          # ขอบบน
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

FONT_REG  = 'THSarabunNew'
FONT_BOLD = 'THSarabunNew-Bold'

# ── โหลด Font (เรียกครั้งเดียวตอน module load) ─────────────────────────
def _register_fonts():
    """ลงทะเบียน TH Sarabun New — ใช้ path เดียวกับ endpoint อื่นใน app.py"""
    base = os.path.dirname(os.path.abspath(__file__))
    font_dir = os.path.join(base, 'fonts')
    try:
        pdfmetrics.registerFont(TTFont(FONT_REG,  os.path.join(font_dir, 'THSarabunNew.ttf')))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, os.path.join(font_dir, 'THSarabunNew Bold.ttf')))
    except Exception:
        # fallback: ลอง FreeSerif (เผื่อ deploy environment เดิม)
        try:
            pdfmetrics.registerFont(TTFont(FONT_REG,  os.path.join(font_dir, 'FreeSerif.ttf')))
            pdfmetrics.registerFont(TTFont(FONT_BOLD, os.path.join(font_dir, 'FreeSerifBold.ttf')))
        except Exception:
            pass

_register_fonts()

# ── Helper ─────────────────────────────────────────────────────────────
def _fmt_number(val):
    """แปลง 758840 หรือ '758,840.00' → '758,840.00'"""
    if not val:
        return ''
    try:
        n = float(str(val).replace(',', ''))
        return f'{n:,.2f}'
    except Exception:
        return str(val)


def _get_scm_logo_path():
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'images', 'scm_logo.png')


def _draw_header(c, entity):
    """
    วาด header SCM เหมือน PDF ตัวอย่าง:
      - โลโก้ขวา
      - ชื่อ/ที่อยู่/โทรฯ ซ้าย (ตัวเล็ก)
    entity = dict: { name, address, phone }
    """
    logo_path = _get_scm_logo_path()
    if os.path.exists(logo_path):
        c.drawImage(logo_path, PAGE_W - MARGIN_R - 35*mm, PAGE_H - MARGIN_T - 18*mm,
                    width=35*mm, height=18*mm, preserveAspectRatio=True, mask='auto')

    # ชื่อบริษัท bold 10pt
    c.setFont(FONT_BOLD, 10)
    name_th = entity.get('name', 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด (สำนักงานใหญ่)')
    c.drawString(MARGIN_L, PAGE_H - MARGIN_T - 5*mm, name_th)

    # ที่อยู่ regular 9pt
    c.setFont(FONT_REG, 9)
    addr = entity.get('address',
        'เลขที่ 92/54-55 ชั้น 19 อาคารสาธรธานี 2 ถนนสาทรเหนือ แขวงสีลม เขตบางรัก กรุงเทพฯ 10500')
    phone = entity.get('phone', 'โทรศัพท์ : +66 (0) 2 116 4213')
    c.drawString(MARGIN_L, PAGE_H - MARGIN_T - 10*mm, addr)
    c.drawString(MARGIN_L, PAGE_H - MARGIN_T - 14.5*mm, phone)

    # เส้นคั่น
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.setLineWidth(0.5)
    c.line(MARGIN_L, PAGE_H - MARGIN_T - 18*mm, PAGE_W - MARGIN_R, PAGE_H - MARGIN_T - 18*mm)
    c.setStrokeColorRGB(0, 0, 0)


def _draw_footer(c, entity):
    """Footer ท้ายกระดาษ — ชื่อบริษัท + ที่อยู่ (สีส้ม เหมือน template)"""
    footer_y = 12*mm
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.setLineWidth(0.5)
    c.line(MARGIN_L, footer_y + 8*mm, PAGE_W - MARGIN_R, footer_y + 8*mm)

    # ชื่อ bold สีส้ม
    c.setFont(FONT_BOLD, 9)
    c.setFillColorRGB(0.91, 0.42, 0.04)   # #E86B0A
    name_bold = entity.get('name', 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด (สำนักงานใหญ่)')
    c.drawCentredString(PAGE_W / 2, footer_y + 4.5*mm, name_bold)

    c.setFont(FONT_REG, 8.5)
    c.setFillColorRGB(0, 0, 0)
    addr_footer = entity.get('address',
        'เลขที่ 92/54-55 ชั้น 19 อาคารสาธรธานี 2 ถนนสาทรเหนือ แขวงสีลม เขตบางรัก กรุงเทพฯ 10500')
    phone_footer = entity.get('phone', 'โทรศัพท์ : +66 (0) 2 116 4213')
    c.drawCentredString(PAGE_W / 2, footer_y + 0.5*mm,
                        addr_footer + '  ' + phone_footer)


def _wrap_text(text, font_name, font_size, max_width):
    """
    ตัดคำ Thai/Eng ให้พอดี max_width (pt) — Thai-safe
    ตัดทีละตัวอักษร รองรับ Thai ที่ไม่มี space ระหว่างคำ
    คืน list ของ lines
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth
    text = str(text or '')
    if not text:
        return ['']
    lines = []
    cur   = ''
    for ch in text:
        test = cur + ch
        if stringWidth(test, font_name, font_size) <= max_width:
            cur = test
        else:
            # ถ้ามี space → ตัดที่ space ล่าสุด
            last_sp = cur.rfind(' ')
            if last_sp > 0:
                lines.append(cur[:last_sp])
                cur = cur[last_sp + 1:] + ch
            else:
                if cur:
                    lines.append(cur)
                cur = ch
    if cur:
        lines.append(cur)
    return lines or ['']


def _draw_justified_line(c, line, x, y, font_name, font_size, max_width):
    """วาด 1 บรรทัดแบบ justify — กระจาย space ให้เต็มความกว้าง"""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    words = line.split(' ')
    if len(words) <= 1:
        c.setFont(font_name, font_size)
        c.drawString(x, y, line)
        return
    total_w = stringWidth(line.replace(' ', ''), font_name, font_size)
    gaps    = len(words) - 1
    space_w = (max_width - total_w) / gaps if gaps > 0 else 0
    cx = x
    c.setFont(font_name, font_size)
    for word in words:
        c.drawString(cx, y, word)
        cx += stringWidth(word, font_name, font_size) + space_w


def _draw_paragraph(c, text, x, y, font_name, font_size, max_width,
                    line_height=None, indent=0, bold_phrases=None):
    """
    วาดย่อหน้าข้อความพร้อม word-wrap + justify
    - ทุกบรรทัดยกเว้นสุดท้าย: justify (ชิดทั้งซ้ายขวา)
    - บรรทัดสุดท้าย: ชิดซ้าย
    bold_phrases: list of strings ที่จะ bold
    คืน y สุดท้าย
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth
    if line_height is None:
        line_height = font_size * 1.45

    lines = _wrap_text(text, font_name, font_size, max_width - indent)
    for i, line in enumerate(lines):
        draw_x  = x + (indent if i == 0 else 0)
        line_w  = max_width - (indent if i == 0 else 0)
        is_last = (i == len(lines) - 1)

        if bold_phrases:
            # มี bold phrase → วาด mixed (ไม่ justify เพื่อความถูกต้องของ bold)
            _draw_mixed_line(c, line, draw_x, y, font_name, FONT_BOLD, font_size, bold_phrases)
        elif is_last or len(line.split(' ')) <= 1:
            # บรรทัดสุดท้าย / บรรทัดคำเดียว → ชิดซ้าย
            c.setFont(font_name, font_size)
            c.drawString(draw_x, y, line)
        else:
            # justify
            _draw_justified_line(c, line, draw_x, y, font_name, font_size, line_w)
        y -= line_height
    return y


def _draw_mixed_line(c, line, x, y, font_reg, font_bold, size, bold_phrases):
    """วาด 1 บรรทัด โดย phrase ที่ใน bold_phrases จะ bold"""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    # สร้าง token list: [(text, is_bold), ...]
    tokens = [(line, False)]
    for phrase in bold_phrases:
        if not phrase:          # ★ skip empty phrase — ป้องกัน empty separator error
            continue
        new_tokens = []
        for (seg, is_b) in tokens:
            if is_b or phrase not in seg:
                new_tokens.append((seg, is_b))
            else:
                parts = seg.split(phrase, 1)
                new_tokens.append((parts[0], False))
                new_tokens.append((phrase, True))
                new_tokens.append((parts[1], False))
        tokens = new_tokens

    cur_x = x
    for (seg, is_b) in tokens:
        if not seg:
            continue
        f = font_bold if is_b else font_reg
        c.setFont(f, size)
        c.drawString(cur_x, y, seg)
        cur_x += stringWidth(seg, f, size)


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT 1: หนังสือแจ้งขอถอนหลักประกันสัญญา
# ══════════════════════════════════════════════════════════════════════

def generate_bg_withdraw():
    """
    POST /generate_bg_withdraw
    Body (JSON):
      contractId        : เลขที่สัญญา  เช่น 'INET LGD 0039/2020'
      contractName      : ชื่อสัญญา
      signedDate        : วันที่สัญญา  เช่น '8 มกราคม พ.ศ.2563'
      company           : คู่สัญญา (เรียน)
      guaranteeNumber   : เลข BG
      guaranteeIssueDate: วันที่ออก BG เช่น '12 กุมภาพันธ์ พ.ศ.2563'
      guaranteeValue    : มูลค่า BG (ตัวเลข หรือ string)
      signerName        : ชื่อผู้ลงนาม เช่น 'นางสาวสมใจ ใจดี'
      signerPosition    : ตำแหน่ง เช่น 'Corporate Lawyers'
      docDate           : วันที่หนังสือ (ถ้าว่าง = วันนี้)
      docNumber         : เลขที่หนังสือ (ถ้าว่าง สร้างอัตโนมัติ)
      entity            : { name, address, phone }  (optional, default SCM Tech)
    Returns:
      { success, pdfBase64, fileName }
    """
    try:
        data = request.get_json(force=True) or {}

        # ── Fields ────────────────────────────────────────────────────
        contract_id     = str(data.get('contractId', '') or '')
        contract_name   = str(data.get('contractName', '') or '')
        signed_date     = str(data.get('signedDate', '') or '')
        company         = str(data.get('company', '') or '')
        bg_number       = str(data.get('guaranteeNumber', '') or '')
        bg_issue_date   = str(data.get('guaranteeIssueDate', '') or '')
        bg_value        = _fmt_number(data.get('guaranteeValue', ''))
        signer_name     = str(data.get('signerName', '') or '')
        signer_pos      = str(data.get('signerPosition', 'Corporate Lawyers') or 'Corporate Lawyers')
        doc_date        = str(data.get('docDate', '') or '')
        doc_number      = str(data.get('docNumber', '') or contract_id)
        entity          = data.get('entity') or {}

        entity_name = entity.get('name', 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด')
        entity_short = 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด'   # ใช้ในเนื้อหา

        # ── สร้าง PDF ─────────────────────────────────────────────────
        buf = io.BytesIO()
        c   = canvas.Canvas(buf, pagesize=A4)

        # — Header —
        _draw_header(c, entity)

        # — เลขที่หนังสือ (ซ้ายบน ใต้ header) —
        y = PAGE_H - MARGIN_T - 25*mm
        c.setFont(FONT_REG, 14)
        c.drawString(MARGIN_L, y, f'เลขที่ {doc_number}')

        # — ชื่อเรื่อง (กลาง) —
        y -= 10*mm
        c.setFont(FONT_BOLD, 16)
        c.drawCentredString(PAGE_W / 2, y, 'หนังสือแจ้งขอถอนหลักประกันสัญญา')

        # — เขียนที่ (ขวา) —
        y -= 12*mm
        c.setFont(FONT_REG, 14)
        c.drawRightString(PAGE_W - MARGIN_R, y,
                          f'เขียนที่ {entity_name}')

        # — เรื่อง / เรียน —
        y -= 9*mm
        c.setFont(FONT_BOLD, 14)
        c.drawString(MARGIN_L, y, 'เรื่อง')
        c.setFont(FONT_REG, 14)
        c.drawString(MARGIN_L + 18*mm, y, 'ขอถอนหลักประกันสัญญา')

        y -= 7*mm
        c.setFont(FONT_BOLD, 14)
        c.drawString(MARGIN_L, y, 'เรียน')
        c.setFont(FONT_REG, 14)
        c.drawString(MARGIN_L + 18*mm, y, company)

        # — ย่อหน้าที่ 1 —
        y -= 10*mm
        para1 = (
            f'ตามที่{entity_short} ได้ทำสัญญา{contract_name} '
            f'ฉบับเลขที่ {contract_id} ลงวันที่ {signed_date} '
            f'กับ {company} นั้น'
        )
        y = _draw_paragraph(c, para1, MARGIN_L, y,
                            FONT_REG, 14, CONTENT_W,
                            indent=12*mm,
                            bold_phrases=[contract_id])

        # — ย่อหน้าที่ 2 —
        y -= 3*mm
        para2 = (
            f'บัดนี้{entity_short} ได้ทำงานสำเร็จเสร็จสิ้นเป็นที่เรียบร้อยแล้วตาม'
            f'สัญญาดังกล่าว บริษัทฯ จึงใคร่ขอคืนหนังสือค้ำประกันเลขที่ {bg_number} '
            f'ลงวันที่ {bg_issue_date} มูลค่าค้ำประกัน {bg_value} บาท'
        )
        y = _draw_paragraph(c, para2, MARGIN_L, y,
                            FONT_REG, 14, CONTENT_W,
                            indent=12*mm,
                            bold_phrases=[bg_number, bg_value])

        # — ย่อหน้าที่ 3 —
        y -= 3*mm
        para3 = (
            'ทางบริษัทฯ หวังเป็นอย่างยิ่งว่าจะได้รับความกรุณาจากท่าน '
            'และขอบคุณล่วงหน้ามา ณ ที่นี้'
        )
        y = _draw_paragraph(c, para3, MARGIN_L, y,
                            FONT_REG, 14, CONTENT_W,
                            indent=12*mm)

        # — ลงนาม —
        y -= 10*mm
        c.setFont(FONT_REG, 14)
        c.drawRightString(PAGE_W - MARGIN_R, y, 'ขอแสดงความนับถือ')

        y -= 22*mm   # พื้นที่ลายเซ็น
        # เส้นลายเซ็น
        sig_center = PAGE_W - MARGIN_R - 40*mm
        c.setLineWidth(0.5)
        c.line(sig_center - 28*mm, y + 4*mm, sig_center + 28*mm, y + 4*mm)

        c.setFont(FONT_REG, 14)
        if signer_name:
            c.drawCentredString(sig_center, y, f'({signer_name})')
        else:
            c.drawCentredString(sig_center, y, '(......)')
        y -= 6*mm
        c.drawCentredString(sig_center, y, signer_pos)

        # — Footer —
        _draw_footer(c, entity)

        c.showPage()
        c.save()

        pdf_bytes = buf.getvalue()
        pdf_b64   = base64.b64encode(pdf_bytes).decode('utf-8')
        file_name = f'หนังสือขอถอนหลักประกัน_{contract_id.replace("/", "-")}.pdf'

        return jsonify({'success': True, 'pdfBase64': pdf_b64, 'fileName': file_name})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT 2: หนังสือมอบอำนาจขอคืนหนังสือค้ำประกันสัญญา
# ══════════════════════════════════════════════════════════════════════

def generate_bg_poa():
    """
    POST /generate_bg_poa
    Body (JSON):
      contractId        : เลขที่สัญญา
      guaranteeNumber   : เลข BG
      guaranteeValue    : มูลค่า BG
      company           : คู่สัญญา
      docDate           : วันที่หนังสือมอบอำนาจ
      grantor           : { name, idCard }  ผู้มอบอำนาจ (กรรมการ)
      grantee           : { name, idCard, address }  ผู้รับมอบอำนาจ
      witnesses         : [{ name }, { name }]  พยาน 2 คน
      entity            : { name, address, phone }  (optional)
    Returns:
      { success, pdfBase64, fileName }
    """
    try:
        data = request.get_json(force=True) or {}

        # ── Fields ────────────────────────────────────────────────────
        contract_id   = str(data.get('contractId', '') or '')
        bg_number     = str(data.get('guaranteeNumber', '') or '')
        bg_value      = _fmt_number(data.get('guaranteeValue', ''))
        company       = str(data.get('company', '') or '')
        doc_date      = str(data.get('docDate', '') or '')
        entity        = data.get('entity') or {}

        grantor  = data.get('grantor')  or {}
        grantee  = data.get('grantee')  or {}
        witnesses = data.get('witnesses') or [{}, {}]
        # ensure 2 witnesses
        while len(witnesses) < 2:
            witnesses.append({})

        grantor_name  = str(grantor.get('name',  'นายบัณฑิต หมั้นทรัพย์') or 'นายบัณฑิต หมั้นทรัพย์')
        grantor_id    = str(grantor.get('idCard', '3101201187013') or '3101201187013')
        grantee_name  = str(grantee.get('name',  '') or '')
        grantee_id    = str(grantee.get('idCard', '') or '')
        grantee_addr  = str(grantee.get('address', '') or '')
        w1_name       = str(witnesses[0].get('name', 'นายปิติชัย พัฒนกิจกุล') or 'นายปิติชัย พัฒนกิจกุล')
        w2_name       = str(witnesses[1].get('name', 'นางสาวสิริกาญจนา จันทร์อ่อน') or 'นางสาวสิริกาญจนา จันทร์อ่อน')

        entity_name  = entity.get('name', 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด')
        entity_short = 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด'
        entity_addr  = entity.get('address',
            'ตั้งอยู่เลขที่ 92/54-55 อาคารสาธรธานี 2 ชั้น 19 ถนนสาทรเหนือ แขวงสีลม เขตบางรัก กรุงเทพมหานคร')

        # ── สร้าง PDF ─────────────────────────────────────────────────
        buf = io.BytesIO()
        c   = canvas.Canvas(buf, pagesize=A4)

        # — Header —
        _draw_header(c, entity)

        # — เลขที่สัญญา (ซ้ายบน) —
        y = PAGE_H - MARGIN_T - 25*mm
        c.setFont(FONT_REG, 14)
        c.drawString(MARGIN_L, y, f'({contract_id})')

        # — ชื่อเรื่อง —
        y -= 10*mm
        c.setFont(FONT_BOLD, 16)
        c.drawCentredString(PAGE_W / 2, y, 'หนังสือมอบอำนาจ')

        # — ทำที่ / วันที่ (ขวา) —
        y -= 12*mm
        c.setFont(FONT_REG, 14)
        c.drawRightString(PAGE_W - MARGIN_R, y,
                          f'ทำที่ {entity_name}')
        y -= 7*mm
        c.drawRightString(PAGE_W - MARGIN_R, y,
                          f'วันที่ {doc_date}')

        # — เนื้อหาหนังสือมอบอำนาจ —
        y -= 10*mm

        # สร้าง grantee_addr_text
        grantee_addr_text = f'ที่อยู่ {grantee_addr}' if grantee_addr else ''

        body = (
            f'โดยหนังสือฉบับนี้ ข้าพเจ้า {entity_short} '
            f'{entity_addr} โดย {grantor_name} '
            f'บัตรประชาชนเลขที่ {grantor_id} '
            f'ผู้มีอำนาจกระทำนิติกรรมตามหนังสือรับรองของสำนักงานทะเบียน'
            f'หุ้นส่วนบริษัทกลางกรมพัฒนาธุรกิจการค้า กระทรวงพาณิชย์ '
            f'ขอมอบอำนาจให้ {grantee_name} '
            f'ผู้ถือบัตรประชาชนเลขที่ {grantee_id} '
        )
        if grantee_addr_text:
            body += grantee_addr_text + ' '
        body += (
            f'เป็นผู้มีอำนาจดำเนินการรับคืนหนังสือค้ำประกันเลขที่ {bg_number} '
            f'มูลค่า {bg_value} บาท กับ {company}'
        )

        y = _draw_paragraph(c, body, MARGIN_L, y,
                            FONT_REG, 14, CONTENT_W,
                            indent=12*mm,
                            bold_phrases=[bg_number, bg_value, grantee_name])

        # — ย่อหน้าที่ 2 —
        y -= 4*mm
        para2 = (
            'การกระทำใดๆ ที่ผู้รับมอบอำนาจได้กระทำไป เปรียบเสมือนข้าพเจ้าได้กระทำทุกประการ '
            'จึงลงลายมือชื่อไว้ต่อหน้าพยานทั้ง 2 คน และให้พยานลงลายมือชื่อไว้เป็นหลักฐาน '
            'พร้อมทั้งแนบสำเนาบัตรประจำตัวประชาชนของข้าพเจ้าและผู้รับมอบอำนาจมานี้ด้วย'
        )
        y = _draw_paragraph(c, para2, MARGIN_L, y,
                            FONT_REG, 14, CONTENT_W,
                            indent=12*mm)

        # — ลายเซ็น (2 คอลัมน์) —
        y -= 14*mm
        sig_right_x = PAGE_W - MARGIN_R - 45*mm   # กลางคอลัมน์ขวา
        line_len = 38*mm

        def _draw_sig_block(cx, label, name_text):
            """วาด 1 ช่องลายเซ็น"""
            c.setLineWidth(0.5)
            c.line(cx - line_len/2, y + 4*mm, cx + line_len/2, y + 4*mm)
            c.setFont(FONT_REG, 14)
            c.drawCentredString(cx, y, label)
            c.drawCentredString(cx, y - 6*mm, f'({name_text})')

        # ผู้มอบอำนาจ (ขวา)
        _draw_sig_block(sig_right_x, 'ผู้มอบอำนาจ', grantor_name)

        y -= 18*mm
        # ผู้รับมอบอำนาจ (ขวา)
        _draw_sig_block(sig_right_x, 'ผู้รับมอบอำนาจ', grantee_name)

        y -= 18*mm
        # พยาน 1 (ขวา)
        _draw_sig_block(sig_right_x, 'พยาน', w1_name)

        y -= 18*mm
        # พยาน 2 (ขวา)
        _draw_sig_block(sig_right_x, 'พยาน', w2_name)

        # — ติดอากรแสตมป์ (ซ้ายล่าง) —
        c.setFont(FONT_REG, 11)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(MARGIN_L, y - 4*mm, 'ติดอากรแสตมป์ 10 บาท')
        c.setFillColorRGB(0, 0, 0)

        # — Footer —
        _draw_footer(c, entity)

        c.showPage()
        c.save()

        pdf_bytes = buf.getvalue()
        pdf_b64   = base64.b64encode(pdf_bytes).decode('utf-8')
        file_name = f'หนังสือมอบอำนาจ_{contract_id.replace("/", "-")}.pdf'

        return jsonify({'success': True, 'pdfBase64': pdf_b64, 'fileName': file_name})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════════
# Registration helper — เรียกจาก app.py
# ══════════════════════════════════════════════════════════════════════

def register_bg_withdraw_routes(app):
    """
    เรียกจาก app.py:
        from generate_bg_withdraw import register_bg_withdraw_routes
        register_bg_withdraw_routes(app)
    """
    app.add_url_rule(
        '/generate_bg_withdraw', 'generate_bg_withdraw',
        generate_bg_withdraw, methods=['POST']
    )
    app.add_url_rule(
        '/generate_bg_poa', 'generate_bg_poa',
        generate_bg_poa, methods=['POST']
    )
