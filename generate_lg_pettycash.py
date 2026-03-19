#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_lg_pettycash.py
========================
PDF Generator สำหรับ:
  1. Request Approve LG (ขออนุมัติหนังสือค้ำประกัน) — auto-expand ไม่จำกัดรายการ
  2. Petty Cash (เอกสารขออนุมัติเบิกจ่ายเงินสดย่อย)

ใช้ reportlab + FreeSerif Thai font — pixel-perfect output
Upload ไปที่ Railway/Render project แล้ว import ใน app.py
"""

import io
import base64
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ============================================================
# FONT REGISTRATION
# ============================================================
FONT_PATH = '/usr/share/fonts/truetype/freefont/'

def register_fonts():
    try:
        pdfmetrics.registerFont(TTFont('FreeSerif', FONT_PATH + 'FreeSerif.ttf'))
        pdfmetrics.registerFont(TTFont('FreeSerif-Bold', FONT_PATH + 'FreeSerifBold.ttf'))
        pdfmetrics.registerFont(TTFont('FreeSerif-Italic', FONT_PATH + 'FreeSerifItalic.ttf'))
        pdfmetrics.registerFont(TTFont('FreeSerif-BoldItalic', FONT_PATH + 'FreeSerifBoldItalic.ttf'))
    except Exception as e:
        print(f"Font registration error: {e}")

register_fonts()

# ============================================================
# CONSTANTS
# ============================================================
PAGE_W, PAGE_H = A4
MARGIN_L = 22 * mm
MARGIN_R = 22 * mm
MARGIN_T = 18 * mm
MARGIN_B = 16 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

# สี
C_PRIMARY  = HexColor('#1a237e')
C_ACCENT   = HexColor('#1e40af')
C_HEADER   = HexColor('#333333')
C_TEXT     = HexColor('#222222')
C_MUTED    = HexColor('#666666')
C_LIGHT    = HexColor('#999999')
C_BG       = HexColor('#f8f9fa')
C_BG2      = HexColor('#e8eaf6')
C_BORDER   = HexColor('#cccccc')
C_BORDER2  = HexColor('#e2e8f0')
C_RED      = HexColor('#c62828')
C_GREEN    = HexColor('#0d9488')
C_ROW_ALT  = HexColor('#f5f5ff')

# ============================================================
# UTILITY
# ============================================================

def _fmtm(val):
    """จัดรูปแบบตัวเลขเงิน → '1,234.56' หรือ '-'"""
    try:
        n = float(str(val or '0').replace(',', ''))
        return '-' if n == 0 else f"{n:,.2f}"
    except (ValueError, TypeError):
        return '-'

def _fmtm_blank(val):
    """จัดรูปแบบตัวเลขเงิน → '' ถ้า 0"""
    try:
        n = float(str(val or '0').replace(',', ''))
        return '' if n == 0 else f"{n:,.2f}"
    except (ValueError, TypeError):
        return ''

def _parse(val):
    try:
        return float(str(val or '0').replace(',', ''))
    except (ValueError, TypeError):
        return 0.0

def _s(val, default='-'):
    s = str(val or '').strip()
    return s if s else default

def _today_be():
    now = datetime.now()
    return f"{now.day:02d}/{now.month:02d}/{now.year + 543}"

def _dt(c, x, y, text, font='FreeSerif', size=9, color=C_TEXT, align='left'):
    """วาดข้อความ"""
    c.setFont(font, size)
    c.setFillColor(color)
    if align == 'center':
        c.drawCentredString(x, y, text)
    elif align == 'right':
        c.drawRightString(x, y, text)
    else:
        c.drawString(x, y, text)

def _dl(c, x1, y1, x2, y2, color=C_BORDER, width=0.5, dash=None):
    """วาดเส้น"""
    c.setStrokeColor(color)
    c.setLineWidth(width)
    if dash:
        c.setDash(dash[0], dash[1])
    else:
        c.setDash([], 0)
    c.line(x1, y1, x2, y2)
    c.setDash([], 0)

def _dr(c, x, y, w, h, fill=None, stroke=C_BORDER, sw=0.5, r=0):
    """วาดสี่เหลี่ยม"""
    c.setStrokeColor(stroke)
    c.setLineWidth(sw)
    if fill:
        c.setFillColor(fill)
        if r > 0:
            c.roundRect(x, y, w, h, r, fill=1, stroke=1)
        else:
            c.rect(x, y, w, h, fill=1, stroke=1)
    else:
        if r > 0:
            c.roundRect(x, y, w, h, r, fill=0, stroke=1)
        else:
            c.rect(x, y, w, h, fill=0, stroke=1)


# ============================================================
# 1. REQUEST APPROVE LG
# ============================================================

def generate_lg_pdf(data):
    """
    สร้าง PDF — Request Approve LG
    รับ data dict ที่มี: companyName, address, phone, fax, taxId,
    date, createdBy, note, items[]
    คืน bytes ของ PDF
    """
    buf = io.BytesIO()
    cv = canvas.Canvas(buf, pagesize=A4)

    items = data.get('items', [])
    if not items:
        items = [{}]

    total_amount = sum(_parse(it.get('amount')) for it in items)
    total_fee = sum(_parse(it.get('fee')) for it in items)

    # Column widths
    col_w_raw = [18, 52, 55, 130, 35, 52, 52, 28, 65, 65]
    scale = CONTENT_W / sum(col_w_raw)
    col_w = [w * scale for w in col_w_raw]

    row_h = 28
    header_row_h = 22
    first_page_max = 12
    next_page_max = 22

    # แบ่งรายการเป็น pages
    pages = []
    rem = items[:]
    pages.append(rem[:first_page_max])
    rem = rem[first_page_max:]
    while rem:
        pages.append(rem[:next_page_max])
        rem = rem[next_page_max:]
    total_pages = len(pages)

    for pi, page_items in enumerate(pages):
        is_first = (pi == 0)
        is_last = (pi == total_pages - 1)
        y = PAGE_H - MARGIN_T
        tx = MARGIN_L

        # ── HEADER ──
        if is_first:
            _dt(cv, PAGE_W/2, y, _s(data.get('companyName'), ''), 'FreeSerif-Bold', 11, C_HEADER, 'center')
            y -= 12
            en = _s(data.get('companyNameEn'), '')
            if en != '-':
                _dt(cv, PAGE_W/2, y, f"{en} (สำนักงานใหญ่)", 'FreeSerif', 8, C_MUTED, 'center')
                y -= 10
            addr = _s(data.get('address'), '')
            if addr != '-':
                _dt(cv, PAGE_W/2, y, addr, 'FreeSerif', 7.5, C_LIGHT, 'center')
                y -= 9
            info = f"โทร. {_s(data.get('phone'))}  แฟกซ์: {_s(data.get('fax'))}  เลขประจำตัวผู้เสียภาษี: {_s(data.get('taxId'))}"
            _dt(cv, PAGE_W/2, y, info, 'FreeSerif', 7.5, C_LIGHT, 'center')
            y -= 14

            _dl(cv, MARGIN_L, y, PAGE_W-MARGIN_R, y, C_HEADER, 1.2)
            y -= 16
            _dt(cv, PAGE_W/2, y, 'Request Approve LG (ขออนุมัติหนังสือค้ำประกัน)', 'FreeSerif-Bold', 13, C_HEADER, 'center')
            y -= 10
            _dl(cv, MARGIN_L, y, PAGE_W-MARGIN_R, y, C_HEADER, 1.2)
            y -= 16

            c1l = MARGIN_L; c1v = MARGIN_L+55; c2l = PAGE_W/2+10; c2v = PAGE_W/2+75
            _dt(cv, c1l, y, 'Date :', 'FreeSerif-Bold', 8.5, C_MUTED)
            _dt(cv, c1v, y, _s(data.get('date', _today_be())), 'FreeSerif', 9, C_TEXT)
            _dt(cv, c2l, y, 'Create LG By :', 'FreeSerif-Bold', 8.5, C_MUTED)
            _dt(cv, c2v, y, _s(data.get('createdBy'), ''), 'FreeSerif', 9, C_TEXT)
            y -= 13
            _dt(cv, c1l, y, 'จำนวนรายการ :', 'FreeSerif-Bold', 8.5, C_MUTED)
            _dt(cv, c1v, y, f"{len(items)} รายการ", 'FreeSerif', 9, C_TEXT)
            _dt(cv, c2l, y, 'รวมวงเงินทั้งหมด :', 'FreeSerif-Bold', 8.5, C_MUTED)
            _dt(cv, c2v, y, f"{_fmtm(total_amount)} บาท", 'FreeSerif-Bold', 9, C_ACCENT)
            y -= 16
        else:
            _dt(cv, MARGIN_L, y, 'Request Approve LG (ต่อ)', 'FreeSerif-Bold', 9, C_HEADER)
            _dt(cv, PAGE_W-MARGIN_R, y, f"หน้า {pi+1}/{total_pages}", 'FreeSerif', 7, C_LIGHT, 'right')
            y -= 6
            _dl(cv, MARGIN_L, y, PAGE_W-MARGIN_R, y, C_BORDER, 0.5)
            y -= 14

        # ── TABLE HEADER ──
        th_y = y
        _dr(cv, tx, th_y-header_row_h, CONTENT_W, header_row_h, fill=HexColor('#eeeeee'), stroke=C_BORDER, sw=0.5)
        headers = ['No.', 'SR No.', 'เลขสัญญา', 'ชื่อโครงการ / คู่สัญญา', 'สถานะ', 'เริ่มต้น', 'สิ้นสุด', 'เดือน', 'วงเงิน BG', 'ค่าธรรมเนียม']
        h_al = ['center','left','left','left','center','left','left','center','right','right']
        cx = tx
        for hdr, ha, cw in zip(headers, h_al, col_w):
            hx = cx+cw/2 if ha=='center' else (cx+3 if ha=='left' else cx+cw-3)
            _dt(cv, hx, th_y-header_row_h+7, hdr, 'FreeSerif-Bold', 7.5, C_HEADER, ha)
            cx += cw
        cx = tx
        for cw in col_w:
            cx += cw
            if cx < tx+CONTENT_W-1:
                _dl(cv, cx, th_y, cx, th_y-header_row_h, C_BORDER, 0.3)
        y = th_y - header_row_h

        # ── ROWS ──
        start_idx = 0 if pi == 0 else first_page_max + (pi-1)*next_page_max
        for ri, item in enumerate(page_items):
            abs_i = start_idx + ri
            ry = y - row_h
            bg = C_ROW_ALT if ri % 2 == 1 else None
            _dr(cv, tx, ry, CONTENT_W, row_h, fill=bg, stroke=C_BORDER2, sw=0.3)
            cx = tx
            for cw in col_w:
                cx += cw
                if cx < tx+CONTENT_W-1:
                    _dl(cv, cx, y, cx, ry, C_BORDER2, 0.3)

            cx = tx
            ty1 = ry + row_h - 10
            ty2 = ry + row_h - 20

            _dt(cv, cx+col_w[0]/2, ty1, str(abs_i+1), 'FreeSerif', 8, C_TEXT, 'center'); cx += col_w[0]
            _dt(cv, cx+3, ty1, _s(item.get('sr'),'-'), 'FreeSerif', 8, C_TEXT); cx += col_w[1]
            _dt(cv, cx+3, ty1, _s(item.get('contract'),'-'), 'FreeSerif', 8, C_TEXT); cx += col_w[2]

            proj = _s(item.get('project'),'-')
            cust = _s(item.get('customer'),'')
            if len(proj)>28: proj = proj[:27]+'…'
            _dt(cv, cx+3, ty1, proj, 'FreeSerif-Bold', 8, C_TEXT)
            if cust and cust!='-':
                if len(cust)>28: cust = cust[:27]+'…'
                _dt(cv, cx+3, ty2, cust, 'FreeSerif', 7, C_MUTED)
            cx += col_w[3]

            is_urg = item.get('urgent') in [True,'TRUE','true','1']
            if is_urg:
                bw, bh = 24, 10
                _dr(cv, cx+(col_w[4]-bw)/2, ty1-2, bw, bh, fill=HexColor('#ffebee'), stroke=HexColor('#ef9a9a'), sw=0.3, r=2)
                _dt(cv, cx+col_w[4]/2, ty1, 'ด่วน', 'FreeSerif-Bold', 6.5, C_RED, 'center')
            else:
                _dt(cv, cx+col_w[4]/2, ty1, 'ปกติ', 'FreeSerif', 6.5, C_LIGHT, 'center')
            cx += col_w[4]

            _dt(cv, cx+3, ty1, _s(item.get('start'),'-'), 'FreeSerif', 7.5, C_TEXT); cx += col_w[5]
            _dt(cv, cx+3, ty1, _s(item.get('end'),'-'), 'FreeSerif', 7.5, C_TEXT); cx += col_w[6]
            _dt(cv, cx+col_w[7]/2, ty1, _s(item.get('duration'),'-'), 'FreeSerif', 8, C_TEXT, 'center'); cx += col_w[7]
            _dt(cv, cx+col_w[8]-3, ty1, _fmtm(item.get('amount')), 'FreeSerif', 8, C_TEXT, 'right'); cx += col_w[8]
            _dt(cv, cx+col_w[9]-3, ty1, _fmtm(item.get('fee')), 'FreeSerif', 8, C_TEXT, 'right')
            y = ry

        # ── TOTAL + SIGNATURES (หน้าสุดท้าย) ──
        if is_last:
            th = 18; ty = y - th
            _dr(cv, tx, ty, CONTENT_W, th, fill=C_BG2, stroke=C_BORDER, sw=0.5)
            lx = tx
            for i in range(8): lx += col_w[i]
            _dt(cv, lx-5, ty+5, 'รวมทั้งหมด', 'FreeSerif-Bold', 8.5, C_HEADER, 'right')
            _dt(cv, tx+sum(col_w[:9])-3, ty+5, _fmtm(total_amount), 'FreeSerif-Bold', 8.5, C_HEADER, 'right')
            _dt(cv, tx+sum(col_w[:10])-3, ty+5, _fmtm(total_fee), 'FreeSerif-Bold', 8.5, C_HEADER, 'right')
            y = ty - 8

            _dr(cv, MARGIN_L+CONTENT_W*0.4, y-22, CONTENT_W*0.6, 22, fill=C_BG2, stroke=C_BORDER2, sw=0.3, r=4)
            _dt(cv, PAGE_W-MARGIN_R-8, y-14, f"Total Fee : {_fmtm(total_fee)} บาท", 'FreeSerif-Bold', 11, C_PRIMARY, 'right')
            y -= 32

            note = _s(data.get('note',''), '')
            if note and note != '-':
                _dt(cv, MARGIN_L, y, 'หมายเหตุ :', 'FreeSerif-Bold', 8.5, C_MUTED)
                y -= 12
                _dt(cv, MARGIN_L+5, y, note, 'FreeSerif', 9, C_TEXT)
                y -= 16

            y -= 8
            sw = CONTENT_W/2 - 10
            for sx, lbl in [(MARGIN_L, 'ผู้ขอ (Requested By)'), (MARGIN_L+sw+20, 'ผู้อนุมัติ (Approved By)')]:
                _dt(cv, sx, y, lbl, 'FreeSerif-Bold', 8, C_MUTED)
                _dl(cv, sx, y-28, sx+sw-10, y-28, C_BORDER, 0.5, (2,2))
                _dt(cv, sx, y-38, 'ลงชื่อ ...................................', 'FreeSerif', 7, C_LIGHT)
                _dt(cv, sx, y-48, 'วันที่ ......../........./............', 'FreeSerif', 7, C_LIGHT)

        # Footer ทุกหน้า
        _dl(cv, MARGIN_L, MARGIN_B+10, PAGE_W-MARGIN_R, MARGIN_B+10, C_BORDER2, 0.3)
        ftxt = f"Request Approve LG — Contract Tracker Pro  |  Generated: {_today_be()}  |  หน้า {pi+1}/{total_pages}"
        _dt(cv, PAGE_W/2, MARGIN_B+2, ftxt, 'FreeSerif', 6.5, C_LIGHT, 'center')

        if not is_last:
            cv.showPage()

    cv.save()
    buf.seek(0)
    return buf.getvalue()


# ============================================================
# 2. PETTY CASH
# ============================================================

def generate_pettycash_pdf(data):
    """
    สร้าง PDF — เอกสารขออนุมัติเบิกจ่ายเงินสดย่อย
    รับ data dict ที่มี: companyName, address, phone, fax, taxId,
    payee, payMethod, payDate, docRef, items[], requester, receiver, accounting, approver
    คืน bytes ของ PDF
    """
    buf = io.BytesIO()
    cv = canvas.Canvas(buf, pagesize=A4)

    items = data.get('items', [])
    payee = _s(data.get('payee'), '')
    pay_method = data.get('payMethod', 'cash')
    pay_date = _s(data.get('payDate', _today_be()))
    doc_ref = _s(data.get('docRef'), '')

    tot_amt = sum(_parse(it.get('amount')) for it in items)
    tot_vat = sum(_parse(it.get('vat')) for it in items)
    tot_wht = sum(_parse(it.get('wht')) for it in items)
    tot_net = sum(_parse(it.get('net')) for it in items)

    y = PAGE_H - MARGIN_T
    tx = MARGIN_L

    # ── HEADER ──
    _dl(cv, MARGIN_L, y+2, PAGE_W-MARGIN_R, y+2, C_PRIMARY, 2)
    _dt(cv, PAGE_W/2, y-10, _s(data.get('companyName'),''), 'FreeSerif-Bold', 11, C_PRIMARY, 'center')
    en = _s(data.get('companyNameEn'), '')
    if en != '-':
        _dt(cv, PAGE_W/2, y-21, f"{en} (สำนักงานใหญ่)", 'FreeSerif', 8, C_MUTED, 'center')
    addr = _s(data.get('address'), '')
    if addr != '-':
        _dt(cv, PAGE_W/2, y-31, addr, 'FreeSerif', 7.5, C_LIGHT, 'center')
    info = f"โทร. {_s(data.get('phone'))}  แฟกซ์: {_s(data.get('fax'))}  เลขประจำตัวผู้เสียภาษี: {_s(data.get('taxId'))}"
    _dt(cv, PAGE_W/2, y-40, info, 'FreeSerif', 7.5, C_LIGHT, 'center')
    y -= 48
    _dl(cv, MARGIN_L, y, PAGE_W-MARGIN_R, y, C_PRIMARY, 1.5)
    y -= 18

    # ── TITLE ──
    _dr(cv, MARGIN_L, y-16, CONTENT_W, 16, fill=C_BG, stroke=C_BORDER2, sw=0.3, r=3)
    _dt(cv, PAGE_W/2, y-12, 'เอกสารขออนุมัติเบิกจ่าย เงินสดย่อย ( Petty Cash )', 'FreeSerif-Bold', 10.5, C_PRIMARY, 'center')
    y -= 24

    # ── INFO ──
    _dt(cv, MARGIN_L, y, 'จ่ายให้ บมจ./บจก./หจก./หสม./บุคคลธรรมดา', 'FreeSerif-Bold', 8.5, C_MUTED)
    _dt(cv, MARGIN_L+190, y, payee if payee!='-' else '', 'FreeSerif', 9, C_TEXT)
    _dl(cv, MARGIN_L+188, y-2, PAGE_W-MARGIN_R, y-2, C_BORDER, 0.5, (1,2))
    y -= 16

    _dt(cv, MARGIN_L, y, 'ชำระโดย', 'FreeSerif-Bold', 8.5, C_MUTED)
    cbx = MARGIN_L + 38
    _dr(cv, cbx, y-2, 9, 9, stroke=C_HEADER, sw=0.5)
    if pay_method == 'cheque':
        _dt(cv, cbx+4.5, y, '✓', 'FreeSerif-Bold', 7, C_PRIMARY, 'center')
    _dt(cv, cbx+12, y, 'เช็ค', 'FreeSerif', 8.5, C_TEXT)
    cbx2 = cbx + 42
    _dr(cv, cbx2, y-2, 9, 9, stroke=C_HEADER, sw=0.5)
    if pay_method == 'cash':
        _dt(cv, cbx2+4.5, y, '✓', 'FreeSerif-Bold', 7, C_PRIMARY, 'center')
    _dt(cv, cbx2+12, y, 'เงินสด', 'FreeSerif', 8.5, C_TEXT)

    dlx = cbx2+55
    _dt(cv, dlx, y, 'ลงวันที่', 'FreeSerif-Bold', 8.5, C_MUTED)
    _dt(cv, dlx+35, y, pay_date, 'FreeSerif', 9, C_TEXT)
    _dl(cv, dlx+33, y-2, dlx+100, y-2, C_BORDER, 0.5, (1,2))
    rlx = dlx+110
    _dt(cv, rlx, y, 'เลขที่', 'FreeSerif-Bold', 8.5, C_MUTED)
    _dt(cv, rlx+28, y, doc_ref if doc_ref!='-' else '', 'FreeSerif', 9, C_TEXT)
    _dl(cv, rlx+26, y-2, PAGE_W-MARGIN_R, y-2, C_BORDER, 0.5, (1,2))
    y -= 18

    # ── TABLE ──
    row_h = 22
    hdr_h = 24
    pc_raw = [24, 42, 130, 58, 68, 48, 58, 68]
    pc_s = CONTENT_W / sum(pc_raw)
    pc_w = [w * pc_s for w in pc_raw]

    th_y = y
    _dr(cv, tx, th_y-hdr_h, CONTENT_W, hdr_h, fill=C_PRIMARY, stroke=C_PRIMARY, sw=0.5)
    hdrs = [('ลำดับ',), ('รหัสงาน',), ('รายการ',), ('เลขที่','เอกสาร'), ('รายจ่ายก่อน','หักภาษี'), ('ภาษีซื้อ',), ('ภาษีหัก ณ','ที่จ่าย (__%)')  , ('จำนวนเงิน','สุทธิ')]
    cx = tx
    for hi, (hdr_tuple, cw) in enumerate(zip(hdrs, pc_w)):
        if len(hdr_tuple) == 2:
            _dt(cv, cx+cw/2, th_y-8, hdr_tuple[0], 'FreeSerif-Bold', 7.5, white, 'center')
            _dt(cv, cx+cw/2, th_y-17, hdr_tuple[1], 'FreeSerif-Bold', 7, white, 'center')
        else:
            _dt(cv, cx+cw/2, th_y-hdr_h+8, hdr_tuple[0], 'FreeSerif-Bold', 7.5, white, 'center')
        cx += cw
    y = th_y - hdr_h

    display_n = max(len(items), 6)
    for ri in range(display_n):
        item = items[ri] if ri < len(items) else {}
        ry = y - row_h
        bg = C_ROW_ALT if ri % 2 == 1 else None
        _dr(cv, tx, ry, CONTENT_W, row_h, fill=bg, stroke=C_BORDER2, sw=0.3)
        cx = tx
        for cw in pc_w:
            cx += cw
            if cx < tx+CONTENT_W-1:
                _dl(cv, cx, y, cx, ry, C_BORDER2, 0.3)

        cx = tx; tty = ry + row_h - 9
        seq = item.get('seq', ri+1) if item else ri+1
        _dt(cv, cx+pc_w[0]/2, tty, str(seq) if item else '', 'FreeSerif', 8, C_TEXT, 'center'); cx += pc_w[0]
        _dt(cv, cx+3, tty, _s(item.get('jobCode'),'') if item.get('jobCode') else '', 'FreeSerif', 8, C_TEXT); cx += pc_w[1]
        desc = _s(item.get('description'),'') if item.get('description') else ''
        if len(desc)>35: desc = desc[:34]+'…'
        _dt(cv, cx+3, tty, desc, 'FreeSerif', 8, C_TEXT); cx += pc_w[2]
        _dt(cv, cx+3, tty, _s(item.get('docNo'),'') if item.get('docNo') else '', 'FreeSerif', 7.5, C_TEXT); cx += pc_w[3]
        _dt(cv, cx+pc_w[4]-3, tty, _fmtm_blank(item.get('amount')), 'FreeSerif', 8, C_TEXT, 'right'); cx += pc_w[4]
        _dt(cv, cx+pc_w[5]-3, tty, _fmtm_blank(item.get('vat')), 'FreeSerif', 8, C_TEXT, 'right'); cx += pc_w[5]
        _dt(cv, cx+pc_w[6]-3, tty, _fmtm_blank(item.get('wht')), 'FreeSerif', 8, C_TEXT, 'right'); cx += pc_w[6]
        _dt(cv, cx+pc_w[7]-3, tty, _fmtm_blank(item.get('net')), 'FreeSerif', 8, C_TEXT, 'right')
        y = ry

    # ── TOTAL ──
    tth = 20; tty = y - tth
    _dr(cv, tx, tty, CONTENT_W, tth, fill=C_BG2, stroke=C_BORDER, sw=0.5)
    _dt(cv, tx+sum(pc_w[:4])/2, tty+6, 'รวมทั้งหมด', 'FreeSerif-Bold', 8.5, C_PRIMARY, 'center')
    _dt(cv, tx+sum(pc_w[:5])-3, tty+6, _fmtm(tot_amt) if tot_amt else '', 'FreeSerif-Bold', 8, C_PRIMARY, 'right')
    _dt(cv, tx+sum(pc_w[:6])-3, tty+6, _fmtm(tot_vat) if tot_vat else '', 'FreeSerif-Bold', 8, C_PRIMARY, 'right')
    _dt(cv, tx+sum(pc_w[:7])-3, tty+6, _fmtm(tot_wht) if tot_wht else '', 'FreeSerif-Bold', 8, C_PRIMARY, 'right')
    _dt(cv, tx+sum(pc_w[:8])-3, tty+6, _fmtm(tot_net) if tot_net else '', 'FreeSerif-Bold', 8, C_GREEN, 'right')
    y = tty - 10

    _dr(cv, MARGIN_L+CONTENT_W*0.35, y-20, CONTENT_W*0.65, 20, fill=C_BG2, stroke=C_BORDER2, sw=0.3, r=4)
    _dt(cv, PAGE_W-MARGIN_R-8, y-13, f"จำนวนเงินสุทธิ : {_fmtm(tot_net) if tot_net else '-'} บาท", 'FreeSerif-Bold', 11, C_GREEN, 'right')
    y -= 32

    # ── SIGNATURES ──
    sw = CONTENT_W/2 - 10
    sigs = [
        ('ผู้ขอเบิก', data.get('requester','')),
        ('ผู้รับเงิน', data.get('receiver','')),
        ('ฝ่ายบัญชี', data.get('accounting','')),
        ('ผู้อนุมัติ', data.get('approver',''))
    ]
    for si, (lbl, name) in enumerate(sigs):
        sx = MARGIN_L if si%2==0 else MARGIN_L+sw+20
        sy = y if si<2 else y-52
        _dt(cv, sx, sy, lbl, 'FreeSerif-Bold', 8, C_MUTED)
        if name:
            _dt(cv, sx+5, sy-12, _s(name,''), 'FreeSerif', 8, C_TEXT)
        _dl(cv, sx, sy-28, sx+sw-10, sy-28, C_BORDER, 0.5, (2,2))
        _dt(cv, sx, sy-36, 'ลงชื่อ ...........................  วันที่ ......../........./............', 'FreeSerif', 7, C_LIGHT)

    # ── FOOTER ──
    _dl(cv, MARGIN_L, MARGIN_B+10, PAGE_W-MARGIN_R, MARGIN_B+10, C_BORDER2, 0.3)
    _dt(cv, PAGE_W/2, MARGIN_B+2, f"เอกสารขออนุมัติเบิกจ่ายเงินสดย่อย (Petty Cash) — Contract Tracker Pro  |  Generated: {_today_be()}", 'FreeSerif', 6.5, C_LIGHT, 'center')

    cv.save()
    buf.seek(0)
    return buf.getvalue()
