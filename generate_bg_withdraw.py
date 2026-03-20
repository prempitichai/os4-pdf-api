#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: overlay-template-v3
"""
generate_bg_withdraw.py
=======================
Railway API endpoints สำหรับสร้าง PDF 2 แบบ:
  1. /generate_bg_withdraw  — หนังสือแจ้งขอถอนหลักประกันสัญญา
  2. /generate_bg_poa       — หนังสือมอบอำนาจขอคืนหนังสือค้ำประกัน

Approach: overlay ข้อความบน template PDF (เหมือน อ.ส.4)
Templates:
  bg_withdraw_template.pdf  — หนังสือขอถอน
  bg_poa_template.pdf       — หนังสือมอบอำนาจ
Font: THSarabunNew
"""

import os, base64, logging
from io import BytesIO
from flask import request, jsonify
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4          # 595 x 842 pt
MARGIN_L  = 25 * mm          # ขอบซ้าย  = 70.9 pt
MARGIN_R  = PAGE_W - 20*mm   # ขอบขวา edge = 538 pt
CONTENT_W = MARGIN_R - MARGIN_L  # 467 pt

FONT_REG  = 'THSarabunNew'
FONT_BOLD = 'THSarabunNew-Bold'

# ── Font registration ──────────────────────────────────────────────────
def _ensure_fonts():
    base     = os.path.dirname(os.path.abspath(__file__))
    font_dir = os.path.join(base, 'fonts')
    for name, fn in [(FONT_REG, 'THSarabunNew.ttf'),
                     (FONT_BOLD, 'THSarabunNew-Bold.ttf')]:
        try:
            pdfmetrics.getFont(name)
        except KeyError:
            p = os.path.join(font_dir, fn)
            if os.path.exists(p):
                pdfmetrics.registerFont(TTFont(name, p))

# ── Template paths ─────────────────────────────────────────────────────
def _tpl_path(name):
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, name)

# ── Number formatter ───────────────────────────────────────────────────
def _fmt(val):
    if not val: return ''
    try:
        n = float(str(val).replace(',', ''))
        return f'{n:,.2f}'
    except Exception:
        return str(val)

# ── Thai-safe word wrap ────────────────────────────────────────────────
def _wrap(c, text, font, size, max_w):
    """ตัดบรรทัด — รองรับ Thai (ไม่มี space) ตัดทีละตัวอักษร"""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    text = str(text or '')
    if not text: return ['']
    lines, cur = [], ''
    for ch in text:
        test = cur + ch
        if stringWidth(test, font, size) <= max_w:
            cur = test
        else:
            sp = cur.rfind(' ')
            if sp > 0:
                lines.append(cur[:sp])
                cur = cur[sp+1:] + ch
            else:
                if cur: lines.append(cur)
                cur = ch
    if cur: lines.append(cur)
    return lines or ['']

# ── Justified line ─────────────────────────────────────────────────────
def _justify(c, line, x, y, font, size, max_w):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    words = line.split(' ')
    if len(words) <= 1:
        c.setFont(font, size); c.drawString(x, y, line); return
    tw = stringWidth(line.replace(' ',''), font, size)
    sw = (max_w - tw) / (len(words)-1)
    cx = x
    c.setFont(font, size)
    for w in words:
        c.drawString(cx, y, w)
        cx += stringWidth(w, font, size) + sw

# ── Draw paragraph (wrap + justify) ───────────────────────────────────
def _para(c, text, x, y, font, size, max_w, lh=None, indent=0, bold=[]):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    if lh is None: lh = size * 1.45
    lines = _wrap(c, text, font, size, max_w - indent)
    for i, ln in enumerate(lines):
        dx = x + (indent if i == 0 else 0)
        lw = max_w - (indent if i == 0 else 0)
        last = (i == len(lines)-1)
        if bold:
            _mixed(c, ln, dx, y, font, FONT_BOLD, size, bold)
        elif last or len(ln.split(' ')) <= 1:
            c.setFont(font, size); c.drawString(dx, y, ln)
        else:
            _justify(c, ln, dx, y, font, size, lw)
        y -= lh
    return y

# ── Mixed bold/regular line ────────────────────────────────────────────
def _mixed(c, line, x, y, freg, fbold, size, phrases):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    tokens = [(line, False)]
    for ph in phrases:
        if not ph: continue
        new = []
        for seg, ib in tokens:
            if ib or ph not in seg:
                new.append((seg, ib))
            else:
                parts = seg.split(ph, 1)
                new += [(parts[0],False),(ph,True),(parts[1],False)]
        tokens = new
    cx = x
    for seg, ib in tokens:
        if not seg: continue
        f = fbold if ib else freg
        c.setFont(f, size); c.drawString(cx, y, seg)
        cx += stringWidth(seg, f, size)

# ── Core: overlay text on template ────────────────────────────────────
def _make_overlay(draw_fn, tpl_file):
    """โหลด template + สร้าง overlay + merge แล้วคืน bytes"""
    _ensure_fonts()
    tpl_path = _tpl_path(tpl_file)
    reader   = PdfReader(tpl_path)
    page     = reader.pages[0]
    pw       = float(page.mediabox.width)
    ph       = float(page.mediabox.height)

    buf = BytesIO()
    c   = canvas.Canvas(buf, pagesize=(pw, ph))
    draw_fn(c, pw, ph)
    c.save(); buf.seek(0)

    overlay = PdfReader(buf).pages[0]
    page.merge_page(overlay)
    writer = PdfWriter()
    writer.add_page(page)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()

# ══════════════════════════════════════════════════════════════════════
# FORM 1: หนังสือแจ้งขอถอนหลักประกันสัญญา
# ══════════════════════════════════════════════════════════════════════
def _draw_withdraw(data):
    contract_id   = str(data.get('contractId','') or '')
    contract_name = str(data.get('contractName','') or '')
    signed_date   = str(data.get('signedDate','') or '')
    company       = str(data.get('company','') or '')
    bg_number     = str(data.get('guaranteeNumber','') or '')
    bg_date       = str(data.get('guaranteeIssueDate','') or '')
    bg_value      = _fmt(data.get('guaranteeValue',''))
    signer        = str(data.get('signerName','') or '')
    signer_pos    = str(data.get('signerPosition','Corporate Lawyers') or 'Corporate Lawyers')
    doc_number    = str(data.get('docNumber','') or contract_id)
    entity        = data.get('entity') or {}
    entity_name   = entity.get('name','บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด')
    entity_short  = 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด'

    def draw(c, pw, ph):
        # เลขที่หนังสือ
        y = ph - 90
        c.setFont(FONT_REG, 14)
        c.drawString(MARGIN_L, y, f'เลขที่ {doc_number}')

        # ชื่อเรื่อง
        y -= 10*mm
        c.setFont(FONT_BOLD, 16)
        c.drawCentredString(pw/2, y, 'หนังสือแจ้งขอถอนหลักประกันสัญญา')

        # เขียนที่
        y -= 12*mm
        c.setFont(FONT_REG, 14)
        c.drawRightString(MARGIN_R, y, f'เขียนที่ {entity_name}')

        # เรื่อง / เรียน
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

        # ย่อหน้า 1
        y -= 10*mm
        p1 = (f'ตามที่{entity_short} ได้ทำสัญญา{contract_name} '
              f'ฉบับเลขที่ {contract_id} ลงวันที่ {signed_date} กับ {company} นั้น')
        y = _para(c, p1, MARGIN_L, y, FONT_REG, 14, CONTENT_W,
                  indent=12*mm, bold=[contract_id])

        # ย่อหน้า 2
        y -= 3*mm
        p2 = (f'บัดนี้{entity_short} ได้ทำงานสำเร็จเสร็จสิ้นเป็นที่เรียบร้อยแล้วตาม'
              f'สัญญาดังกล่าว บริษัทฯ จึงใคร่ขอคืนหนังสือค้ำประกันเลขที่ {bg_number} '
              f'ลงวันที่ {bg_date} มูลค่าค้ำประกัน {bg_value} บาท')
        y = _para(c, p2, MARGIN_L, y, FONT_REG, 14, CONTENT_W,
                  indent=12*mm, bold=[bg_number, bg_value])

        # ย่อหน้า 3
        y -= 3*mm
        p3 = ('ทางบริษัทฯ หวังเป็นอย่างยิ่งว่าจะได้รับความกรุณาจากท่าน '
              'และขอบคุณล่วงหน้ามา ณ ที่นี้')
        y = _para(c, p3, MARGIN_L, y, FONT_REG, 14, CONTENT_W, indent=12*mm)

        # ลงนาม
        y -= 10*mm
        c.setFont(FONT_REG, 14)
        c.drawRightString(MARGIN_R, y, 'ขอแสดงความนับถือ')
        y -= 22*mm
        sc = MARGIN_R - 40*mm
        c.setLineWidth(0.5)
        c.line(sc - 28*mm, y+4*mm, sc+28*mm, y+4*mm)
        c.setFont(FONT_REG, 14)
        c.drawCentredString(sc, y, f'({signer})' if signer else '(......)')
        c.drawCentredString(sc, y-6*mm, signer_pos)
    return draw


# ══════════════════════════════════════════════════════════════════════
# FORM 2: หนังสือมอบอำนาจ
# ══════════════════════════════════════════════════════════════════════
def _draw_poa(data):
    contract_id  = str(data.get('contractId','') or '')
    bg_number    = str(data.get('guaranteeNumber','') or '')
    bg_value     = _fmt(data.get('guaranteeValue',''))
    company      = str(data.get('company','') or '')
    doc_date     = str(data.get('docDate','') or '')
    entity       = data.get('entity') or {}
    grantor      = data.get('grantor') or {}
    grantee      = data.get('grantee') or {}
    witnesses    = data.get('witnesses') or [{},{}]
    while len(witnesses) < 2: witnesses.append({})

    entity_name  = entity.get('name','บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด')
    entity_short = 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด'
    entity_addr  = entity.get('address',
        'ตั้งอยู่เลขที่ 92/54-55 อาคารสาธรธานี 2 ชั้น 19 ถนนสาทรเหนือ แขวงสีลม เขตบางรัก กรุงเทพมหานคร')
    grantor_name = str(grantor.get('name','นายบัณฑิต หมั้นทรัพย์') or '')
    grantor_id   = str(grantor.get('idCard','3101201187013') or '')
    grantee_name = str(grantee.get('name','') or '')
    grantee_id   = str(grantee.get('idCard','') or '')
    grantee_addr = str(grantee.get('address','') or '')
    w1           = str(witnesses[0].get('name','นายปิติชัย พัฒนกิจกุล') or '')
    w2           = str(witnesses[1].get('name','นางสาวสิริกาญจนา จันทร์อ่อน') or '')

    def draw(c, pw, ph):
        # เลขที่สัญญา
        y = ph - 90
        c.setFont(FONT_REG, 14)
        c.drawString(MARGIN_L, y, f'({contract_id})')

        # ชื่อเรื่อง
        y -= 10*mm
        c.setFont(FONT_BOLD, 16)
        c.drawCentredString(pw/2, y, 'หนังสือมอบอำนาจ')

        # ทำที่ / วันที่
        y -= 12*mm
        c.setFont(FONT_REG, 14)
        c.drawRightString(MARGIN_R, y, f'ทำที่ {entity_name}')
        y -= 7*mm
        c.drawRightString(MARGIN_R, y, f'วันที่ {doc_date}')

        # เนื้อหา
        y -= 10*mm
        addr_part = f'ที่อยู่ {grantee_addr} ' if grantee_addr else ''
        body = (f'โดยหนังสือฉบับนี้ ข้าพเจ้า {entity_short} '
                f'{entity_addr} โดย {grantor_name} '
                f'บัตรประชาชนเลขที่ {grantor_id} '
                f'ผู้มีอำนาจกระทำนิติกรรมตามหนังสือรับรองของสำนักงานทะเบียน'
                f'หุ้นส่วนบริษัทกลางกรมพัฒนาธุรกิจการค้า กระทรวงพาณิชย์ '
                f'ขอมอบอำนาจให้ {grantee_name} '
                f'ผู้ถือบัตรประชาชนเลขที่ {grantee_id} '
                f'{addr_part}'
                f'เป็นผู้มีอำนาจดำเนินการรับคืนหนังสือค้ำประกันเลขที่ {bg_number} '
                f'มูลค่า {bg_value} บาท กับ {company}')
        y = _para(c, body, MARGIN_L, y, FONT_REG, 14, CONTENT_W,
                  indent=12*mm, bold=[bg_number, bg_value, grantee_name])

        # ย่อหน้า 2
        y -= 4*mm
        p2 = ('การกระทำใดๆ ที่ผู้รับมอบอำนาจได้กระทำไป เปรียบเสมือนข้าพเจ้าได้กระทำทุกประการ '
              'จึงลงลายมือชื่อไว้ต่อหน้าพยานทั้ง 2 คน และให้พยานลงลายมือชื่อไว้เป็นหลักฐาน '
              'พร้อมทั้งแนบสำเนาบัตรประจำตัวประชาชนของข้าพเจ้าและผู้รับมอบอำนาจมานี้ด้วย')
        y = _para(c, p2, MARGIN_L, y, FONT_REG, 14, CONTENT_W, indent=12*mm)

        # ลายเซ็น 4 ช่อง
        y -= 14*mm
        sc  = MARGIN_R - 45*mm
        ll  = 38*mm

        def sig(label, name, yy):
            c.setLineWidth(0.5)
            c.line(sc-ll/2, yy+4*mm, sc+ll/2, yy+4*mm)
            c.setFont(FONT_REG, 14)
            c.drawCentredString(sc, yy, label)
            c.drawCentredString(sc, yy-6*mm, f'({name})')
            return yy - 18*mm

        y = sig('ผู้มอบอำนาจ', grantor_name, y)
        y = sig('ผู้รับมอบอำนาจ', grantee_name, y)
        y = sig('พยาน', w1, y)
        y = sig('พยาน', w2, y)

        # ติดอากรแสตมป์
        c.setFont(FONT_REG, 11)
        c.setFillColorRGB(0.4,0.4,0.4)
        c.drawString(MARGIN_L, y-4*mm, 'ติดอากรแสตมป์ 10 บาท')
        c.setFillColorRGB(0,0,0)
    return draw


# ══════════════════════════════════════════════════════════════════════
# Flask endpoints
# ══════════════════════════════════════════════════════════════════════
def generate_bg_withdraw():
    try:
        data = request.get_json(force=True) or {}
        pdf  = _make_overlay(_draw_withdraw(data), 'bg_withdraw_template.pdf')
        cid  = str(data.get('contractId','draft') or 'draft')
        return jsonify({'success':True,
                        'pdfBase64': base64.b64encode(pdf).decode(),
                        'fileName': f'หนังสือขอถอนหลักประกัน_{cid.replace("/","-")}.pdf'})
    except Exception as e:
        logger.error(f'bg_withdraw error: {e}')
        return jsonify({'success':False,'message':str(e)}), 500

def generate_bg_poa():
    try:
        data = request.get_json(force=True) or {}
        pdf  = _make_overlay(_draw_poa(data), 'bg_poa_template.pdf')
        cid  = str(data.get('contractId','draft') or 'draft')
        return jsonify({'success':True,
                        'pdfBase64': base64.b64encode(pdf).decode(),
                        'fileName': f'หนังสือมอบอำนาจ_{cid.replace("/","-")}.pdf'})
    except Exception as e:
        logger.error(f'bg_poa error: {e}')
        return jsonify({'success':False,'message':str(e)}), 500

def register_bg_withdraw_routes(app):
    app.add_url_rule('/generate_bg_withdraw','generate_bg_withdraw',
                     generate_bg_withdraw, methods=['POST'])
    app.add_url_rule('/generate_bg_poa','generate_bg_poa',
                     generate_bg_poa, methods=['POST'])
