#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_messenger.py — ใบสั่งงาน Messenger & Logistic
★ v17 — v16 + ปรับหน้าตาให้สวยงาม
  - entity section band (light blue background)
  - title accent underline
  - section separator lines
  - left accent bars สำหรับ section headers
  - signature area background
  พิกัดทุกจุดวัดจาก PDF ต้นแบบโดยตรง (y ของ ReportLab = PH - y_pdf)
  - title        y_pdf=778.6 → t=63
  - entity row1  y_pdf=716.9 → t=125
  - entity row2  y_pdf=688.9 → t=153
  - vehicle      y_pdf=653.9 → t=188
  - urgency      y_pdf=625.9 → t=216
  - วันดำเนิน    y_pdf=599.9 → t=242
  - messenger    y_pdf=563.9 → t=278
  - รายละเอียด  y_pdf=528.9 → t=313 (5 lines: 344,375,406,437,468)
  - นำกลับ       y_pdf=373.9 → t=468 (3 lines: 504,539,575)
  - สถานที่       y_pdf=266.9 → t=575 (3 lines: 603,631,658)
  - sig receiver y_pdf=155.9 → t=686
  - sig order1   y_pdf=127.9 → t=714
  - sig order2   y_pdf=99.9  → t=742
  - sig approver y_pdf=71.9  → t=770
"""
import io
import os
import base64
import logging
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

from messenger_images import SCM_LOGO_B64, SCM_WATERMARK_B64

logger = logging.getLogger(__name__)

# ── FONT REGISTRATION ────────────────────────────────────────────────────────
_FONT_SEARCH_DIRS = [
    './fonts/',
    '/app/fonts/',
    os.path.expanduser('~/fonts/'),
    '/usr/share/fonts/truetype/freefont/',
    './',
]
_FONT_REG = False

def _register_fonts():
    global _FONT_REG
    if _FONT_REG:
        return
    try:
        pdfmetrics.getFont('S')
        pdfmetrics.getFont('SB')
        _FONT_REG = True
        return
    except KeyError:
        pass

    found = False
    for fp in _FONT_SEARCH_DIRS:
        reg_path  = os.path.join(fp, 'THSarabunNew.ttf')
        bold_path = os.path.join(fp, 'THSarabunNew-Bold.ttf')
        if os.path.isfile(reg_path):
            try:
                pdfmetrics.registerFont(TTFont('S',  reg_path))
                if os.path.isfile(bold_path):
                    pdfmetrics.registerFont(TTFont('SB', bold_path))
                else:
                    pdfmetrics.registerFont(TTFont('SB', reg_path))
                    logger.warning(f"ไม่พบ THSarabunNew-Bold.ttf — ใช้ regular แทน")
                logger.info(f"ลงทะเบียนฟอนต์ Messenger จาก: {fp}")
                found = True
                break
            except Exception as e:
                logger.warning(f"Register font ล้มเหลวจาก {fp}: {e}")

    if not found:
        raise FileNotFoundError(
            f"ไม่พบ THSarabunNew.ttf ใน: {_FONT_SEARCH_DIRS}\n"
            "กรุณาวาง font files ไว้ใน ./fonts/ หรือ /app/fonts/"
        )
    _FONT_REG = True


# ── CONSTANTS ────────────────────────────────────────────────────────────────
PW, PH = A4            # 595.276 x 841.890
F       = 'S'          # THSarabunNew regular
FB      = 'SB'         # THSarabunNew bold

FS_T   = 16            # title
FS_LBL = 12            # label
FS_DAT = 10            # data value
FS_DOT = 10            # dots

LX = 50                # left margin (x)
RX = PW - 50           # right margin (x)

C   = HexColor('#333333')   # text ทั่วไป
CF  = HexColor('#1a237e')   # ค่าที่กรอก (น้ำเงินเข้ม)
CB  = HexColor('#bbbbbb')   # dots
CL  = HexColor('#cccccc')   # footer

# Design colors
C_ACCENT  = HexColor('#1a237e')   # blue accent
C_BAND    = HexColor('#eef0ff')   # entity/sig band fill
C_BAND_SIG = HexColor('#f4f5ff')  # sig area fill
C_BAND_BDR = HexColor('#c5cae9')  # band border
C_SEP     = HexColor('#e0e0e8')   # separator line


# ── HELPERS ──────────────────────────────────────────────────────────────────

def Y(t):
    """แปลง t (จากบนลงล่าง) → y coordinate ของ ReportLab (จากล่างขึ้นบน)"""
    return PH - t


def _s(v, d=''):
    s = str(v or '').strip()
    # newlines from textarea → separator
    s = s.replace('\r\n', ' / ').replace('\r', ' / ').replace('\n', ' / ')
    # box/checkbox Unicode chars the Thai font can't render
    for ch in ('☐', '☑', '☒', '□', '■', '▪', '▫'):
        s = s.replace(ch, ' / ')
    s = s.strip(' /')
    return s if s else d


def _tbe():
    n = datetime.now()
    return f"{n.day:02d}/{n.month:02d}/{n.year + 543}"


def _dots(cv, x1, yt, x2):
    """วาด dot line แนวนอน จาก x1 ถึง x2 ที่ตำแหน่ง Y(yt)"""
    if x1 >= x2 - 2:
        return
    cv.setFont(F, FS_DOT)
    cv.setFillColor(CB)
    dw  = cv.stringWidth('.', F, FS_DOT)
    n   = int((x2 - x1) / (dw * 0.8))
    txt = '.' * n
    while cv.stringWidth(txt, F, FS_DOT) > (x2 - x1) and n > 0:
        n -= 1
        txt = '.' * n
    cv.drawString(x1, Y(yt), txt)


def _fdots(cv, yt):
    """full-width dot line"""
    _dots(cv, LX, yt, RX)


def _flines(cv, text, yt_list, first_line_x=None):
    lines = []
    if text:
        mw_first = RX - (first_line_x or LX) - 2
        mw_rest  = RX - LX - 2
        rem = str(text)

        if first_line_x and rem:
            fit = rem
            while len(fit) > 1 and cv.stringWidth(fit, F, FS_DAT) > mw_first:
                fit = fit[:-1]
            lines.append(fit)
            rem = rem[len(fit):]

        while rem and len(lines) < len(yt_list):
            fit = rem
            while len(fit) > 1 and cv.stringWidth(fit, F, FS_DAT) > mw_rest:
                fit = fit[:-1]
            lines.append(fit)
            rem = rem[len(fit):]

    for i, yt in enumerate(yt_list):
        cx = (first_line_x or LX) if i == 0 else LX
        _fdots(cv, yt)

        if i < len(lines) and lines[i]:
            tw = cv.stringWidth(lines[i], F, FS_DAT)
            cv.setFillColor(white)
            cv.rect(cx - 1, Y(yt) - 2, tw + 4, FS_DAT + 3, fill=1, stroke=0)
            cv.setFont(F, FS_DAT)
            cv.setFillColor(CF)
            cv.drawString(cx, Y(yt) + 1, lines[i])


def _draw_checkmark(cv, x, ry, sz, color):
    cv.setStrokeColor(color)
    cv.setLineWidth(1.8)
    p1x = x + sz * 0.15;  p1y = ry + sz * 0.48
    p2x = x + sz * 0.38;  p2y = ry + sz * 0.22
    p3x = x + sz * 0.85;  p3y = ry + sz * 0.72
    cv.line(p1x, p1y, p2x, p2y)
    cv.line(p2x, p2y, p3x, p3y)
    cv.setLineWidth(1.0)


def _chk(cv, x, yt, checked, label):
    sz = 14
    ry = Y(yt) - 2

    cv.setLineWidth(1.0)
    if checked:
        cv.setStrokeColor(HexColor('#4a5eb8'))
        cv.setFillColor(HexColor('#4a5eb8'))
        cv.roundRect(x, ry, sz, sz, 3, fill=1, stroke=1)
        _draw_checkmark(cv, x, ry, sz, white)
    else:
        cv.setStrokeColor(HexColor('#aab0c0'))
        cv.setFillColor(white)
        cv.roundRect(x, ry, sz, sz, 3, fill=1, stroke=1)

    cv.setFont(F, FS_LBL)
    cv.setFillColor(C)
    cv.drawString(x + sz + 5, ry + 1, label)


def _loc_field(cv, lx, yt, label, val, end_x=None):
    """Sub-field ในส่วน สถานที่: label สีเทา 11pt + dots + value ซ้าย"""
    end_x = end_x or RX
    C_SUB = HexColor('#666666')
    cv.setFont(F, 11); cv.setFillColor(C_SUB)
    cv.drawString(lx, Y(yt), label)
    lw = cv.stringWidth(label, F, 11)
    dot_x1 = lx + lw + 4
    _dots(cv, dot_x1, yt + 4, end_x)
    if val:
        vw = cv.stringWidth(val, F, FS_DAT)
        cv.setFillColor(white)
        cv.rect(dot_x1 + 1, Y(yt) - 2, vw + 4, FS_DAT + 3, fill=1, stroke=0)
        cv.setFont(F, FS_DAT); cv.setFillColor(CF)
        cv.drawString(dot_x1 + 2, Y(yt), val)


def _vdots(cv, x, yt, val, end_x):
    _dots(cv, x, yt + 5, end_x)
    if not val:
        return
    vw   = cv.stringWidth(val, F, FS_DAT)
    zone = end_x - x
    vx   = x + (zone - vw) / 2
    cv.setFillColor(white)
    cv.rect(vx - 2, Y(yt) - 2, vw + 4, FS_DAT + 4, fill=1, stroke=0)
    cv.setFont(F, FS_DAT)
    cv.setFillColor(CF)
    cv.drawString(vx, Y(yt), val)


def _flines_inline(cv, text, label_t, label_lw, extra_yt_list):
    mw_first = RX - (LX + label_lw + 8) - 2
    mw_rest  = RX - LX - 2
    lines    = []

    if text:
        rem = str(text)
        if rem:
            fit = rem
            while len(fit) > 1 and cv.stringWidth(fit, F, FS_DAT) > mw_first:
                fit = fit[:-1]
            lines.append(('first', fit))
            rem = rem[len(fit):]
        while rem and len(lines) - 1 < len(extra_yt_list):
            fit = rem
            while len(fit) > 1 and cv.stringWidth(fit, F, FS_DAT) > mw_rest:
                fit = fit[:-1]
            lines.append(('rest', fit))
            rem = rem[len(fit):]

    dot_x1_first = LX + label_lw + 8
    _dots(cv, dot_x1_first, label_t + 5, RX)
    if lines and lines[0][0] == 'first' and lines[0][1]:
        val0 = lines[0][1]
        vw0  = cv.stringWidth(val0, F, FS_DAT)
        cv.setFillColor(white)
        cv.rect(dot_x1_first, Y(label_t) - 3, vw0 + 4, FS_DAT + 4, fill=1, stroke=0)
        cv.setFont(F, FS_DAT); cv.setFillColor(CF)
        cv.drawString(dot_x1_first + 2, Y(label_t), val0)

    rest_vals = [ln[1] for ln in lines if ln[0] == 'rest']
    for i, yt in enumerate(extra_yt_list):
        _fdots(cv, yt)
        if i < len(rest_vals):
            val = rest_vals[i]
            tw  = cv.stringWidth(val, F, FS_DAT)
            cv.setFillColor(white)
            cv.rect(LX - 1, Y(yt) - 2, tw + 4, FS_DAT + 3, fill=1, stroke=0)
            cv.setFont(F, FS_DAT); cv.setFillColor(CF)
            cv.drawString(LX, Y(yt) + 1, val)


def _split_items(v):
    """Split textarea value (newline-separated) into list."""
    s = str(v or '').strip()
    parts = [p.strip() for p in s.replace('\r\n', '\n').replace('\r', '\n').split('\n') if p.strip()]
    return parts or ([s] if s else [])


def _split_csv(v):
    """Split comma-separated value into list."""
    s = str(v or '').strip()
    return [p.strip() for p in s.split(',') if p.strip()]


def _draw_doc_table(cv, items, t_start, t_end):
    """Draw numbered document table: ลำดับ | รายการเอกสาร | จำนวน (ฉบับ)"""
    COL_NUM  = LX + 35
    COL_QTY  = RX - 52
    HEADER_H = 20
    ROW_H    = 18
    FS_TBL   = 9.5

    max_rows = max(1, int((t_end - t_start - HEADER_H) / ROW_H))

    # ── Header ────────────────────────────────────────────────────────────────
    h_bot = Y(t_start + HEADER_H)   # bottom-left y of header rect
    cv.setFillColor(C_BAND)
    cv.rect(LX, h_bot, RX - LX, HEADER_H, fill=1, stroke=0)
    cv.setStrokeColor(C_BAND_BDR); cv.setLineWidth(0.6)
    cv.rect(LX, h_bot, RX - LX, HEADER_H, fill=0, stroke=1)

    hdr_text_y = h_bot + (HEADER_H - FS_TBL) / 2
    cv.setFont(FB, FS_TBL); cv.setFillColor(C_ACCENT)

    lbl_n = 'ลำดับ'
    nw = cv.stringWidth(lbl_n, FB, FS_TBL)
    cv.drawString(LX + (COL_NUM - LX - nw) / 2, hdr_text_y, lbl_n)

    cv.drawString(COL_NUM + 6, hdr_text_y, 'รายการเอกสาร')

    lbl_q = 'จำนวน (ฉบับ)'
    qw = cv.stringWidth(lbl_q, FB, FS_TBL)
    cv.drawString(COL_QTY + (RX - COL_QTY - qw) / 2, hdr_text_y, lbl_q)

    # Vertical dividers in header
    cv.setStrokeColor(C_BAND_BDR); cv.setLineWidth(0.5)
    cv.line(COL_NUM, Y(t_start), COL_NUM, h_bot)
    cv.line(COL_QTY, Y(t_start), COL_QTY, h_bot)

    # ── Rows ──────────────────────────────────────────────────────────────────
    row_items = items[:max_rows]
    for i, item in enumerate(row_items):
        r_bot = Y(t_start + HEADER_H + (i + 1) * ROW_H)
        r_top = r_bot + ROW_H

        if i % 2 == 1:
            cv.setFillColor(HexColor('#f4f5ff'))
            cv.rect(LX, r_bot, RX - LX, ROW_H, fill=1, stroke=0)

        cv.setStrokeColor(HexColor('#e0e0e8')); cv.setLineWidth(0.3)
        cv.line(LX, r_bot, RX, r_bot)
        cv.line(COL_NUM, r_top, COL_NUM, r_bot)
        cv.line(COL_QTY, r_top, COL_QTY, r_bot)

        text_y = r_bot + (ROW_H - FS_TBL) / 2

        # ลำดับ (centered)
        cv.setFont(F, FS_TBL); cv.setFillColor(C)
        ns = str(i + 1)
        nw = cv.stringWidth(ns, F, FS_TBL)
        cv.drawString(LX + (COL_NUM - LX - nw) / 2, text_y, ns)

        # รายการเอกสาร (truncate to fit)
        max_w = COL_QTY - COL_NUM - 12
        txt = _s(item)
        while len(txt) > 1 and cv.stringWidth(txt, F, FS_TBL) > max_w:
            txt = txt[:-1]
        cv.setFont(F, FS_TBL); cv.setFillColor(CF)
        cv.drawString(COL_NUM + 6, text_y, txt)

        # จำนวน (centered, default 1)
        cv.setFont(F, FS_TBL); cv.setFillColor(C)
        qs = '1'
        qw = cv.stringWidth(qs, F, FS_TBL)
        cv.drawString(COL_QTY + (RX - COL_QTY - qw) / 2, text_y, qs)

    # ── Outer border ──────────────────────────────────────────────────────────
    actual_h = HEADER_H + len(row_items) * ROW_H
    cv.setStrokeColor(C_BAND_BDR); cv.setLineWidth(0.7)
    cv.rect(LX, Y(t_start + actual_h), RX - LX, actual_h, fill=0, stroke=1)
    cv.setLineWidth(1.0)


def _rcol_field(cv, lx, yt, label, val, end_x):
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(lx, Y(yt), label)
    lw = cv.stringWidth(label, F, FS_LBL)
    dot_x1 = lx + lw + 4
    dot_x2 = end_x
    _dots(cv, dot_x1, yt + 5, dot_x2)
    if val:
        vw = cv.stringWidth(val, F, FS_DAT)
        mid_x = dot_x1 + (dot_x2 - dot_x1 - vw) / 2
        cv.setFillColor(white)
        cv.rect(mid_x - 2, Y(yt) - 3, vw + 4, FS_DAT + 4, fill=1, stroke=0)
        cv.setFont(F, FS_DAT); cv.setFillColor(CF)
        cv.drawString(mid_x, Y(yt), val)


def _sep(cv, t, color=None, lw=0.5):
    """วาด separator line ที่ t"""
    cv.setStrokeColor(color or C_SEP)
    cv.setLineWidth(lw)
    cv.line(LX, Y(t), RX, Y(t))
    cv.setLineWidth(1.0)


def _accent_bar(cv, t):
    """วาด left accent bar (แถบสีน้ำเงิน) ซ้ายของ section header"""
    cv.setFillColor(C_ACCENT)
    cv.rect(42, Y(t) - 1, 4, 15, fill=1, stroke=0)


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

def generate_messenger_pdf(data):
    """
    สร้าง PDF ใบสั่งงาน Messenger & Logistic
    Layout พิกัดวัดจาก PDF ต้นแบบ (v16) + visual polish (v17)
    """
    _register_fonts()

    d   = data or {}
    buf = io.BytesIO()
    cv  = canvas.Canvas(buf, pagesize=A4)

    # ── Watermark (วาดก่อนสุด อยู่ด้านหลัง) ─────────────────────────────
    try:
        wm = ImageReader(io.BytesIO(base64.b64decode(SCM_WATERMARK_B64)))
        cv.drawImage(wm, 60, Y(380) - 220, width=460, height=220,
                     preserveAspectRatio=True, mask='auto')
    except Exception as e:
        logger.debug(f"Watermark load ล้มเหลว: {e}")

    # ── Logo (top-right) ──────────────────────────────────────────────────
    try:
        logo = ImageReader(io.BytesIO(base64.b64decode(SCM_LOGO_B64)))
        cv.drawImage(logo, RX - 90, Y(18) - 45, width=90, height=45,
                     preserveAspectRatio=True, mask='auto')
    except Exception as e:
        logger.debug(f"Logo load ล้มเหลว: {e}")

    # ── Background bands (วาดก่อน text ทั้งหมด) ──────────────────────────
    # Entity section band (t=108 → t=170)
    cv.setFillColor(C_BAND)
    cv.rect(LX, Y(170), RX - LX, 62, fill=1, stroke=0)
    cv.setStrokeColor(C_BAND_BDR)
    cv.setLineWidth(0.5)
    cv.line(LX, Y(108), RX, Y(108))
    cv.line(LX, Y(170), RX, Y(170))

    # Signature section band (t=676 → t=790)
    cv.setFillColor(C_BAND_SIG)
    cv.rect(LX, Y(790), RX - LX, 114, fill=1, stroke=0)

    cv.setLineWidth(1.0)

    # ── Title: t=63 ───────────────────────────────────────────────────────
    cv.setFont(FB, FS_T)
    cv.setFillColor(C)
    cv.drawCentredString(PW / 2, Y(63), 'ใบสั่งงาน Messenger & Logistic')

    # Title accent underline
    cv.setStrokeColor(C_ACCENT)
    cv.setLineWidth(1.5)
    cv.line(LX + 30, Y(73), RX - 30, Y(73))
    cv.setLineWidth(1.0)

    # ── Entity checkboxes ─────────────────────────────────────────────────
    ent = _s(d.get('entity'), '').lower().replace(' ', '').replace('-', '')
    _ENTITY_NORM = {
        'scmtech': 'scmtech', 'scmt': 'scmtech',
        'scms': 'scms',
        'scmc': 'scmc',
        'holding': 'holding',
        'cyber': 'cyber',
        'bc': 'bc',
        'b2b': 'b2b',
        'fahcloud': 'fahcloud',
    }
    ent = _ENTITY_NORM.get(ent, ent)

    _LABEL_X = [69.0, 192.8, 316.6, 440.5]
    _ENT_ROW1 = [('SCM Tech', 'scmtech'), ('SCM S', 'scms'),
                 ('SCM C',    'scmc'),    ('Holding', 'holding')]
    _ENT_ROW2 = [('Cyber', 'cyber'), ('BC', 'bc'),
                 ('B2B',   'b2b'),   ('Fahcloud', 'fahcloud')]

    for i, (label, key) in enumerate(_ENT_ROW1):
        _chk(cv, _LABEL_X[i] - 20, 125, key == ent, label)

    for i, (label, key) in enumerate(_ENT_ROW2):
        _chk(cv, _LABEL_X[i] - 20, 153, key == ent, label)

    # Separator after entity band
    _sep(cv, 178)

    # ── Vehicle type: t=188 ───────────────────────────────────────────────
    veh = d.get('vehicleType', 'car')
    _veh    = str(veh or 'car').lower().strip()
    is_car  = _veh in ['car', 'รถยนต์']
    is_moto = _veh in ['motorcycle', 'motorbike', 'รถมอเตอร์ไซด์', 'รถมอเตอร์']
    if not is_car and not is_moto:
        is_car = True

    if d.get('vehicle_car') is True:        is_car, is_moto = True, False
    if d.get('vehicle_motorcycle') is True: is_car, is_moto = False, True

    T_VEH = 188

    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(50, Y(T_VEH), '(')
    sz = 14
    ry_v = Y(T_VEH) - 2
    cv.setLineWidth(1.0)
    if is_car:
        cv.setStrokeColor(HexColor('#4a5eb8')); cv.setFillColor(HexColor('#4a5eb8'))
        cv.roundRect(58, ry_v, sz, sz, 3, fill=1, stroke=1)
        _draw_checkmark(cv, 58, ry_v, sz, white)
    else:
        cv.setStrokeColor(HexColor('#aab0c0')); cv.setFillColor(white)
        cv.roundRect(58, ry_v, sz, sz, 3, fill=1, stroke=1)
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(86, Y(T_VEH), ') รถยนต์')

    cv.drawString(165, Y(T_VEH), '(')
    ry_v2 = Y(T_VEH) - 2
    if is_moto:
        cv.setStrokeColor(HexColor('#4a5eb8')); cv.setFillColor(HexColor('#4a5eb8'))
        cv.roundRect(173, ry_v2, sz, sz, 3, fill=1, stroke=1)
        _draw_checkmark(cv, 173, ry_v2, sz, white)
    else:
        cv.setStrokeColor(HexColor('#aab0c0')); cv.setFillColor(white)
        cv.roundRect(173, ry_v2, sz, sz, 3, fill=1, stroke=1)
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(201, Y(T_VEH), ') รถมอเตอร์ไซด์')

    _rcol_field(cv, 310, T_VEH, 'เลข PR :', _s(d.get('contractNumber')), RX)

    # ── Urgency: t=216 ───────────────────────────────────────────────────
    urg = d.get('isUrgent') in [True, 'TRUE', 'true', '1']
    if d.get('urgent_true') is True:  urg = True
    if d.get('urgent_false') is True: urg = False

    T_URG = 216

    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(50, Y(T_URG), '(')
    ry_u = Y(T_URG) - 2
    cv.setLineWidth(1.0)
    if urg:
        cv.setStrokeColor(HexColor('#4a5eb8')); cv.setFillColor(HexColor('#4a5eb8'))
        cv.roundRect(58, ry_u, sz, sz, 3, fill=1, stroke=1)
        _draw_checkmark(cv, 58, ry_u, sz, white)
    else:
        cv.setStrokeColor(HexColor('#aab0c0')); cv.setFillColor(white)
        cv.roundRect(58, ry_u, sz, sz, 3, fill=1, stroke=1)
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(86, Y(T_URG), ') ด่วน')

    cv.drawString(165, Y(T_URG), '(')
    ry_u2 = Y(T_URG) - 2
    if not urg:
        cv.setStrokeColor(HexColor('#4a5eb8')); cv.setFillColor(HexColor('#4a5eb8'))
        cv.roundRect(173, ry_u2, sz, sz, 3, fill=1, stroke=1)
        _draw_checkmark(cv, 173, ry_u2, sz, white)
    else:
        cv.setStrokeColor(HexColor('#aab0c0')); cv.setFillColor(white)
        cv.roundRect(173, ry_u2, sz, sz, 3, fill=1, stroke=1)
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(201, Y(T_URG), ') ไม่ด่วน')

    _rcol_field(cv, 310, T_URG, 'วันที่สั่งงาน :', _s(d.get('orderDate', _tbe())), RX)

    # ── วันที่ดำเนินงาน: t=242 ───────────────────────────────────────────
    T_OPD = 242
    _rcol_field(cv, 310, T_OPD, 'วันที่ดำเนินงาน :', _s(d.get('operationDate')), RX)

    # Separator before messenger section
    _sep(cv, 264)

    # ── ชื่อเจ้าหน้าที่: t=278 ───────────────────────────────────────────
    T_MSG = 278
    lbl_msg = 'ชื่อเจ้าหน้าที่ (Messenger / Logistic):'
    cv.setFont(FB, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(T_MSG), lbl_msg)
    lw_msg = cv.stringWidth(lbl_msg, FB, FS_LBL)
    nm_val = _s(d.get('messengerName', 'พี่วุฒ'))
    dot_nm_x1 = LX + lw_msg + 8
    _dots(cv, dot_nm_x1, T_MSG + 5, RX)
    if nm_val:
        cv.setFont(F, FS_DAT); cv.setFillColor(CF)
        vw_nm = cv.stringWidth(nm_val, F, FS_DAT)
        mid_nm = dot_nm_x1 + (RX - dot_nm_x1 - vw_nm) / 2
        cv.setFillColor(white)
        cv.rect(mid_nm - 2, Y(T_MSG) - 3, vw_nm + 4, FS_DAT + 4, fill=1, stroke=0)
        cv.setFont(F, FS_DAT); cv.setFillColor(CF)
        cv.drawString(mid_nm, Y(T_MSG), nm_val)

    # Separator before content sections
    _sep(cv, 300)

    # ── รายละเอียดของงาน: label t=313, table t=326–464 ──────────────────
    _accent_bar(cv, 313)
    cv.setFont(FB, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(313), 'รายละเอียดของงานที่ให้ไปรับ-ส่ง:')
    _draw_doc_table(cv, _split_items(d.get('jobDetail')), 326, 464)

    # ── สิ่งที่นำกลับ: label t=468, table t=481–571 ─────────────────────
    _accent_bar(cv, 468)
    cv.setFont(FB, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(468), 'สิ่งที่นำกลับ :')
    _draw_doc_table(cv, _split_csv(d.get('returnItems')), 481, 571)

    # ── สถานที่: แบ่งช่องแยก (t=575–651) ────────────────────────────────────
    _accent_bar(cv, 575)
    cv.setFont(FB, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(575), 'สถานที่ ส่งงาน-รับงาน:')

    # บริษัท / สถานที่ (t=593)
    _loc_field(cv, LX + 8, 593, 'บริษัท / สถานที่ :',
               _s(d.get('locationCompany', d.get('location'))))

    # ที่อยู่ (t=614 + overflow t=632) — fallback to old field name 'locationDetail'
    addr_full = _s(d.get('locationAddress', d.get('locationDetail')))
    _loc_field(cv, LX + 8, 614, 'ที่อยู่ :', addr_full)
    # overflow line 2 — ถ้า address ยาว
    if addr_full:
        lw_a = cv.stringWidth('ที่อยู่ :', F, 11)
        dot_x_a = LX + 8 + lw_a + 4
        mw_a = RX - dot_x_a - 2
        mw_rest = RX - LX - 8 - 2
        fit1 = addr_full
        while len(fit1) > 1 and cv.stringWidth(fit1, F, FS_DAT) > mw_a:
            fit1 = fit1[:-1]
        rest = addr_full[len(fit1):]
        if rest:
            _dots(cv, LX + 8, 632 + 4, RX)
            rw = cv.stringWidth(rest, F, FS_DAT)
            cv.setFillColor(white)
            cv.rect(LX + 8, Y(632) - 2, rw + 4, FS_DAT + 3, fill=1, stroke=0)
            cv.setFont(F, FS_DAT); cv.setFillColor(CF)
            cv.drawString(LX + 8, Y(632), rest)

    # ผู้ติดต่อ / โทร split (t=651) — fallback to old field names
    T_CT = 651
    CT_MID = LX + (RX - LX) * 0.52
    _loc_field(cv, LX + 8, T_CT, 'ผู้ติดต่อ :',
               _s(d.get('locationContact', d.get('contactPerson'))), end_x=CT_MID - 4)
    _loc_field(cv, CT_MID + 2, T_CT, 'โทร :',
               _s(d.get('locationPhone', d.get('contactPhone'))))

    # Separator before signature section
    _sep(cv, 672, color=C_BAND_BDR, lw=1.0)

    # ── Signature section ─────────────────────────────────────────────────
    SIG_MID = 305

    # ผู้รับเอกสาร: t=686
    T_SIG1 = 686
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    lbl_recv = 'ผู้รับเอกสาร :'
    cv.drawString(LX, Y(T_SIG1), lbl_recv)
    lw_recv = cv.stringWidth(lbl_recv, F, FS_LBL)
    _dots(cv, LX + lw_recv + 2, T_SIG1 + 5, SIG_MID - 5)
    lbl_recv2 = '/วันที่รับเอกสาร'
    cv.drawString(SIG_MID, Y(T_SIG1), lbl_recv2)
    lw_recv2 = cv.stringWidth(lbl_recv2, F, FS_LBL)
    _dots(cv, SIG_MID + lw_recv2 + 2, T_SIG1 + 5, RX)

    # ผู้สั่งงาน / วันที่สั่งงาน: t=714
    T_SIG2 = 714
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    lbl_ord = 'ผู้สั่งงาน / วันที่สั่งงาน :'
    cv.drawString(LX, Y(T_SIG2), lbl_ord)
    lw_ord = cv.stringWidth(lbl_ord, F, FS_LBL)
    nm_ord = _s(d.get('ordererName'))
    cv.setFont(FB, FS_DAT); cv.setFillColor(CF)
    cv.drawString(LX + lw_ord + 4, Y(T_SIG2), nm_ord)
    gap_ord = cv.stringWidth(nm_ord, FB, FS_DAT) if nm_ord else 0
    _dots(cv, LX + lw_ord + gap_ord + 6, T_SIG2 + 5, SIG_MID - 5)
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(SIG_MID, Y(T_SIG2), '/')
    _dots(cv, SIG_MID + 8, T_SIG2 + 5, RX)

    # ผู้สั่งงาน / วันที่ดำเนินงานเสร็จสิ้น: t=742
    T_SIG3 = 742
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    lbl_fin = 'ผู้สั่งงาน / วันที่ดำเนินงานเสร็จสิ้น :'
    cv.drawString(LX, Y(T_SIG3), lbl_fin)
    lw_fin = cv.stringWidth(lbl_fin, F, FS_LBL)
    _dots(cv, LX + lw_fin + 2, T_SIG3 + 5, SIG_MID - 5)
    cv.drawString(SIG_MID, Y(T_SIG3), '/')
    _dots(cv, SIG_MID + 8, T_SIG3 + 5, RX)

    # ผู้อนุมัติ: t=770
    T_SIG4 = 770
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    lbl_apv = 'ผู้อนุมัติ :'
    cv.drawString(LX, Y(T_SIG4), lbl_apv)
    lw_apv = cv.stringWidth(lbl_apv, F, FS_LBL)
    _dots(cv, LX + lw_apv + 2, T_SIG4 + 5, RX)

    # ── Footer ────────────────────────────────────────────────────────────
    cv.setFont(F, 7); cv.setFillColor(CL)
    cv.drawCentredString(
        PW / 2, 15,
        f"ใบสั่งงาน Messenger & Logistic — Contract Tracker Pro  |  Generated: {_tbe()}"
    )

    cv.save()
    buf.seek(0)
    return buf.getvalue()
