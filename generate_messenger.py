#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_messenger.py — ใบสั่งงาน Messenger & Logistic
★ v14 — แก้ไข:
  1. Font registration: เพิ่ม raise เมื่อหาฟอนต์ไม่พบ (แทน silent fail)
  2. Font size +2pt ทุกจุด (กลับค่าจาก v13 ที่ลดไป -2pt)
★ v15 — รองรับ Thai + English key

Font sizes (v14 vs v13):
  label: 10→12  |  data: 8→10  |  title: 14→16
  dots:   8→10  |  footer: 5→7  |  checkbox: 8→10
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
# ★ แก้ไข: เพิ่ม raise FileNotFoundError เมื่อหาฟอนต์ไม่พบ (แทน silent fail)
_FONT_SEARCH_DIRS = [
    '/usr/share/fonts/truetype/freefont/',
    './fonts/',
    '/app/fonts/',
    './',
]
_FONT_REG = False

def _register_fonts():
    """
    ลงทะเบียน TH Sarabun New ครั้งเดียว
    ★ แก้ไข: raise FileNotFoundError ถ้าหาไม่พบ แทนการ fail เงียบๆ
    """
    global _FONT_REG
    if _FONT_REG:
        return

    # ตรวจสอบว่า register แล้วหรือยัง (กรณีที่ app.py register ก่อน)
    try:
        pdfmetrics.getFont('S')
        pdfmetrics.getFont('SB')
        _FONT_REG = True
        logger.debug("ฟอนต์ S/SB ถูก register แล้ว — ข้าม")
        return
    except KeyError:
        pass

    # ค้นหาและ register
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
                    # Bold ไม่พบ — ใช้ regular แทน
                    pdfmetrics.registerFont(TTFont('SB', reg_path))
                    logger.warning(f"ไม่พบ THSarabunNew-Bold.ttf — ใช้ regular แทน")
                logger.info(f"ลงทะเบียนฟอนต์ Messenger จาก: {fp}")
                found = True
                break
            except Exception as e:
                logger.warning(f"Register font ล้มเหลวจาก {fp}: {e}")
                continue

    if not found:
        # ★ แก้ไข: raise แทน silent fail
        raise FileNotFoundError(
            f"ไม่พบ THSarabunNew.ttf ใน: {_FONT_SEARCH_DIRS}\n"
            f"กรุณาวาง font files ไว้ใน ./fonts/ หรือ /app/fonts/"
        )
    _FONT_REG = True


# ── DEFAULT COMPANY INFO (SCM Technologies — fallback ถ้า GAS ไม่ส่งมา) ─────────
_SCM_DEFAULT = {
    'companyName':   'บจก. เอส ซีเอ็ม เอส เทคโนโลจีส์',
    'companyNameEn': 'SCM Technologies Co., Ltd.',
    'address':       '92/41 อาคารสาธรธานี 2 ชั้นที่ 15 ถนนสาทรเหนือ แขวงสีลม เขตบางรัก กรุงเทพมหานคร 10500',
    'phone':         '02-116-4312, 02-116-4213',
    'fax':           '02-235-3699',
    'taxId':         '0105563004553',
}

# ── CONSTANTS ────────────────────────────────────────────────────────────────
PW, PH = A4
F  = 'S'   # THSarabunNew regular
FB = 'SB'  # THSarabunNew bold

# ★ font sizes +2pt จาก v13
FS_LBL = 12  # label (เดิม 10)
FS_DAT = 10  # data  (เดิม 8)
FS_T   = 16  # title (เดิม 14)
FS_DOT = 10  # dots  (เดิม 8)

ML = 50; MR = 50; LX = ML; RX = PW - MR
C  = HexColor('#333333'); CF = HexColor('#1a237e')
CB = HexColor('#bbbbbb'); CL = HexColor('#cccccc')


# ── HELPERS ──────────────────────────────────────────────────────────────────

def Y(t):
    """แปลง y จากบนลงล่าง → ล่างขึ้นบน (reportlab coordinate)"""
    return PH - t

def _s(v, d=''):
    """Safe string — คืน default ถ้าว่าง"""
    s = str(v or '').strip()
    return s if s else d

def _tbe():
    """วันที่ปัจจุบันในรูปแบบ พ.ศ."""
    n = datetime.now()
    return f"{n.day:02d}/{n.month:02d}/{n.year + 543}"


def _dots(cv, x1, yt, x2):
    """
    วาดจุด dotted line จาก x1 ถึง x2
    ใช้ FS_DOT เป็น font size
    """
    if x1 >= x2 - 2:
        return
    cv.setFont(F, FS_DOT)
    cv.setFillColor(CB)
    dw  = cv.stringWidth('.', F, FS_DOT)
    n   = int((x2 - x1) / (dw * 0.8))
    txt = '.' * n
    while cv.stringWidth(txt, F, FS_DOT) > (x2 - x1) and n > 0:
        n -= 1; txt = '.' * n
    cv.drawString(x1, Y(yt), txt)


def _fdots(cv, yt):
    """วาด full-width dotted line"""
    _dots(cv, LX, yt, RX)


def _flines(cv, text, yt_list):
    """
    แสดงข้อความหลายบรรทัด พร้อม dotted underline
    ข้อความจะ wrap ตาม yt_list ที่ให้มา
    """
    mw    = RX - LX - 2
    lines = []
    if text:
        rem = str(text)
        while rem and len(lines) < len(yt_list):
            fit = rem
            while len(fit) > 1 and cv.stringWidth(fit, F, FS_DAT) > mw:
                fit = fit[:-1]
            lines.append(fit)
            rem = rem[len(fit):]

    for i, yt in enumerate(yt_list):
        _fdots(cv, yt)
        if i < len(lines):
            tw = cv.stringWidth(lines[i], F, FS_DAT)
            # วาด white background ก่อนเพื่อลบ dot ออก
            cv.setFillColor(white)
            cv.rect(LX - 1, Y(yt) - 2, tw + 4, FS_DAT + 3, fill=1, stroke=0)
            cv.setFont(F, FS_DAT)
            cv.setFillColor(CF)
            cv.drawString(LX, Y(yt) + 1, lines[i])


def _chk(cv, x, yt, checked, label):
    """
    วาด checkbox พร้อม label
    ★ font size +2pt: checkbox ✓ เดิม 8→10
    """
    sz = 14; ry = Y(yt) - 2
    cv.setLineWidth(1.0)
    if checked:
        cv.setStrokeColor(HexColor('#4a5eb8'))
        cv.setFillColor(HexColor('#4a5eb8'))
        cv.roundRect(x, ry, sz, sz, 3, fill=1, stroke=1)
        cv.setFont(FB, 10)         # ★ 8→10
        cv.setFillColor(white)
        cv.drawCentredString(x + sz / 2, ry + 2.5, '✓')
    else:
        cv.setStrokeColor(HexColor('#aab0c0'))
        cv.setFillColor(white)
        cv.roundRect(x, ry, sz, sz, 3, fill=1, stroke=1)
    cv.setFont(F, FS_LBL)
    cv.setFillColor(C)
    cv.drawString(x + sz + 5, ry + 1, label)


def _vdots(cv, x, yt, val, end_x):
    """วาดค่า + dotted line ต่อท้าย"""
    cv.setFont(F, FS_DAT)
    cv.setFillColor(CF)
    cv.drawString(x, Y(yt), val)
    _dots(cv, x + cv.stringWidth(val, F, FS_DAT) + 3, yt + 5, end_x)


# ════════════════════════════════════════════════════════════
# MAIN: generate_messenger_pdf
# ════════════════════════════════════════════════════════════

def generate_messenger_pdf(data):
    """
    สร้าง PDF ใบสั่งงาน Messenger & Logistic
    รองรับ entity selector (SCM Tech, SCM S, SCM C, Holding, Cyber, BC, B2B, Fahcloud)
    """
    _register_fonts()

    d   = data or {}
    buf = io.BytesIO()
    cv  = canvas.Canvas(buf, pagesize=A4)

    # ── Watermark ──
    try:
        wm = ImageReader(io.BytesIO(base64.b64decode(SCM_WATERMARK_B64)))
        cv.drawImage(wm, 60, Y(380) - 220, width=460, height=220,
                     preserveAspectRatio=True, mask='auto')
    except Exception as e:
        logger.debug(f"Watermark load ล้มเหลว: {e}")

    # ── Logo ──
    try:
        logo = ImageReader(io.BytesIO(base64.b64decode(SCM_LOGO_B64)))
        cv.drawImage(logo, PW - MR - 90, Y(18) - 45, width=90, height=45,
                     preserveAspectRatio=True, mask='auto')
    except Exception as e:
        logger.debug(f"Logo load ล้มเหลว: {e}")

    # ── Title ──
    cv.setFont(FB, FS_T)   # ★ 14→16
    cv.setFillColor(C)
    cv.drawCentredString(PW / 2, Y(58), 'ใบสั่งงาน Messenger & Logistic')

    # ── Entity checkboxes (2 แถว) ──
    ent  = _s(d.get('entity'), '').lower().replace(' ', '')
    slot = (RX - LX) / 4
    entities_row1 = ['SCM Tech', 'SCM S', 'SCM C', 'Holding']
    entities_row2 = ['Cyber',    'BC',    'B2B',   'Fahcloud']

    for i, nm in enumerate(entities_row1):
        _chk(cv, LX + i * slot, 86, nm.lower().replace(' ', '') == ent, nm)
    for i, nm in enumerate(entities_row2):
        _chk(cv, LX + i * slot, 114, nm.lower().replace(' ', '') == ent, nm)

    # ── ประเภทพาหนะ ──
    yt  = 150
    veh = d.get('vehicleType', 'car')
    # [FIX-VEHICLE v15] รองรับทั้ง English key ('car','motorcycle')
    # และ Thai label ('รถยนต์','รถมอเตอร์ไซด์') จาก WebApp.gs
    _veh    = str(veh or 'car').lower().strip()
    is_car  = _veh in ['car', 'รถยนต์']
    is_moto = _veh in ['motorcycle', 'motorbike', 'รถมอเตอร์ไซด์', 'รถมอเตอร์']
    if not is_car and not is_moto:
        is_car = True   # default = รถยนต์
    cnx = 310   # x เริ่มต้นของ "Contract Number"
 
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(yt), '(')
    if is_car:
        cv.setFont(FB, FS_LBL); cv.setFillColor(CF)
        cv.drawCentredString(LX + 20, Y(yt), '✓')
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX + 36, Y(yt), ') รถยนต์')
    cv.drawString(LX + 115, Y(yt), '(')
    if is_moto:
        cv.setFont(FB, FS_LBL); cv.setFillColor(CF)
        cv.drawCentredString(LX + 135, Y(yt), '✓')
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX + 151, Y(yt), ') รถมอเตอร์ไซด์')
 
    cv.drawString(cnx, Y(yt), 'Contract Number:')
    lw = cv.stringWidth('Contract Number:', F, FS_LBL)
    _vdots(cv, cnx + lw + 4, yt, _s(d.get('contractNumber')), RX)

    # ── ระดับความเร่งด่วน ──
    yt  = 178
    urg = d.get('isUrgent') in [True, 'TRUE', 'true', '1']

    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(yt), '(')
    if urg:
        cv.setFont(FB, FS_LBL); cv.setFillColor(CF)
        cv.drawCentredString(LX + 20, Y(yt), '✓')
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX + 36, Y(yt), ') ด่วน')
    cv.drawString(LX + 115, Y(yt), '(')
    if not urg:
        cv.setFont(FB, FS_LBL); cv.setFillColor(CF)
        cv.drawCentredString(LX + 135, Y(yt), '✓')
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX + 151, Y(yt), ') ไม่ด่วน')

    cv.drawString(cnx, Y(yt), 'วันที่สั่งงาน :')
    lw = cv.stringWidth('วันที่สั่งงาน :', F, FS_LBL)
    _vdots(cv, cnx + lw + 4, yt, _s(d.get('orderDate', _tbe())), RX)

    # ── วันที่ดำเนินงาน ──
    yt = 204
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(cnx, Y(yt), 'วันที่ดำเนินงาน :')
    lw = cv.stringWidth('วันที่ดำเนินงาน :', F, FS_LBL)
    _vdots(cv, cnx + lw + 4, yt, _s(d.get('operationDate')), RX)

    # ── ชื่อเจ้าหน้าที่ Messenger ──
    yt = 240
    cv.setFont(FB, FS_LBL); cv.setFillColor(C)
    lbl = 'ชื่อเจ้าหน้าที่ (Messenger / Logistic):'
    cv.drawString(LX, Y(yt), lbl)
    lw = cv.stringWidth(lbl, FB, FS_LBL)
    cv.setFont(F, FS_DAT); cv.setFillColor(CF)
    cv.drawString(LX + lw + 4, Y(yt), _s(d.get('messengerName', 'พี่วุฒ')))
    _fdots(cv, yt + 5)

    # ── รายละเอียดงาน ──
    cv.setFont(FB, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(275), 'รายละเอียดของงานที่ให้ไปรับ-ส่ง:')
    _flines(cv, _s(d.get('jobDetail')), [299, 323, 347, 371, 395])

    # ── สิ่งที่นำกลับ ──
    cv.setFont(FB, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(430), 'สิ่งที่นำกลับ :')
    _flines(cv, _s(d.get('returnItems')), [454, 478, 502])

    # ── สถานที่ ──
    cv.setFont(FB, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(537), 'สถานที่ ส่งงาน-รับงาน:')
    _flines(cv, _s(d.get('location')), [561, 585, 609])

    # ── Signature section ──
    mid = 305

    # ผู้รับเอกสาร
    yt = 648
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(yt), 'ผู้รับเอกสาร :')
    lw = cv.stringWidth('ผู้รับเอกสาร :', F, FS_LBL)
    _dots(cv, LX + lw + 2, yt + 5, mid - 5)
    cv.drawString(mid, Y(yt), '/วันที่รับเอกสาร')
    lw2 = cv.stringWidth('/วันที่รับเอกสาร', F, FS_LBL)
    _dots(cv, mid + lw2 + 2, yt + 5, RX)

    # ผู้สั่งงาน
    yt = 676
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    lbl = 'ผู้สั่งงาน / วันที่สั่งงาน :'
    cv.drawString(LX, Y(yt), lbl)
    lw = cv.stringWidth(lbl, F, FS_LBL)

    cv.setFont(FB, FS_DAT); cv.setFillColor(CF)
    nm = _s(d.get('ordererName'))
    cv.drawString(LX + lw + 4, Y(yt), nm)
    _dots(cv, LX + lw + cv.stringWidth(nm, FB, FS_DAT) + 6, yt + 5, mid - 5)

    cv.setFont(F, FS_LBL); cv.setFillColor(C); cv.drawString(mid, Y(yt), '/')
    cv.setFont(F, FS_DAT); cv.setFillColor(CF)
    dt = _s(d.get('ordererDate'))
    cv.drawString(mid + 8, Y(yt), dt)
    _dots(cv, mid + 8 + cv.stringWidth(dt, F, FS_DAT) + 2, yt + 5, RX)

    # ผู้สั่งงาน / วันที่ดำเนินงานเสร็จสิ้น
    yt = 704
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    lbl = 'ผู้สั่งงาน / วันที่ดำเนินงานเสร็จสิ้น :'
    cv.drawString(LX, Y(yt), lbl)
    lw = cv.stringWidth(lbl, F, FS_LBL)
    _dots(cv, LX + lw + 2, yt + 5, mid - 5)
    cv.drawString(mid, Y(yt), '/')
    _dots(cv, mid + 8, yt + 5, RX)

    # ผู้อนุมัติ
    yt = 732
    cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(yt), 'ผู้อนุมัติ :')
    lw = cv.stringWidth('ผู้อนุมัติ :', F, FS_LBL)
    _dots(cv, LX + lw + 2, yt + 5, RX)

    # ── Footer ──
    cv.setFont(F, 7); cv.setFillColor(CL)   # ★ 5→7
    cv.drawCentredString(
        PW / 2, 15,
        f"ใบสั่งงาน Messenger & Logistic — Contract Tracker Pro  |  Generated: {_tbe()}"
    )

    cv.save(); buf.seek(0)
    return buf.getvalue()
