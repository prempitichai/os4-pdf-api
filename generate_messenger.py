#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_messenger.py — ใบสั่งงาน Messenger & Logistic (v12)
★ v13 — ลด font -2pt ทุกจุด (TH Sarabun New เดิมอยู่แล้ว)

เดิม: label=12 / data=10 / title=16 / dots=10 / footer=7
ใหม่: label=10 / data=8  / title=14 / dots=8  / footer=5
"""
import io, os, base64
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from messenger_images import SCM_LOGO_B64, SCM_WATERMARK_B64

for fp in ['/usr/share/fonts/truetype/freefont/', './fonts/', '/app/fonts/', './']:
    if os.path.exists(fp + 'THSarabunNew.ttf'):
        pdfmetrics.registerFont(TTFont('S', fp + 'THSarabunNew.ttf'))
        pdfmetrics.registerFont(TTFont('SB', fp + 'THSarabunNew-Bold.ttf'))
        break

PW, PH = A4; F = 'S'; FB = 'SB'
# ★ ลด -2pt: 12→10, 10→8, 16→14
FS_LBL = 10; FS_DAT = 8; FS_T = 14; FS_DOT = 8
ML = 50; MR = 50; LX = ML; RX = PW - MR
C = HexColor('#333333'); CF = HexColor('#1a237e')
CB = HexColor('#bbbbbb'); CL = HexColor('#cccccc')

def Y(t): return PH - t
def _s(v, d=''): s = str(v or '').strip(); return s if s else d
def _tbe():
    n = datetime.now(); return f"{n.day:02d}/{n.month:02d}/{n.year + 543}"

def _dots(cv, x1, yt, x2):
    if x1 >= x2 - 2: return
    cv.setFont(F, FS_DOT); cv.setFillColor(CB)
    dw = cv.stringWidth('.', F, FS_DOT); n = int((x2 - x1) / (dw * 0.8)); txt = '.' * n
    while cv.stringWidth(txt, F, FS_DOT) > (x2 - x1) and n > 0: n -= 1; txt = '.' * n
    cv.drawString(x1, Y(yt), txt)

def _fdots(cv, yt): _dots(cv, LX, yt, RX)

def _flines(cv, text, yt_list):
    mw = RX - LX - 2; lines = []
    if text:
        rem = str(text)
        while rem and len(lines) < len(yt_list):
            fit = rem
            while len(fit) > 1 and cv.stringWidth(fit, F, FS_DAT) > mw: fit = fit[:-1]
            lines.append(fit); rem = rem[len(fit):]
    for i, yt in enumerate(yt_list):
        _fdots(cv, yt)
        if i < len(lines):
            tw = cv.stringWidth(lines[i], F, FS_DAT)
            cv.setFillColor(white); cv.rect(LX - 1, Y(yt) - 2, tw + 4, FS_DAT + 3, fill=1, stroke=0)
            cv.setFont(F, FS_DAT); cv.setFillColor(CF); cv.drawString(LX, Y(yt) + 1, lines[i])

def _chk(cv, x, yt, checked, label):
    sz = 14; ry = Y(yt) - 2; cv.setLineWidth(1.0)
    if checked:
        cv.setStrokeColor(HexColor('#4a5eb8')); cv.setFillColor(HexColor('#4a5eb8'))
        cv.roundRect(x, ry, sz, sz, 3, fill=1, stroke=1)
        # ★ 10→8
        cv.setFont(FB, 8); cv.setFillColor(white); cv.drawCentredString(x + sz / 2, ry + 2.5, '✓')
    else:
        cv.setStrokeColor(HexColor('#aab0c0')); cv.setFillColor(white)
        cv.roundRect(x, ry, sz, sz, 3, fill=1, stroke=1)
    cv.setFont(F, FS_LBL); cv.setFillColor(C); cv.drawString(x + sz + 5, ry + 1, label)

def _vdots(cv, x, yt, val, end_x):
    cv.setFont(F, FS_DAT); cv.setFillColor(CF); cv.drawString(x, Y(yt), val)
    _dots(cv, x + cv.stringWidth(val, F, FS_DAT) + 3, yt + 5, end_x)


def generate_messenger_pdf(data):
    d = data or {}; buf = io.BytesIO(); cv = canvas.Canvas(buf, pagesize=A4)

    try:
        wm = ImageReader(io.BytesIO(base64.b64decode(SCM_WATERMARK_B64)))
        cv.drawImage(wm, 60, Y(380) - 220, width=460, height=220, preserveAspectRatio=True, mask='auto')
    except: pass
    try:
        logo = ImageReader(io.BytesIO(base64.b64decode(SCM_LOGO_B64)))
        cv.drawImage(logo, PW - MR - 90, Y(18) - 45, width=90, height=45, preserveAspectRatio=True, mask='auto')
    except: pass

    cv.setFont(FB, FS_T); cv.setFillColor(C)
    cv.drawCentredString(PW / 2, Y(58), 'ใบสั่งงาน Messenger & Logistic')

    ent = _s(d.get('entity'), '').lower().replace(' ', ''); slot = (RX - LX) / 4
    for i, nm in enumerate(['SCM Tech', 'SCM S', 'SCM C', 'Holding']): _chk(cv, LX + i * slot, 86, nm.lower().replace(' ', '') == ent, nm)
    for i, nm in enumerate(['Cyber', 'BC', 'B2B', 'Fahcloud']): _chk(cv, LX + i * slot, 114, nm.lower().replace(' ', '') == ent, nm)

    yt = 150; veh = d.get('vehicleType', 'car'); cnx = 310
    cv.setFont(F, FS_LBL); cv.setFillColor(C); cv.drawString(LX, Y(yt), '(')
    if veh == 'car': cv.setFont(FB, FS_LBL); cv.setFillColor(CF); cv.drawCentredString(LX + 20, Y(yt), '✓')
    cv.setFont(F, FS_LBL); cv.setFillColor(C); cv.drawString(LX + 36, Y(yt), ') รถยนต์')
    cv.drawString(LX + 115, Y(yt), '(')
    if veh == 'motorcycle': cv.setFont(FB, FS_LBL); cv.setFillColor(CF); cv.drawCentredString(LX + 135, Y(yt), '✓')
    cv.setFont(F, FS_LBL); cv.setFillColor(C); cv.drawString(LX + 151, Y(yt), ') รถมอเตอร์ไซด์')
    cv.drawString(cnx, Y(yt), 'Contract Number:'); lw = cv.stringWidth('Contract Number:', F, FS_LBL)
    _vdots(cv, cnx + lw + 4, yt, _s(d.get('contractNumber')), RX)

    yt = 178; urg = d.get('isUrgent') in [True, 'TRUE', 'true', '1']
    cv.setFont(F, FS_LBL); cv.setFillColor(C); cv.drawString(LX, Y(yt), '(')
    if urg: cv.setFont(FB, FS_LBL); cv.setFillColor(CF); cv.drawCentredString(LX + 20, Y(yt), '✓')
    cv.setFont(F, FS_LBL); cv.setFillColor(C); cv.drawString(LX + 36, Y(yt), ') ด่วน')
    cv.drawString(LX + 115, Y(yt), '(')
    if not urg: cv.setFont(FB, FS_LBL); cv.setFillColor(CF); cv.drawCentredString(LX + 135, Y(yt), '✓')
    cv.setFont(F, FS_LBL); cv.setFillColor(C); cv.drawString(LX + 151, Y(yt), ') ไม่ด่วน')
    cv.drawString(cnx, Y(yt), 'วันที่สั่งงาน :'); lw = cv.stringWidth('วันที่สั่งงาน :', F, FS_LBL)
    _vdots(cv, cnx + lw + 4, yt, _s(d.get('orderDate', _tbe())), RX)

    yt = 204; cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(cnx, Y(yt), 'วันที่ดำเนินงาน :'); lw = cv.stringWidth('วันที่ดำเนินงาน :', F, FS_LBL)
    _vdots(cv, cnx + lw + 4, yt, _s(d.get('operationDate')), RX)

    yt = 240; cv.setFont(FB, FS_LBL); cv.setFillColor(C)
    lbl = 'ชื่อเจ้าหน้าที่ (Messenger / Logistic):'; cv.drawString(LX, Y(yt), lbl)
    lw = cv.stringWidth(lbl, FB, FS_LBL)
    cv.setFont(F, FS_DAT); cv.setFillColor(CF); cv.drawString(LX + lw + 4, Y(yt), _s(d.get('messengerName', 'พี่วุฒ')))
    _fdots(cv, yt + 5)

    cv.setFont(FB, FS_LBL); cv.setFillColor(C); cv.drawString(LX, Y(275), 'รายละเอียดของงานที่ให้ไปรับ-ส่ง:')
    _flines(cv, _s(d.get('jobDetail')), [299, 323, 347, 371, 395])

    cv.setFont(FB, FS_LBL); cv.setFillColor(C); cv.drawString(LX, Y(430), 'สิ่งที่นำกลับ :')
    _flines(cv, _s(d.get('returnItems')), [454, 478, 502])

    cv.setFont(FB, FS_LBL); cv.setFillColor(C); cv.drawString(LX, Y(537), 'สถานที่ ส่งงาน-รับงาน:')
    _flines(cv, _s(d.get('location')), [561, 585, 609])

    mid = 305
    yt = 648; cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(yt), 'ผู้รับเอกสาร :'); lw = cv.stringWidth('ผู้รับเอกสาร :', F, FS_LBL)
    _dots(cv, LX + lw + 2, yt + 5, mid - 5)
    cv.drawString(mid, Y(yt), '/วันที่รับเอกสาร'); lw2 = cv.stringWidth('/วันที่รับเอกสาร', F, FS_LBL)
    _dots(cv, mid + lw2 + 2, yt + 5, RX)

    yt = 676; cv.setFont(F, FS_LBL); cv.setFillColor(C)
    lbl = 'ผู้สั่งงาน / วันที่สั่งงาน :'; cv.drawString(LX, Y(yt), lbl); lw = cv.stringWidth(lbl, F, FS_LBL)
    cv.setFont(FB, FS_DAT); cv.setFillColor(CF); nm = _s(d.get('ordererName'))
    cv.drawString(LX + lw + 4, Y(yt), nm)
    _dots(cv, LX + lw + cv.stringWidth(nm, FB, FS_DAT) + 6, yt + 5, mid - 5)
    cv.setFont(F, FS_LBL); cv.setFillColor(C); cv.drawString(mid, Y(yt), '/')
    cv.setFont(F, FS_DAT); cv.setFillColor(CF); dt = _s(d.get('ordererDate'))
    cv.drawString(mid + 8, Y(yt), dt); _dots(cv, mid + 8 + cv.stringWidth(dt, F, FS_DAT) + 2, yt + 5, RX)

    yt = 704; cv.setFont(F, FS_LBL); cv.setFillColor(C)
    lbl = 'ผู้สั่งงาน / วันที่ดำเนินงานเสร็จสิ้น :'; cv.drawString(LX, Y(yt), lbl)
    lw = cv.stringWidth(lbl, F, FS_LBL); _dots(cv, LX + lw + 2, yt + 5, mid - 5)
    cv.drawString(mid, Y(yt), '/'); _dots(cv, mid + 8, yt + 5, RX)

    yt = 732; cv.setFont(F, FS_LBL); cv.setFillColor(C)
    cv.drawString(LX, Y(yt), 'ผู้อนุมัติ :'); lw = cv.stringWidth('ผู้อนุมัติ :', F, FS_LBL)
    _dots(cv, LX + lw + 2, yt + 5, RX)

    # ★ footer 7→5
    cv.setFont(F, 5); cv.setFillColor(CL)
    cv.drawCentredString(PW / 2, 15, f"ใบสั่งงาน Messenger & Logistic — Contract Tracker Pro  |  Generated: {_tbe()}")

    cv.save(); buf.seek(0); return buf.getvalue()
