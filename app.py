#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OS4 PDF API Server — deploy บน Render / Railway
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
★ v6 — แก้ไข:
  1. Font registration guard (ป้องกัน register ซ้ำ)
  2. Input validation ทุก endpoint (items type check)
  3. API Key ใช้ hmac.compare_digest (ป้องกัน timing attack)
  4. Error message แยก debug/production
  5. Template path validate ตอน startup
  6. Font size +2pt ทุกจุด (กลับไปขนาดเดิมก่อน v3)
  7. [NEW v6] _fmt_val แยก บาท | สต. (ไม่แสดงทศนิยมรวม)
  8. [NEW v6] _fmt_cent() ฟังก์ชันใหม่ดึง สตางค์ part
  9. [NEW v6] Signature: ลบชื่อ line1, ขยับขึ้น 10pt, กึ่งกลาง

★ v7 — แก้ไข BG Delivery (20/04/69):
  1. [BG-#1+5+6] Format จำนวนเงิน "62,500.00 บาท" ทุกจุด (helper: _bg_fmt_money)
  2. [BG-#4] Fix logic ชื่อบริษัทแบบส่ง — ของ [counterparty] ไม่ใช่ SCM
  3. [BG-#2] ขยาย column ชื่อสัญญา 148→175, คู่สัญญา 125→145, ลบ Project Owner
  4. [BG-#NEW] เพิ่ม "ส่วนที่ 4 — รายละเอียดสำหรับการขอคืนหลักประกัน"
     ใต้ส่วนที่ 3 (ช่องว่าง 3 บรรทัดเส้นประให้เขียน)
  5. [BG-L2] แก้ชื่อบริษัท default "บจก." → "บริษัท...จำกัด" เต็ม
  6. [BG-L2] Smart word-boundary wrap — ตัดที่ space/คำ แทนตัวอักษรกลางคำ
     (ปัจจุบันใช้ template_utils.wrap_text)

★ v8 — TH Sarabun New 14 แบบ Word ทั้งฟอร์ม BG Delivery (2026-10)
  ขนาดตัวอักษรกำหนดผ่าน template_utils.th_pt ; ฟอร์ม อ.ส.4 คงขนาดเดิม (ช่องของแบบฟอร์มกรมสรรพากรตายตัว)

Endpoints:
  POST /generate               → อ.ส.4 stamp duty
  POST /generate_bg_delivery   → BG Delivery Form
  POST /generate_lg            → Request Approve LG
  POST /generate_pettycash     → Petty Cash
  POST /generate_messenger     → Messenger Form
  POST /generate_bg_withdraw   → หนังสือขอถอนหลักประกัน
  POST /generate_bg_poa        → หนังสือมอบอำนาจ
  POST /generate_request_doc   → Request Company Document
  POST /generate_general_letter → หนังสือทั่วไป (General Letter)
  GET  /health                 → health check
"""

import os
import json
import base64
import math
import hmac
import logging
import traceback
from io import BytesIO

from flask import Flask, request, jsonify
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter

from generate_lg_pettycash import generate_lg_pdf, generate_pettycash_pdf
from generate_messenger import generate_messenger_pdf
from generate_bg_withdraw import register_bg_withdraw_routes
from generate_request_doc import register_request_doc_routes
from generate_general_letter import register_general_letter_routes
from generate_warning_letter import register_warning_letter_routes
from generate_training_agreement import register_training_agreement_routes

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================================================
# FONT — THSarabunNew (guard ป้องกัน register ซ้ำ)
# ============================================================
THAI_FONT      = 'THSarabunNew'
THAI_FONT_BOLD = 'THSarabunNew-Bold'

_FONT_SEARCH = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts'),
    '/app/fonts',
    os.path.expanduser('~/fonts'),
]

def _find_font(fn):
    for d in _FONT_SEARCH:
        p = os.path.join(d, fn)
        if os.path.isfile(p):
            return p
    return None

def _register_fonts_once():
    """
    ★ แก้ไข #1: ลงทะเบียนฟอนต์เพียงครั้งเดียว
    ตรวจสอบก่อนว่า register แล้วหรือยัง ป้องกัน duplicate registration
    และ conflict กับ generate_lg_pettycash.py ที่มี guard ของตัวเอง
    """
    font_pairs = [
        ('THSarabunNew',      'THSarabunNew.ttf'),
        ('THSarabunNew-Bold', 'THSarabunNew-Bold.ttf'),
    ]
    for name, fn in font_pairs:
        try:
            pdfmetrics.getFont(name)
            logger.debug(f"ฟอนต์ '{name}' ถูก register แล้ว — ข้าม")
        except KeyError:
            p = _find_font(fn)
            if p:
                pdfmetrics.registerFont(TTFont(name, p))
                logger.info(f"ลงทะเบียนฟอนต์: {name} จาก {p}")
            else:
                logger.warning(f"ไม่พบฟอนต์ '{fn}' ใน: {_FONT_SEARCH}")

_register_fonts_once()

# ============================================================
# CONFIG
# ============================================================
TEMPLATE_PATH = os.environ.get('OS4_TEMPLATE', './os4_blank.pdf')
API_KEY       = os.environ.get('OS4_API_KEY', '')
DEBUG_MODE    = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

if not os.path.exists(TEMPLATE_PATH):
    logger.error(f"Template ไม่พบ: {TEMPLATE_PATH} — กรุณาตั้งค่า OS4_TEMPLATE")
    _TEMPLATE_MISSING = True
else:
    _TEMPLATE_MISSING = False
    logger.info(f"Template: {TEMPLATE_PATH} ✓")


def _check_key():
    """
    ★ แก้ไข #3: ตรวจ API Key ด้วย hmac.compare_digest
    ป้องกัน timing attack — ใช้เวลาเท่ากันไม่ว่า key จะถูกหรือผิด
    """
    if not API_KEY:
        return None
    incoming = request.headers.get('X-API-Key', '')
    if not hmac.compare_digest(incoming.encode('utf-8'), API_KEY.encode('utf-8')):
        logger.warning(f"API key ไม่ถูกต้อง จาก IP: {request.remote_addr}")
        return jsonify({'success': False, 'message': 'Invalid API key'}), 401
    return None


def _safe_error(e, context=''):
    """
    ★ แก้ไข #4: จัดการ error message แยก debug/production
    ใน production: ไม่เปิดเผย internal details
    ใน debug: แสดง stack trace เต็ม
    """
    logger.error(f"Error [{context}]: {e}\n{traceback.format_exc()}")
    if DEBUG_MODE:
        return {'success': False, 'message': f'[{context}] {str(e)}'}
    return {'success': False, 'message': 'เกิดข้อผิดพลาดในการสร้าง PDF กรุณาลองใหม่อีกครั้ง'}


def _validate_list_field(data, field, min_len=0):
    """
    ★ แก้ไข #2: Validate ว่า field เป็น list จริงๆ
    ป้องกัน crash เมื่อ client ส่ง items เป็น string หรือ dict
    """
    val = data.get(field, [])
    if not isinstance(val, list):
        logger.warning(f"Field '{field}' ควรเป็น list แต่ได้รับ {type(val).__name__}")
        return []
    return val


# ════════════════════════════════════════════════════════════
# 1. อ.ส.4 STAMP DUTY
# ════════════════════════════════════════════════════════════

TIN_C = [145.9, 162.6, 173.7, 184.7, 195.8, 212.3, 223.4, 234.5, 245.6, 256.7, 273.5, 284.7, 301.2]
BR_C  = [352.3, 364.3, 376.3, 388.2, 400.3]
ZIP_C = [364.9, 376.9, 389.0, 401.0, 413.1]


def build_fields(d):
    """สร้าง list ของ field ที่จะ overlay บน PDF template"""
    fields = []

    def add(x, yt, text, fs=9, cen=False):
        if text and str(text).strip():
            fields.append({
                'x': x, 'y_top': yt,
                'text': str(text),
                'fs': fs,
                'centered': cen
            })

    def digits(s, centers, yt, fs=9):
        s = str(s or '').replace(' ', '').replace('-', '')
        for i, c in enumerate(s[:len(centers)]):
            add(centers[i], yt, c, fs, True)

    # ── ส่วนหัว ──
    add(175, 87, d.get('branchOffice', ''))
    add(410, 87, d.get('day', ''))
    add(470, 87, d.get('month', ''))
    add(548, 87, d.get('year', ''))

    # ── ข้อมูลผู้เสียภาษี ──
    add(96, 104, d.get('taxpayerName', ''))
    digits(d.get('taxpayerTIN', ''), TIN_C, 119)
    digits(d.get('taxpayerBranch', '00000'), BR_C, 119)

    ta = d.get('tAddr', d.get('taxpayerAddr', {}))
    add(85,  138, ta.get('building', '-'),    8)
    add(239, 138, ta.get('room', '-'),         8)
    add(314, 138, ta.get('floor', '-'),        8)
    add(363, 138, ta.get('village', '-'),      8)
    add(482, 138, ta.get('number', '-'),       8)
    add(543, 138, ta.get('moo', '-'),          8)
    add(80,  157, ta.get('soi', '-'),          8)
    add(210, 157, ta.get('yaek', '-'),         8)
    add(310, 157, ta.get('road', '-'),         8)
    add(465, 157, ta.get('subDistrict', '-'),  8)
    add(90,  172, ta.get('district', '-'),     8)
    add(240, 172, ta.get('province', '-'),     8)
    digits(ta.get('zip', ''), ZIP_C, 170, 8)

    # ── ข้อมูลคู่สัญญา ──
    add(96, 190, d.get('counterpartyName', ''))
    digits(d.get('counterpartyTIN', ''), TIN_C, 213)
    digits(d.get('counterpartyBranch', '00000'), BR_C, 213)

    ca = d.get('cpAddr', d.get('counterpartyAddr', {}))
    add(85,  232, ca.get('building', '-'),    8)
    add(239, 232, ca.get('room', '-'),         8)
    add(314, 232, ca.get('floor', '-'),        8)
    add(363, 232, ca.get('village', '-'),      8)
    add(482, 232, ca.get('number', '-'),       8)
    add(543, 232, ca.get('moo', '-'),          8)
    add(80,  249, ca.get('soi', '-'),          8)
    add(210, 249, ca.get('yaek', '-'),         8)
    add(310, 249, ca.get('road', '-'),         8)
    add(465, 249, ca.get('subDistrict', '-'),  8)
    add(90,  266, ca.get('district', '-'),     8)
    add(240, 266, ca.get('province', '-'),     8)
    digits(ca.get('zip', ''), ZIP_C, 264, 8)

    # ── ประเภทสัญญา ──
    ct = d.get('contractType', 'hire')
    if ct == 'hire':  add(152, 282, 'X', 9, True)
    if ct == 'lease': add(215, 282, 'X', 9, True)
    if ct == 'other':
        add(279, 282, 'X', 9, True)
        add(340, 282, d.get('contractTypeOther', ''), 8)

    add(92,  298, d.get('contractNo', ''))
    add(445, 298, d.get('contractDate', ''))
    add(140, 315, d.get('startDate', ''))
    add(150, 330, d.get('endDate', ''))

    # ── ตาราง stamp duty ──
    ROW_Y   = [540, 558, 576, 594]
    TOTAL_Y = 608
    ROW_STEP = 18

    def _pf(v):
        try:
            return float(str(v or '0').replace(',', ''))
        except (ValueError, TypeError):
            return 0.0

    def _fmt_val(v):
        try:
            n = _pf(v)
            if n <= 0:
                return ''
            return f'{int(n):,}'
        except Exception:
            return str(v or '')

    def _fmt_cent(v):
        try:
            n = _pf(v)
            if n <= 0:
                return ''
            frac = round((n - int(n)) * 100)
            return f'{frac:02d}'
        except Exception:
            return '00'

    def _fmt_duty(v):
        try:
            n = _pf(v)
            return f'{int(n):,}' if n > 0 else ''
        except Exception:
            return str(v or '')

    def _auto_duty(value_str):
        try:
            return math.ceil(_pf(value_str) / 1000)
        except Exception:
            return 0

    raw_items = d.get('items')

    if isinstance(raw_items, list) and raw_items:
        row_list = []
        for i, it in enumerate(raw_items[:4]):
            val_raw  = it.get('value', '')
            duty_raw = it.get('duty', '')
            if not duty_raw and val_raw:
                duty_calc = _auto_duty(val_raw)
                duty_raw  = duty_calc
            sur_raw  = it.get('surcharge', '-')
            tot_raw  = it.get('total', duty_raw)
            row_list.append({
                'seq':    str(it.get('seq', i + 1)),
                'clause': str(it.get('clause', '')),
                'desc':   str(it.get('desc', '')),
                'qty':    str(it.get('qty', '1')),
                'val':    str(val_raw),
                'rate':   str(it.get('rate', '')),
                'duty':   _fmt_duty(duty_raw),
                'sur':    str(sur_raw) if sur_raw else '-',
                'tot':    _fmt_duty(tot_raw),
            })
    else:
        desc_single = (
            'จ้างทำของ'     if ct == 'hire'  else
            'เช่าทรัพย์สิน' if ct == 'lease' else
            d.get('contractTypeOther', '')
        )
        clause_s  = d.get('stampClause', '4' if ct == 'hire' else '1')
        val_s     = d.get('instrumentValue', '')
        duty_s    = d.get('stampDutyAmount', '')
        if not duty_s and val_s:
            duty_s = str(_auto_duty(val_s))
        rate_s = d.get('stampRate', '')
        sur_s  = d.get('surcharge', '-')
        tot_s  = d.get('totalDuty', duty_s)
        row_list = [{
            'seq':    '1',
            'clause': clause_s,
            'desc':   desc_single,
            'qty':    '1',
            'val':    val_s,
            'rate':   rate_s,
            'duty':   _fmt_duty(duty_s),
            'sur':    sur_s,
            'tot':    _fmt_duty(tot_s),
        }]

    for ri, row in enumerate(row_list):
        ry = ROW_Y[ri]
        add(43,  ry, row['seq'],                 8, True)
        add(65,  ry, row['clause'],              8, True)
        add(85,  ry, row['desc'],                8)
        add(192, ry, row['qty'],                 8, True)
        add(220, ry, _fmt_val(row['val']),       8)
        add(280, ry, _fmt_cent(row['val']),      8, True)
        add(368, ry, row['duty'],                7)
        add(407, ry, '00',                       7, True)
        add(446, ry, row['sur'],                 7)
        add(485, ry, '00',                       7, True)
        add(524, ry, row['tot'],                 7)
        add(564, ry, '00',                       7, True)

    # ยอดรวมมูลค่าตราสาร = ผลรวมทุกแถว (เดิมพิมพ์มูลค่าของแถวแรก — ผิดเมื่อมีมากกว่า 1 รายการ)
    first_val       = sum(_pf(r['val']) for r in row_list)
    total_duty      = sum(_pf(r['duty']) for r in row_list)
    total_sur_nums  = [_pf(r['sur']) for r in row_list if r['sur'] not in ('-', '', None)]
    total_sur       = sum(total_sur_nums) if total_sur_nums else 0
    total_tot       = sum(_pf(r['tot'])  for r in row_list)

    add(220, TOTAL_Y, _fmt_val(first_val),                        8)
    add(280, TOTAL_Y, _fmt_cent(first_val),                       8, True)
    add(368, TOTAL_Y, _fmt_duty(total_duty),                      7)
    add(407, TOTAL_Y, '00',                                       7, True)
    add(446, TOTAL_Y, _fmt_duty(total_sur) if total_sur else '-', 7)
    add(485, TOTAL_Y, '00',                                       7, True)
    add(524, TOTAL_Y, _fmt_duty(total_tot),                       7)
    add(564, TOTAL_Y, '00',                                       7, True)

    sub = d.get('submittedInstrument', True)
    if sub:
        add(44, 628, 'X', 9, True)
    else:
        add(44,  644, 'X', 9, True)
        add(230, 646, d.get('notSubmittedReason', ''), 8)

    _sx = 387.5
    if d.get('signerName'):
        fields.append({
            'x': _sx, 'y_top': 693,
            'text': str(d['signerName']),
            'fs': 8, 'centered': True
        })
    if d.get('signerPosition'):
        fields.append({
            'x': _sx, 'y_top': 709,
            'text': str(d['signerPosition']),
            'fs': 8, 'centered': True
        })

    return fields


_OS4_PT = {9: 14, 8: 12, 7: 11}


def create_pdf(data):
    """สร้าง PDF อ.ส.4 โดย overlay ข้อมูลบน template"""
    if _TEMPLATE_MISSING:
        raise FileNotFoundError(f"Template ไม่พบ: {TEMPLATE_PATH}")

    fields = build_fields(data)
    reader = PdfReader(TEMPLATE_PATH)
    page   = reader.pages[0]
    pw     = float(page.mediabox.width)
    ph     = float(page.mediabox.height)

    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(pw, ph))

    for f in fields:
        # 'fs' ของช่องเป็น "หน่วยตำแหน่ง" ของแบบฟอร์ม (9 / 8 / 7 — ใช้คำนวณ y ให้ลงช่องของแบบ อ.ส.4)
        # ขนาดตัวอักษรจริง: 9 → 14 , 8 → 12 , 7 → 11 (TH Sarabun New ; เดิมไฟล์ฟอนต์รุ่นขยายให้ 13.8 / 12.2 / 10.7)
        fs = f['fs']
        c.setFont(THAI_FONT, _OS4_PT.get(fs) or round(fs * 1.53, 1))
        y = ph - f['y_top'] - fs + (3 if f.get('centered') else 6)
        if f.get('centered'):
            c.drawCentredString(f['x'], y, f['text'])
        else:
            c.drawString(f['x'] + 2, y, f['text'])

    c.save()
    packet.seek(0)

    overlay = PdfReader(packet).pages[0]
    writer  = PdfWriter()
    page.merge_page(overlay)
    writer.add_page(page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()


# ════════════════════════════════════════════════════════════
# 2. BG DELIVERY FORM
# ════════════════════════════════════════════════════════════
from reportlab.lib.pagesizes import landscape as _landscape
from reportlab.lib.colors import HexColor as _HC, white, black

_BLUE   = _HC('#1a3a7a'); _TEAL   = _HC('#0a7a6e'); _PURPLE = _HC('#6a3a9a')
_GRAY   = _HC('#555555'); _LGRAY  = _HC('#999999'); _BORDER = _HC('#bbbbbb')
_FIELD_BG = _HC('#f7f9fc'); _FIELD_BD = _HC('#d0d5dd')
_W = white; _B = black; _TF = THAI_FONT

# ขนาดตัวอักษรของ BG Delivery Form — TH Sarabun New 14 แบบ Word ทั้งฟอร์ม
# (กำหนดผ่าน th_pt ดู template_utils — ขนาดในโค้ด = ขนาดใน Word และที่โปรแกรม PDF รายงาน)
from template_utils import th_pt as _th_pt, th_box as _th_box, wrap_text as _wrap_text, company_name as _company_name
_S14 = _th_pt(14)
_S16 = _th_pt(16)


# [BG-v7] Money formatter — "62,500.00 บาท"
def _bg_fmt_money(v):
    """
    [v7] Format ตัวเลข → "62,500.00 บาท"
    - ว่าง/0 → คืนค่าว่าง ''
    - parse ได้ → "1,234.56 บาท"
    - parse ไม่ได้ → คืน string เดิม (ไม่ crash)
    """
    if v is None or v == '':
        return ''
    try:
        s = str(v).replace(',', '').replace(' ', '').replace('บาท', '').strip()
        if not s:
            return ''
        n = float(s)
        if n == 0:
            return ''
        return f'{n:,.2f} บาท'
    except (ValueError, TypeError):
        return str(v)


def _draw_checkmark_bg(c, x, y, sz, color):
    c.setStrokeColor(color)
    c.setLineWidth(1.2)
    p1x = x + sz * 0.15;  p1y = y + sz * 0.48
    p2x = x + sz * 0.38;  p2y = y + sz * 0.22
    p3x = x + sz * 0.85;  p3y = y + sz * 0.72
    c.line(p1x, p1y, p2x, p2y)
    c.line(p2x, p2y, p3x, p3y)
    c.setLineWidth(1.0)


def _bg_chk(c, x, y, on, sz=10):
    c.setLineWidth(1)
    if on:
        c.setStrokeColor(_BLUE)
        c.setFillColor(_HC('#e0e8f8'))
        c.rect(x, y, sz, sz, fill=1, stroke=1)
        _draw_checkmark_bg(c, x, y, sz, _BLUE)   # เดิมวาดสีขาวบนพื้นฟ้าอ่อน — แทบมองไม่เห็นว่าเลือกช่องไหน
    else:
        c.setStrokeColor(_BORDER)
        c.setFillColor(_W)
        c.rect(x, y, sz, sz, fill=1, stroke=1)
    c.setFillColor(_B)


def _bg_field(c, x, y, w, h, text='', fs=None):
    fs = _S14 if fs is None else fs
    c.setStrokeColor(_FIELD_BD)
    c.setFillColor(_FIELD_BG)
    c.setLineWidth(0.5)
    c.roundRect(x, y, w, h, 2, fill=1, stroke=1)
    if text:
        c.setFillColor(_B)
        c.setFont(_TF, fs)
        t = str(text)
        max_w = w - 6
        # [BG-v7-L2] Smart truncate — ลองตัดที่ space ก่อนใส่ ellipsis
        if c.stringWidth(t, _TF, fs) > max_w:
            # ตัดจนกว่าจะ fit (+ room for '…')
            while len(t) > 1 and c.stringWidth(t + '…', _TF, fs) > max_w:
                t = t[:-1]
            # [SMART] ถ้าเจอ space หลังครึ่งแรก → ตัดที่ space
            sp = t.rfind(' ')
            if sp > len(t) * 0.5:
                t = t[:sp]
            t = t + '…'
        c.drawString(x + 3, y + (h - _th_box(fs)) / 2, t)
    c.setFillColor(_B)


def _bg_label(c, x, y, text, fs=None):
    fs = _S14 if fs is None else fs
    c.setFont(_TF, fs)
    c.setFillColor(_GRAY)
    c.drawString(x, y, text)
    c.setFillColor(_B)


def _bg_section(c, x, y, w, text, fs=None):
    fs = _S14 if fs is None else fs
    c.setStrokeColor(_BLUE)
    c.setLineWidth(2)
    c.line(x, y + 2, x, y - 12)
    c.setFont(_TF, fs)
    c.setFillColor(_BLUE)
    c.drawString(x + 8, y - 9, text)
    c.setStrokeColor(_HC('#dde2ea'))
    c.setLineWidth(0.5)
    c.line(x, y - 14, x + w, y - 14)
    c.setFillColor(_B)
    return y - 22


def _bg_sign(c, x, y, title, w=170, h=68):
    """กล่องลงนาม: หัวข้อ / เส้นลงนาม / (ชื่อ) / วันที่"""
    c.setStrokeColor(_HC('#c0c8d8'))
    c.setLineWidth(0.8)
    c.setDash(4, 3)
    c.roundRect(x, y, w, h, 4)
    c.setDash()
    c.setFont(_TF, _S14)
    c.setFillColor(_GRAY)
    c.drawCentredString(x + w / 2, y + h - 13, title)
    c.setStrokeColor(_HC('#b0b8c8'))
    c.setLineWidth(0.5)
    c.line(x + 15, y + h - 36, x + w - 15, y + h - 36)
    c.setFillColor(_LGRAY)
    c.drawCentredString(x + w / 2, y + h - 49, '(                                               )')
    c.drawCentredString(x + w / 2, y + h - 62, 'วันที่ ........./................/...........')
    c.setFillColor(_B)


def _create_bg_delivery_pdf(d):
    """สร้าง BG Delivery Form (2 หน้า: Landscape + Portrait)
    
    ★ v7 แก้ไข:
      [BG-#1+5+6] จำนวนเงินใช้ _bg_fmt_money() → "62,500.00 บาท"
      [BG-#4]     Logic "ของ [X]" แบบส่ง = counterparty (cpy) ไม่ใช่ SCM
      [BG-#2]     Column widths: ชื่อสัญญา 148→175, คู่สัญญา 125→145, ลบ Project Owner
    """
    from reportlab.lib.pagesizes import A4
    A4W, A4H   = A4
    LW, LH     = _landscape(A4)
    buf        = BytesIO()
    c          = canvas.Canvas(buf)

    sn  = d.get('senderName', '');    sc  = d.get('senderCompany', '');   sp  = d.get('senderPhone', '')
    rn  = d.get('receiverName', '');  rc  = d.get('receiverCompany', ''); rp  = d.get('receiverPhone', '')
    cno = d.get('contractNo', '');    cnm = d.get('contractName', '')
    dt  = d.get('docTypeText', 'หนังสือค้ำประกันสัญญา')
    bgn = d.get('bgNumber', '');      isd = d.get('issueDate', '')
    # [BG-v7 #1+5+6] Format จำนวนเงินครั้งเดียวที่นี่ — ใช้ซ้ำทุกจุด
    bgv = _bg_fmt_money(d.get('bgValue', ''))
    bge = d.get('bgExpiry', '');      cpy = d.get('counterparty', '');    po  = d.get('poNumber', '')
    # ธนาคาร / สาขา / ชื่อบริษัท มาจาก web app (ค่าเริ่มต้นกำหนดที่หน้า Admin) — ไม่ได้รับ = เว้นว่าง
    own = d.get('projectOwner', '');  bnk = d.get('bankName') or ''
    bbr = d.get('bankBranch') or ''
    chd = d.get('companyForHeader') or _company_name(d.get('entity') or d.get('entityKey') or '')
    gcat  = d.get('guaranteeCategory', 'contract')
    ptype = d.get('paymentType', 'bank_lg')
    td    = d.get('thaiDay', '');   tm  = d.get('thaiMonth', '');  tyr = d.get('thaiYear', '')
    ib = gcat == 'bid'; ic = gcat == 'contract'; ii = gcat == 'insurance'

    # ════ หน้า 1 LANDSCAPE ════
    c.setPageSize(_landscape(A4))
    pw, ph = LW, LH
    mx = 35; mr = pw - 35

    c.setFont(THAI_FONT_BOLD, _S16); c.setFillColor(_BLUE)
    c.drawCentredString(pw / 2, ph - 38, 'แบบฟอร์มนำส่งหนังสือค้ำประกัน')
    c.setFont(_TF, _S14); c.setFillColor(_LGRAY)
    c.drawCentredString(pw / 2, ph - 52, 'กรมธรรม์ประกันภัย / Bank Guarantee Delivery Form')
    c.setStrokeColor(_BLUE); c.setLineWidth(1.5)
    c.line(pw / 2 - 140, ph - 59, pw / 2 + 140, ph - 59)

    y = _bg_section(c, mx, ph - 72, mr - mx, 'ส่วนที่ 1 — ผู้นำส่งเอกสาร / ผู้รับเอกสาร')
    half = (mr - mx) / 2 - 10; lx = mx; rx = mx + half + 20; rh = 17; g = 5; lw = 36

    y -= 5
    c.setFont(_TF, _S14)
    c.setFillColor(_TEAL);  c.drawString(lx + 5, y, 'ผู้นำส่งเอกสาร')
    c.setFillColor(_BLUE);  c.drawString(rx + 5, y, 'ผู้รับเอกสาร')

    for i, (lb, vl, vr) in enumerate([('ชื่อ', sn, rn), ('บริษัท', sc, rc), ('โทร', sp, rp)]):
        fy = y - 22 - i * (rh + g)
        _bg_label(c, lx + 5, fy + 4, lb)
        _bg_field(c, lx + lw + 10, fy, half - lw - 15, rh, vl)
        _bg_label(c, rx + 5, fy + 4, lb)
        _bg_field(c, rx + lw + 10, fy, half - lw - 15, rh, vr)

    ty = y - 22 - 2 * (rh + g) - 12
    ty = _bg_section(c, mx, ty, mr - mx, 'ส่วนที่ 2 — ข้อมูลจัดเก็บเอกสาร')

    # ความกว้างคอลัมน์รวม = ความกว้างเนื้อหา (772pt) พอดี — เดิมรวม 782pt ตารางล้นขอบขวา 10pt
    hds = ['#', 'เลขที่สัญญา', 'ชื่อสัญญา', 'ประเภทเอกสาร', 'เลขที่เอกสาร',
           'ลงวันที่', 'จำนวนเงิน (บาท)', 'วันครบกำหนด', 'คู่สัญญา', 'เลขที่ PO']
    cw_tbl = [22, 68, 154, 76, 74, 56, 84, 64, 102, 72]
    tw  = sum(cw_tbl); tx_tbl = mx; thh = 20; lh_tbl = 14; max_ln = 4
    tdh = max_ln * lh_tbl + 8

    c.setFillColor(_BLUE); c.rect(tx_tbl, ty - thh, tw, thh, fill=1)
    c.setFillColor(_W); c.setFont(_TF, _S14)
    cx_ = tx_tbl
    for i, ht in enumerate(hds):
        c.drawCentredString(cx_ + cw_tbl[i] / 2, ty - thh + 6, ht)
        cx_ += cw_tbl[i]

    c.setStrokeColor(_BORDER); c.setLineWidth(0.4); c.setFillColor(_W)
    c.rect(tx_tbl, ty - thh - tdh, tw, tdh, fill=1, stroke=1)
    cx_ = tx_tbl
    for w in cw_tbl[:-1]:
        cx_ += w; c.line(cx_, ty - thh, cx_, ty - thh - tdh)

    # [BG-v7 #1] bgv = formatted money แล้ว | ลบ own (Project Owner) ออก
    vs = ['1', cno, cnm, dt, bgn, isd, bgv, bge, cpy, po]
    c.setFont(_TF, _S14); c.setFillColor(_B)
    cx_ = tx_tbl
    for i, v in enumerate(vs):
        # ตัดบรรทัดที่ช่องว่างก่อน และไม่แยกสระ/วรรณยุกต์ออกจากพยัญชนะ
        ls = _wrap_text(lambda t: c.stringWidth(t, _TF, _S14), str(v or ''), cw_tbl[i] - 6, max_ln)
        for li, ln in enumerate(ls):
            c.drawString(cx_ + 3, ty - thh - 13 - li * lh_tbl, ln)
        cx_ += cw_tbl[i]

    sy = ty - thh - tdh - 10
    sy = _bg_section(c, mx, sy, mr - mx, 'ส่วนที่ 3 — สำหรับเจ้าหน้าที่รับเอกสาร')
    sy -= 5
    _bg_label(c, mx + 10, sy, 'ข้าพเจ้าตรวจสอบรายละเอียดแล้ว ถูกต้องครบถ้วน')
    sx = pw / 2 - 190
    _bg_sign(c, sx, sy - 80, 'ลงนามผู้นำส่ง')
    _bg_sign(c, sx + 210, sy - 80, 'ลงนามผู้รับเอกสาร')

    # ═══════════════════════════════════════════════════════
    # [BG-v7] ส่วนที่ 4 — รายละเอียดสำหรับการขอคืนหลักประกัน
    # ═══════════════════════════════════════════════════════
    # ตำแหน่ง: ใต้ส่วนที่ 3 (ใต้กล่องลงนาม) ; เส้นประ 3 บรรทัดให้เขียนด้วยมือ
    s4y = sy - 80 - 12
    s4y = _bg_section(c, mx, s4y, mr - mx, 'ส่วนที่ 4 — รายละเอียดสำหรับการขอคืนหลักประกัน')
    _line_w  = mr - mx - 20          # เว้น padding 10 ซ้าย + 10 ขวา
    _line_x1 = mx + 10
    _line_x2 = _line_x1 + _line_w
    for _i in range(3):
        _ly = s4y - 4 - _i * 18      # line spacing 18pt
        c.setStrokeColor(_HC('#aaaaaa'))
        c.setLineWidth(0.5)
        c.setDash(1, 2)              # dotted line
        c.line(_line_x1, _ly, _line_x2, _ly)
    c.setDash()                      # reset dash

    c.showPage()

    # ════ หน้า 2 PORTRAIT ════
    from reportlab.lib.pagesizes import A4
    c.setPageSize(A4)
    pw2, ph2 = A4W, A4H; m2 = 35; fw = pw2 - 70; bw = 170
    RH = 20                       # ระยะระหว่างแถว
    FH = 17                       # ความสูงช่องกรอก
    sh = 336; st = ph2 - 25; sb = st - sh; rg = 18; rh2 = 306; rt = sb - rg; rb = rt - rh2
    sw_ = lambda t: c.stringWidth(t, _TF, _S14)

    def fit(text, max_w):
        """ข้อความบรรทัดเดียว — ยาวเกินใส่ … (ไม่ล้นกรอบ)"""
        return _wrap_text(sw_, text, max_w, 1)[0]

    def chk_text(x, y, on, text):
        _bg_chk(c, x, y, on)
        c.setFont(_TF, _S14); c.setFillColor(_B)
        c.drawString(x + 14, y + 1.5, text)

    def labelled(x, y, label, w, text, gap=6):
        """ป้าย + ช่องกรอก — ช่องเริ่มหลังป้ายพอดี ; คืนตำแหน่ง x ท้ายช่อง"""
        _bg_label(c, x, y + 4, label)
        fx = x + sw_(label) + gap
        _bg_field(c, fx, y, w - (fx - x), FH, text)
        return x + w

    def payment_rows(y):
        chk_text(m2 + 10,  y, ptype == 'cash',   'เงินสด')
        chk_text(m2 + 80,  y, ptype == 'bond',   'พันธบัตรรัฐบาลไทย')
        chk_text(m2 + 215, y, ptype == 'cheque', 'แคชเชียร์เช็ค')
        y -= 17
        chk_text(m2 + 10,  y, ptype == 'bank_lg', 'หนังสือค้ำประกันของธนาคารภายในประเทศ')
        chk_text(m2 + 270, y, ptype == 'car_insurance', 'กรมธรรม์ประกันภัย CAR & PL')
        return y

    # ── แบบส่งหลักประกัน ──
    c.setStrokeColor(_TEAL);  c.setLineWidth(1.2); c.rect(m2, sb, fw, sh)
    c.setFillColor(_TEAL); c.rect(pw2 / 2 - bw / 2, st - 9, bw, 18, fill=1)
    c.setFillColor(_W); c.setFont(_TF, _S14); c.drawCentredString(pw2 / 2, st - 3.5, 'แบบส่งหลักประกัน')
    c.setFillColor(_B)

    cy = st - 32
    x_ = labelled(m2 + 10, cy - 4, 'วันที่', 62, td)
    x_ = labelled(x_ + 10, cy - 4, 'เดือน', 110, tm)
    labelled(x_ + 10, cy - 4, 'พ.ศ.', 76, tyr)

    cy -= RH + 2
    st_ = fit(sc or cpy, fw - 60)
    c.setFont(_TF, _S14); c.setFillColor(_B); c.drawString(m2 + 10, cy, st_)
    c.setFillColor(_TEAL); c.drawString(m2 + 10 + sw_(st_) + 5, cy, 'ได้ส่ง')

    cy -= RH
    chk_text(m2 + 10,  cy, ib, 'หลักประกันซอง')
    chk_text(m2 + 120, cy, ic, 'หลักประกันสัญญา')
    chk_text(m2 + 245, cy, ii, 'เอกสารประกันภัย')

    # [BG-v7 #4] แบบส่ง: "ของ [counterparty]" — แยกเป็นแถวของตัวเอง (เดิมต่อท้ายตัวเลือก ชื่อยาวล้นกรอบ)
    cy -= RH
    labelled(m2 + 10, cy - 4, 'ของ', fw - 20, cpy or chd)

    cy -= RH + 2
    labelled(m2 + 10, cy - 4, 'สำหรับโครงการ', fw - 20, cnm)

    cy -= RH + 2
    labelled(m2 + 10, cy - 4, 'เลขที่สัญญา', 260, cno)

    cy -= RH + 2
    cy = payment_rows(cy)

    cy -= RH + 2
    x_ = labelled(m2 + 10, cy - 4, 'ชื่อธนาคาร/บริษัท', 275, bnk)
    labelled(x_ + 10, cy - 4, 'สาขา', fw - 20 - 275 - 10, bbr)

    cy -= RH + 2
    x_ = labelled(m2 + 10, cy - 4, 'เลขที่', 175, bgn)
    # [BG-v7 #5] แบบส่ง — bgv = formatted money "62,500.00 บาท" แล้ว
    x_ = labelled(x_ + 10, cy - 4, 'จำนวน', 185, bgv)
    c.setFont(_TF, _S14); c.setFillColor(_LGRAY)
    c.drawString(x_ + 10, cy, 'ครบถ้วนถูกต้องเรียบร้อย')
    _bg_sign(c, pw2 / 2 - 85, cy - 86, 'ลงชื่อผู้ส่งหลักประกัน')

    # ── แบบคืนหลักประกัน ──
    c.setStrokeColor(_PURPLE); c.setLineWidth(1.2); c.rect(m2, rb, fw, rh2)
    c.setFillColor(_PURPLE); c.rect(pw2 / 2 - bw / 2, rt - 9, bw, 18, fill=1)
    c.setFillColor(_W); c.setFont(_TF, _S14); c.drawCentredString(pw2 / 2, rt - 3.5, 'แบบคืนหลักประกัน')
    c.setFillColor(_B)

    cy2 = rt - 30
    chd_ = fit(chd, fw - 60)
    c.setFont(_TF, _S14); c.drawString(m2 + 10, cy2, chd_)
    c.setFillColor(_PURPLE); c.drawString(m2 + 10 + sw_(chd_) + 5, cy2, 'ได้คืน')

    cy2 -= RH
    for lb, cv2 in [('หลักประกันซอง', ib), ('หลักประกันสัญญา', ic), ('เอกสารประกันภัย', ii)]:
        chk_text(m2 + 10, cy2, cv2, fit(lb + '  ของ  ' + cpy, fw - 34))
        cy2 -= 17

    cy2 -= 5
    cy2 = payment_rows(cy2)

    cy2 -= RH + 2
    labelled(m2 + 10, cy2 - 4, 'ชื่อธนาคาร/บริษัท', fw - 20, bnk)

    cy2 -= RH + 2
    labelled(m2 + 10, cy2 - 4, 'สาขา', fw - 20, bbr)

    cy2 -= RH + 2
    x_ = labelled(m2 + 10, cy2 - 4, 'เลขที่', 175, bgn)
    # [BG-v7 #6] แบบคืน — bgv = formatted money "62,500.00 บาท" แล้ว
    x_ = labelled(x_ + 10, cy2 - 4, 'จำนวน', 185, bgv)
    c.setFont(_TF, _S14); c.setFillColor(_LGRAY)
    c.drawString(x_ + 10, cy2, 'ครบถ้วน')
    _bg_sign(c, pw2 / 2 - 85, cy2 - 86, 'ลงชื่อผู้คืนหลักประกัน')

    c.save()
    return buf.getvalue()


# ════════════════════════════════════════════════════════════
# ROUTES
# ════════════════════════════════════════════════════════════

@app.route('/health')
def health():
    font_ok = True
    try:
        pdfmetrics.getFont(THAI_FONT)
    except KeyError:
        font_ok = False

    return jsonify({
        'status':           'ok',
        'template_exists':  os.path.exists(TEMPLATE_PATH),
        'template_path':    TEMPLATE_PATH,
        'font':             THAI_FONT,
        'font_registered':  font_ok,
        'debug_mode':       DEBUG_MODE,
    })


@app.route('/generate', methods=['POST'])
def generate():
    try:
        err = _check_key()
        if err: return err

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No JSON body'}), 400

        pdf_bytes = create_pdf(data)
        safe_no   = (data.get('contractNo') or 'draft').replace('/', '_')

        return jsonify({
            'success':   True,
            'pdfBase64': base64.b64encode(pdf_bytes).decode(),
            'fileName':  f"OS4_{safe_no}.pdf"
        })
    except Exception as e:
        return jsonify(_safe_error(e, 'generate')), 500


@app.route('/generate_bg_delivery', methods=['POST'])
def generate_bg_delivery():
    try:
        err = _check_key()
        if err: return err

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No JSON body'}), 400

        pdf_bytes = _create_bg_delivery_pdf(data)
        fn = (data.get('contractNo') or 'BG').replace('/', '_').replace(' ', '_')

        return jsonify({
            'success':   True,
            'pdfBase64': base64.b64encode(pdf_bytes).decode(),
            'fileName':  f"BG_Delivery_{fn}.pdf"
        })
    except Exception as e:
        return jsonify(_safe_error(e, 'generate_bg_delivery')), 500


@app.route('/generate_lg', methods=['POST'])
def api_generate_lg():
    try:
        err = _check_key()
        if err: return err

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No JSON body'}), 400

        items = _validate_list_field(data, 'items')
        if not isinstance(data.get('items'), list):
            data['items'] = items

        pdf_bytes = generate_lg_pdf(data)
        pdf_b64   = base64.b64encode(pdf_bytes).decode('utf-8')

        proj  = (items[0].get('project', '') if items else '').strip()
        safe  = ''.join(
            ch for ch in proj[:40]
            if ch.isalnum() or ch in '_- ' or '\u0e00' <= ch <= '\u0e7f'
        )
        filename = 'Request_Approve_LG_' + (safe.strip() or 'form') + '.pdf'

        return jsonify({'success': True, 'pdfBase64': pdf_b64, 'fileName': filename})
    except Exception as e:
        return jsonify(_safe_error(e, 'generate_lg')), 500


@app.route('/generate_pettycash', methods=['POST'])
def api_generate_pettycash():
    try:
        err = _check_key()
        if err: return err

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No JSON body'}), 400

        items = _validate_list_field(data, 'items')
        if not isinstance(data.get('items'), list):
            data['items'] = items

        pdf_bytes = generate_pettycash_pdf(data)
        pdf_b64   = base64.b64encode(pdf_bytes).decode('utf-8')

        desc  = (items[0].get('description', '') if items else '').strip()
        safe  = ''.join(
            ch for ch in desc[:40]
            if ch.isalnum() or ch in '_- ' or '\u0e00' <= ch <= '\u0e7f'
        )
        filename = 'PettyCash_' + (safe.strip() or 'form') + '.pdf'

        return jsonify({'success': True, 'pdfBase64': pdf_b64, 'fileName': filename})
    except Exception as e:
        return jsonify(_safe_error(e, 'generate_pettycash')), 500


@app.route('/generate_messenger', methods=['POST'])
def api_generate_messenger():
    try:
        err = _check_key()
        if err: return err

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No JSON body'}), 400

        pdf_bytes = generate_messenger_pdf(data)
        pdf_b64   = base64.b64encode(pdf_bytes).decode('utf-8')

        cn       = (data.get('contractNumber') or 'MSG').replace('/', '_').replace(' ', '_')
        filename = f'Messenger_{cn}.pdf'

        return jsonify({'success': True, 'pdfBase64': pdf_b64, 'fileName': filename})
    except Exception as e:
        return jsonify(_safe_error(e, 'generate_messenger')), 500


# ── Register external route modules ──
register_bg_withdraw_routes(app)
register_request_doc_routes(app)
register_general_letter_routes(app)
register_warning_letter_routes(app)
register_training_agreement_routes(app)

# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting server on port {port} | debug={DEBUG_MODE}")
    app.run(host='0.0.0.0', port=port, debug=DEBUG_MODE)
