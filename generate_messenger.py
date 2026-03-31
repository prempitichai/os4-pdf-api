#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_messenger.py — ใบสั่งงาน Messenger & Logistic
★ v16 — แก้ layout ให้ตรงตาม PDF ต้นแบบที่อนุมัติแล้ว
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


# ── HELPERS ──────────────────────────────────────────────────────────────────

def Y(t):
    """แปลง t (จากบนลงล่าง) → y coordinate ของ ReportLab (จากล่างขึ้นบน)"""
    return PH - t


def _s(v, d=''):
    s = str(v or '').strip()
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
    """
    วาด dot lines และ fill ข้อความ (wrap อัตโนมัติ)
    [FIX v17] first_line_x: ถ้าระบุ → บรรทัดแรกเริ่ม text จาก x นั้น (inline กับ label)
              บรรทัดถัดไปเริ่มจาก LX ตามปกติ
    yt_list: รายการ t-values ของแต่ละบรรทัด
    """
    # บรรทัดแรก: ถ้า first_line_x ระบุ → วาด dots จาก LX ถึง RX ก่อน (เต็มบรรทัด)
    # แล้ว clear area ตั้งแต่ first_line_x ไปทางซ้าย (label area) ด้วย white-box
    # จากนั้น fill text ที่ first_line_x

    lines = []
    if text:
        # คำนวณ wrap สำหรับบรรทัดแรก (width แคบกว่า เพราะ label กินที่)
        mw_first = RX - (first_line_x or LX) - 2
        mw_rest  = RX - LX - 2
        rem = str(text)

        # บรรทัดแรก
        if first_line_x and rem:
            fit = rem
            while len(fit) > 1 and cv.stringWidth(fit, F, FS_DAT) > mw_first:
                fit = fit[:-1]
            lines.append(fit)
            rem = rem[len(fit):]

        # บรรทัดที่เหลือ
        while rem and len(lines) < len(yt_list):
            fit = rem
            while len(fit) > 1 and cv.stringWidth(fit, F, FS_DAT) > mw_rest:
                fit = fit[:-1]
            lines.append(fit)
            rem = rem[len(fit):]

    for i, yt in enumerate(yt_list):
        # กำหนด x เริ่มต้น content ในบรรทัดนี้
        cx = (first_line_x or LX) if i == 0 else LX
        _fdots(cv, yt)   # วาด dots เต็มบรรทัดก่อนเสมอ

        if i < len(lines) and lines[i]:
            tw = cv.stringWidth(lines[i], F, FS_DAT)
            # white-box ลบ dots บริเวณที่จะวาง text
            cv.setFillColor(white)
            cv.rect(cx - 1, Y(yt) - 2, tw + 4, FS_DAT + 3, fill=1, stroke=0)
            cv.setFont(F, FS_DAT)
            cv.setFillColor(CF)
            cv.drawString(cx, Y(yt) + 1, lines[i])


def _draw_checkmark(cv, x, ry, sz, color):
    """
    วาด ✓ ด้วย drawLines (รองรับฟอนต์ที่ไม่มี glyph U+2713)
    x, ry: bottom-left ของ checkbox rect
    sz: ขนาด checkbox
    """
    cv.setStrokeColor(color)
    cv.setLineWidth(1.8)
    p1x = x + sz * 0.15;  p1y = ry + sz * 0.48
    p2x = x + sz * 0.38;  p2y = ry + sz * 0.22
    p3x = x + sz * 0.85;  p3y = ry + sz * 0.72
    cv.line(p1x, p1y, p2x, p2y)
    cv.line(p2x, p2y, p3x, p3y)
    cv.setLineWidth(1.0)


def _chk(cv, x, yt, checked, label):
    """
    วาด checkbox + label
    x: left edge ของ checkbox
    yt: t value (ใช้กับ Y(yt) สำหรับ bottom ของ text)
    """
    sz = 14
    ry = Y(yt) - 2   # bottom-left ของ rect

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


def _vdots(cv, x, yt, val, end_x):
    """
    [FIX v17] วาด dots เต็มบรรทัดจาก x → end_x ก่อน
    แล้ว white-box ทับใต้ value เพื่อให้ value ไม่ทับ dots
    ค่า val จะ float กึ่งกลางระหว่าง x ถึง end_x
    """
    # วาด dots เต็มก่อน
    _dots(cv, x, yt + 5, end_x)
    if not val:
        return
    # คำนวณตำแหน่งกึ่งกลาง
    vw   = cv.stringWidth(val, F, FS_DAT)
    zone = end_x - x
    vx   = x + (zone - vw) / 2  # center ใน zone
    # white-box ลบ dots ใต้ value
    cv.setFillColor(white)
    cv.rect(vx - 2, Y(yt) - 2, vw + 4, FS_DAT + 4, fill=1, stroke=0)
    # วาด value
    cv.setFont(F, FS_DAT)
    cv.setFillColor(CF)
    cv.drawString(vx, Y(yt), val)




def _flines_inline(cv, text, label_t, label_lw, extra_yt_list):
    """
    [FIX v17] เหมือน _flines แต่บรรทัดแรก fill ต่อจาก label ในแถวเดียวกัน
    label_t    : t value ของแถว label
    label_lw   : ความกว้าง label (pixels)
    extra_yt_list: t values ของบรรทัดถัดไป (ไม่รวม label line)
    """
    mw_first = RX - (LX + label_lw + 8) - 2   # พื้นที่ด้านขวาของ label
    mw_rest  = RX - LX - 2
    lines    = []

    if text:
        rem = str(text)
        # บรรทัดแรก: ใช้พื้นที่หลัง label
        if rem:
            fit = rem
            while len(fit) > 1 and cv.stringWidth(fit, F, FS_DAT) > mw_first:
                fit = fit[:-1]
            lines.append(('first', fit))
            rem = rem[len(fit):]
        # บรรทัดถัดไป: เต็มแถว
        while rem and len(lines) - 1 < len(extra_yt_list):
            fit = rem
            while len(fit) > 1 and cv.stringWidth(fit, F, FS_DAT) > mw_rest:
                fit = fit[:-1]
            lines.append(('rest', fit))
            rem = rem[len(fit):]

    # วาดบรรทัดแรก (ต่อจาก label)
    dot_x1_first = LX + label_lw + 8
    _dots(cv, dot_x1_first, label_t + 5, RX)
    if lines and lines[0][0] == 'first' and lines[0][1]:
        val0 = lines[0][1]
        vw0  = cv.stringWidth(val0, F, FS_DAT)
        cv.setFillColor(white)
        cv.rect(dot_x1_first, Y(label_t) - 3, vw0 + 4, FS_DAT + 4, fill=1, stroke=0)
        cv.setFont(F, FS_DAT); cv.setFillColor(CF)
        cv.drawString(dot_x1_first + 2, Y(label_t), val0)

    # วาดบรรทัดถัดไป
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


def _rcol_field(cv, lx, yt, label, val, end_x):
    """
    [FIX v17] วาด field แบบ right-column:
      label ซ้าย → dots เต็มแถว → val วางกึ่งกลาง dots area (ไม่ทับ label)
    """
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(lx, Y(yt), label)
    lw = cv.stringWidth(label, F, FS_LBL)
    dot_x1 = lx + lw + 4
    dot_x2 = end_x
    # วาด dots เต็มพื้นที่ก่อน
    _dots(cv, dot_x1, yt + 5, dot_x2)
    if val:
        # คำนวณตำแหน่งกึ่งกลาง dots area
        vw = cv.stringWidth(val, F, FS_DAT)
        mid_x = dot_x1 + (dot_x2 - dot_x1 - vw) / 2
        # white rect ทับ dots ใต้ค่า (เพื่อไม่ให้ dots โชว์ทับ)
        cv.setFillColor(white)
        cv.rect(mid_x - 2, Y(yt) - 3, vw + 4, FS_DAT + 4, fill=1, stroke=0)
        # วาดค่า
        cv.setFont(F, FS_DAT); cv.setFillColor(CF)
        cv.drawString(mid_x, Y(yt), val)



# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

def generate_messenger_pdf(data):
    """
    สร้าง PDF ใบสั่งงาน Messenger & Logistic
    Layout พิกัดวัดจาก PDF ต้นแบบ (v16)
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
    # ตาม PDF ต้นแบบ: logo อยู่บนขวา ห่างจากขอบ right ~50, top ~18
    try:
        logo = ImageReader(io.BytesIO(base64.b64decode(SCM_LOGO_B64)))
        cv.drawImage(logo, RX - 90, Y(18) - 45, width=90, height=45,
                     preserveAspectRatio=True, mask='auto')
    except Exception as e:
        logger.debug(f"Logo load ล้มเหลว: {e}")

    # ── Title: t=63 ───────────────────────────────────────────────────────
    cv.setFont(FB, FS_T)
    cv.setFillColor(C)
    cv.drawCentredString(PW / 2, Y(63), 'ใบสั่งงาน Messenger & Logistic')

    # ── Entity checkboxes ─────────────────────────────────────────────────
    # พิกัดวัดจาก PDF: row1 y_pdf=716.9 → t=125, row2 y_pdf=688.9 → t=153
    # label x: [69, 193, 317, 441]  checkbox x: label_x - 20
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

    # x positions ของ label แต่ละ column (วัดจาก PDF)
    _LABEL_X = [69.0, 192.8, 316.6, 440.5]
    _ENT_ROW1 = [('SCM Tech', 'scmtech'), ('SCM S', 'scms'),
                 ('SCM C',    'scmc'),    ('Holding', 'holding')]
    _ENT_ROW2 = [('Cyber', 'cyber'), ('BC', 'bc'),
                 ('B2B',   'b2b'),   ('Fahcloud', 'fahcloud')]

    for i, (label, key) in enumerate(_ENT_ROW1):
        _chk(cv, _LABEL_X[i] - 20, 125, key == ent, label)

    for i, (label, key) in enumerate(_ENT_ROW2):
        _chk(cv, _LABEL_X[i] - 20, 153, key == ent, label)

    # ── Vehicle type: t=188 ───────────────────────────────────────────────
    # พิกัดจาก PDF: ( x=50, checkbox ~58, ) x=86, label x=93
    #               ( x=165, checkbox ~173, ) x=201, label x=208
    # Contract Number: x=310
    veh = d.get('vehicleType', 'car')
    _veh    = str(veh or 'car').lower().strip()
    is_car  = _veh in ['car', 'รถยนต์']
    is_moto = _veh in ['motorcycle', 'motorbike', 'รถมอเตอร์ไซด์', 'รถมอเตอร์']
    if not is_car and not is_moto:
        is_car = True

    # บังคับ: รับ boolean flags จาก WebApp.gs ด้วย (v15 compat)
    if d.get('vehicle_car') is True:        is_car, is_moto = True, False
    if d.get('vehicle_motorcycle') is True: is_car, is_moto = False, True

    T_VEH = 188   # t value สำหรับแถว vehicle

    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    # col 1: รถยนต์
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

    # col 2: รถมอเตอร์ไซด์
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

    # Contract Number (right column): x=310
    # [FIX v17] label+dots เต็มแถว, ค่ากึ่งกลาง dots area
    _rcol_field(cv, 310, T_VEH, 'Contract Number:', _s(d.get('contractNumber')), RX)

    # ── Urgency: t=216 ───────────────────────────────────────────────────
    # พิกัดเหมือน vehicle row (x=50,165) แต่ t=216
    # วันที่สั่งงาน: x=312.5 → 310
    urg = d.get('isUrgent') in [True, 'TRUE', 'true', '1']
    # compat: WebApp.gs อาจส่ง urgent_true/urgent_false
    if d.get('urgent_true') is True:  urg = True
    if d.get('urgent_false') is True: urg = False

    T_URG = 216

    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    # col 1: ด่วน
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

    # col 2: ไม่ด่วน
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

    # วันที่สั่งงาน (right column): x=310
    # [FIX v17] label+dots เต็มแถว, ค่ากึ่งกลาง
    _rcol_field(cv, 310, T_URG, 'วันที่สั่งงาน :', _s(d.get('orderDate', _tbe())), RX)

    # ── วันที่ดำเนินงาน: t=242 ───────────────────────────────────────────
    # อยู่แค่ column ขวา x=310
    T_OPD = 242
    # [FIX v17] label+dots เต็มแถว, ค่ากึ่งกลาง
    _rcol_field(cv, 310, T_OPD, 'วันที่ดำเนินงาน :', _s(d.get('operationDate')), RX)

    # ── ชื่อเจ้าหน้าที่: t=278 ───────────────────────────────────────────
    T_MSG = 278
    lbl_msg = 'ชื่อเจ้าหน้าที่ (Messenger / Logistic):'
    cv.setFont(FB, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(T_MSG), lbl_msg)
    lw_msg = cv.stringWidth(lbl_msg, FB, FS_LBL)
    # [FIX v17] dots เต็มแถวก่อน จากนั้นวาง nm_val กึ่งกลาง dot area
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

    # ── รายละเอียดของงาน: label t=313, lines t=[344,375,406,437,468] ────
    # [FIX v17] fill ข้อมูลต่อในบรรทัด label ได้เลย
    cv.setFont(FB, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(313), 'รายละเอียดของงานที่ให้ไปรับ-ส่ง:')
    _lbl_lw = cv.stringWidth('รายละเอียดของงานที่ให้ไปรับ-ส่ง:', FB, FS_LBL)
    _flines_inline(cv, _s(d.get('jobDetail')), 313, _lbl_lw, [344, 375, 406, 437, 468])

    # ── สิ่งที่นำกลับ: label t=468, lines t=[504,539,575] ───────────────
    # [FIX v17] fill ข้อมูลต่อในบรรทัด label ได้เลย
    cv.setFont(FB, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(468), 'สิ่งที่นำกลับ :')
    _lbl_ret_lw = cv.stringWidth('สิ่งที่นำกลับ :', FB, FS_LBL)
    _flines_inline(cv, _s(d.get('returnItems')), 468, _lbl_ret_lw, [504, 539, 575])

    # ── สถานที่: label t=575, lines t=[603,631,658] ──────────────────────
    # [FIX v17] fill ข้อมูลต่อในบรรทัด label ได้เลย
    cv.setFont(FB, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(575), 'สถานที่ ส่งงาน-รับงาน:')
    _lbl_loc_lw = cv.stringWidth('สถานที่ ส่งงาน-รับงาน:', FB, FS_LBL)
    _flines_inline(cv, _s(d.get('location')), 575, _lbl_loc_lw, [603, 631, 658])

    # ── Signature section ─────────────────────────────────────────────────
    # พิกัดจาก PDF: mid=305
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
    # fill ordererName
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
