#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_lg_pettycash.py — Landscape A4
1. Request Approve LG — auto-expand ไม่จำกัดรายการ
2. Petty Cash
ทั้งคู่เป็น Landscape A4 — พื้นที่กว้างพอสำหรับข้อมูลภาษาไทยยาวๆ

★ v4 — แก้ไข:
  1. Font registration guard — ใช้ try/except ตรวจสอบก่อน register
  2. เพิ่ม raise FileNotFoundError เมื่อหาฟอนต์ไม่พบ (แทน silent fail)
  3. Validate items type ก่อนใช้งาน
  4. Font size +2pt ทุกจุด (กลับค่าจาก v3 ที่ลดไป -2pt)
"""

import io
import logging
import os
from datetime import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

# ── FONT PATH ────────────────────────────────────────────────────────────────
_FONT_SEARCH = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts'),
    '/app/fonts',
    os.path.expanduser('~/fonts'),
]

def _find_font(fn):
    """ค้นหาไฟล์ฟอนต์จากหลาย path"""
    for d in _FONT_SEARCH:
        p = os.path.join(d, fn)
        if os.path.isfile(p):
            return p
    return None


# ★ แก้ไข #1: guard ป้องกัน register ซ้ำ + raise เมื่อหาไม่พบ
_FONT_REG = False

def _register_fonts():
    """
    ลงทะเบียนฟอนต์ TH Sarabun New
    - ตรวจสอบ _FONT_REG flag ป้องกัน register ซ้ำ
    - ใช้ pdfmetrics.getFont() ตรวจสอบซ้ำก่อน register จริง
    - ★ แก้ไข #2: raise FileNotFoundError เมื่อหาฟอนต์ไม่พบ
    """
    global _FONT_REG
    if _FONT_REG:
        return

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
            if not p:
                # ★ แก้ไข: raise แทนที่จะ silent fail
                raise FileNotFoundError(
                    f"ไม่พบฟอนต์ '{fn}' — ค้นหาใน: {_FONT_SEARCH}\n"
                    f"กรุณาวาง font files ไว้ใน ./fonts/ หรือ /app/fonts/"
                )
            pdfmetrics.registerFont(TTFont(name, p))
            logger.info(f"ลงทะเบียนฟอนต์: {name} จาก {p}")

    _FONT_REG = True


# ── SHARED ADDRESS (ทุก entity ใช้ที่อยู่เดียวกัน) ───────────────────────────────
_SCM_ADDR = {
    'address': '92/41 อาคารสาธรธานี 2 ชั้นที่ 15 ถนนสาทรเหนือ แขวงสีลม เขตบางรัก กรุงเทพมหานคร 10500',
    'phone':   '02-116-4312, 02-116-4213',
    'fax':     '02-235-3699',
    # taxId ไม่รวมที่นี่ — แต่ละ entity มีเลขต่างกัน (ดูใน _ENTITY_MAP)
}

# ── ENTITY MAP — แปลง entity key → company info ─────────────────────────────────
# entity key = lowercase + no space (ตรงกับที่ GAS ส่งมาใน field 'entity')
# ที่อยู่/โทร/fax ใช้ร่วมกันทุก entity — taxId แยกในแต่ละ entity
# ── TIN จาก Companies sheet (ภาพ 20/03/2569) ─────────────────────────────────
# row 2: บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด          → 0105552095731  (SCM Tech หลัก)
# row 3: บริษัท เอสซีเอ็ม เอส เทคโนโลจีส์ จำกัด         → 0105562133562
# row 4: บริษัท เอสซีเอ็ม ซี เทคโนโลจีส์ จำกัด           → 0105563004553
# row 5: บริษัท เอสซีเอ็ม ไซเบอร์ จำกัด                   → 0105567042204
# row 6: บริษัท เอสซีเอ็ม บิซิเนส คอนเนคท์ จำกัด          → 0105568091021
# row 7: บริษัท เอสซีเอ็ม บีทูบี จำกัด                     → 0105569003087
# row 8: บริษัท ฟ้าคลาวด์ อินโนเทค จำกัด                   → 0105569004881
_ENTITY_MAP = {
    # entity key (lowercase, no space) → companyName + TIN
    'scmtech':  {
        'companyName':   'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด',
        'companyNameEn': 'SCM Technologies Co., Ltd.',
        'taxId':         '0105552095731',
    },
    'scms':     {
        'companyName':   'บริษัท เอสซีเอ็ม เอส เทคโนโลจีส์ จำกัด',
        'companyNameEn': 'SCM S Technologies Co., Ltd.',
        'taxId':         '0105562133562',
    },
    'scmc':     {
        'companyName':   'บริษัท เอสซีเอ็ม ซี เทคโนโลจีส์ จำกัด',
        'companyNameEn': 'SCM C Technologies Co., Ltd.',
        'taxId':         '0105563004553',
    },
    'holding':  {
        'companyName':   'บริษัท เอสซีเอ็ม โฮลดิ้ง จำกัด',
        'companyNameEn': 'SCM Holding Co., Ltd.',
        # taxId: ไม่ hardcode — ดึงจาก Companies sheet ผ่าน GAS เสมอ
        # ถ้า GAS ไม่ส่งมา → fallback _SCM_ADDR ซึ่งไม่มี taxId → คืน '-'
    },
    'cyber':    {
        'companyName':   'บริษัท เอสซีเอ็ม ไซเบอร์ จำกัด',
        'companyNameEn': 'SCM Cyber Co., Ltd.',
        'taxId':         '0105567042204',
    },
    'bc':       {
        'companyName':   'บริษัท เอสซีเอ็ม บิซิเนส คอนเนคท์ จำกัด',
        'companyNameEn': 'SCM Business Connect Co., Ltd.',
        'taxId':         '0105568091021',
    },
    'b2b':      {
        'companyName':   'บริษัท เอสซีเอ็ม บีทูบี จำกัด',
        'companyNameEn': 'SCM B2B Co., Ltd.',
        'taxId':         '0105569003087',
    },
    'fahcloud': {
        'companyName':   'บริษัท ฟ้าคลาวด์ อินโนเทค จำกัด',
        'companyNameEn': 'Fahcloud Innotech Co., Ltd.',
        'taxId':         '0105569004881',
    },
}

# DEFAULT = SCM Technologies (ถ้าไม่ระบุ entity)
# _SCM_DEFAULT: ใช้เป็น last-resort fallback (address/phone/fax เท่านั้น)
# ★ ไม่รวม taxId — เพื่อกัน entity ที่ไม่มี taxId ใน map ได้รับ TIN ผิด
_SCM_DEFAULT = {
    **_SCM_ADDR,                          # address, phone, fax
    **_ENTITY_MAP['scmtech'],             # companyName, companyNameEn ของ default
    # taxId: จงใจไม่ใส่ที่นี่ → ถ้าหาไม่ได้จากทุก source จะคืน '-'
}
# ลบ taxId ออกจาก _SCM_DEFAULT เพื่อไม่ให้ entity ที่ไม่มี TIN ใน map ได้ TIN ผิด
_SCM_DEFAULT.pop('taxId', None)

def _resolve_entity(data):
    """
    แปลง entity field เป็น company info dict
    Priority: data['entity'] → _ENTITY_MAP → scmtech (default)
    รองรับ: 'scmtech', 'SCM Tech', 'SCMTECH' (normalize ก่อน lookup)
    """
    raw  = str(data.get('entity') or '').lower().replace(' ', '')
    info = _ENTITY_MAP.get(raw, _ENTITY_MAP['scmtech'])
    # merge: _SCM_ADDR (address/phone/fax) + entity info (companyName/taxId)
    # entity info อยู่ด้านขวา → override _SCM_ADDR ถ้า key ซ้ำ
    return {**_SCM_ADDR, **info}

def _co(data, key):
    """
    ดึงค่า company info ตาม entity
    Priority:
      1. data[key]          — GAS ส่งมาโดยตรง (สูงสุด)
      2. _resolve_entity()  — จาก _ENTITY_MAP ตาม entity key
      3. _SCM_DEFAULT       — fallback สุดท้าย (ไม่มี taxId)
      4. '-'                — ค่าว่าง
    """
    # 1. GAS ส่งมาโดยตรง → ใช้เลย
    v = data.get(key)
    if v and str(v).strip():
        return str(v).strip()
    # 2. ดึงจาก entity map
    entity_info = _resolve_entity(data)
    if key in entity_info and entity_info[key]:
        return str(entity_info[key]).strip()
    # 3. fallback _SCM_DEFAULT (ไม่มี taxId → ป้องกันคืน TIN ผิด)
    return str(_SCM_DEFAULT.get(key, '-'))

# ── PAGE (Landscape A4) ───────────────────────────────────────────────────────
L_W, L_H = landscape(A4)    # 841.89 x 595.28 pt
ML = 20 * mm; MR = 20 * mm; MT = 15 * mm; MB = 14 * mm
CW = L_W - ML - MR          # ~525 pt content width

# ── COLORS ───────────────────────────────────────────────────────────────────
CP   = HexColor('#1a237e');  CA   = HexColor('#1e40af')
CH   = HexColor('#333333');  CT   = HexColor('#222222')
CM   = HexColor('#666666');  CL   = HexColor('#999999')
CBG  = HexColor('#f8f9fa');  CBG2 = HexColor('#e8eaf6')
CB   = HexColor('#cccccc');  CB2  = HexColor('#e2e8f0')
CR   = HexColor('#c62828');  CG   = HexColor('#0d9488')
CRA  = HexColor('#f5f5ff')

# ★ เปลี่ยนจาก FreeSerif → THSarabunNew
F  = 'THSarabunNew'
FB = 'THSarabunNew-Bold'


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _fm(v):
    """Format ตัวเลขเป็น comma-separated พร้อม 2 ทศนิยม, คืน '-' ถ้าเป็น 0"""
    try:
        n = float(str(v or '0').replace(',', ''))
        return '-' if n == 0 else f"{n:,.2f}"
    except (ValueError, TypeError):
        return '-'

def _fmb(v):
    """Format ตัวเลข คืน '' ถ้าเป็น 0 (สำหรับ cell ว่าง)"""
    try:
        n = float(str(v or '0').replace(',', ''))
        return '' if n == 0 else f"{n:,.2f}"
    except (ValueError, TypeError):
        return ''

def _pf(v):
    """Parse float อย่างปลอดภัย"""
    try:
        return float(str(v or '0').replace(',', ''))
    except (ValueError, TypeError):
        return 0.0

def _s(v, d='-'):
    """Safe string — คืน default ถ้าว่าง"""
    s = str(v or '').strip()
    return s if s else d

def _tbe():
    """วันที่ปัจจุบันในรูปแบบ พ.ศ."""
    n = datetime.now()
    return f"{n.day:02d}/{n.month:02d}/{n.year + 543}"

def _tx(c, x, y, t, f=F, s=9, co=CT, a='left'):
    """
    วาดข้อความ
    ★ default size=9 (+2 จาก v3 ที่เป็น 7)
    """
    c.setFont(f, s)
    c.setFillColor(co)
    if a == 'center':
        c.drawCentredString(x, y, t)
    elif a == 'right':
        c.drawRightString(x, y, t)
    else:
        c.drawString(x, y, t)

def _ln(c, x1, y1, x2, y2, co=CB, w=0.5, d=None):
    """วาดเส้น"""
    c.setStrokeColor(co); c.setLineWidth(w)
    if d:
        c.setDash(d[0], d[1])
    else:
        c.setDash([], 0)
    c.line(x1, y1, x2, y2)
    c.setDash([], 0)

def _rc(c, x, y, w, h, fi=None, st=CB, sw=0.5, r=0):
    """วาด rectangle"""
    c.setStrokeColor(st); c.setLineWidth(sw)
    if fi:
        c.setFillColor(fi)
        if r > 0: c.roundRect(x, y, w, h, r, fill=1, stroke=1)
        else:      c.rect(x, y, w, h, fill=1, stroke=1)
    else:
        if r > 0: c.roundRect(x, y, w, h, r, fill=0, stroke=1)
        else:      c.rect(x, y, w, h, fill=0, stroke=1)

def _trunc(cv, t, fo, sz, mw):
    """ตัดข้อความตาม pixel width จริง พร้อม ellipsis"""
    if not t:
        return t
    t = str(t)
    if cv.stringWidth(t, fo, sz) <= mw:
        return t
    while len(t) > 1 and cv.stringWidth(t + '…', fo, sz) > mw:
        t = t[:-1]
    return t + '…'

def _wrap(cv, t, fo, sz, mw, ml=2):
    """
    แบ่งข้อความเป็นหลายบรรทัด — สูงสุด ml บรรทัด
    บรรทัดสุดท้ายจะมี '…' ถ้าข้อความยังเหลืออยู่
    """
    if not t:
        return ['']
    t = str(t)
    if cv.stringWidth(t, fo, sz) <= mw:
        return [t]

    lines = []; rem = t
    while rem and len(lines) < ml:
        fit = rem
        while len(fit) > 1 and cv.stringWidth(fit, fo, sz) > mw:
            fit = fit[:-1]
        if len(lines) == ml - 1 and len(fit) < len(rem):
            while len(fit) > 1 and cv.stringWidth(fit + '…', fo, sz) > mw:
                fit = fit[:-1]
            lines.append(fit + '…')
            break
        else:
            lines.append(fit)
            rem = rem[len(fit):]
    return lines or ['']

def _safe_items(data):
    """
    ★ แก้ไข #3: Validate items type
    ป้องกัน crash เมื่อ client ส่ง items เป็น string, dict หรือ None
    """
    items = data.get('items')
    if not isinstance(items, list):
        if items is not None:
            logger.warning(f"'items' ควรเป็น list แต่ได้รับ {type(items).__name__} — ใช้ list ว่าง")
        return [{}]
    return items if items else [{}]


# ════════════════════════════════════════════════════════════
# 1. REQUEST APPROVE LG — Landscape A4
# ════════════════════════════════════════════════════════════

def generate_lg_pdf(data):
    """
    สร้าง PDF ขออนุมัติหนังสือค้ำประกัน (Request Approve LG)
    รองรับหลายหน้า — auto paginate เมื่อรายการมากกว่า 10 รายการ
    """
    _register_fonts()
    buf = io.BytesIO()
    cv  = canvas.Canvas(buf, pagesize=landscape(A4))

    # ★ แก้ไข #3: ใช้ _safe_items แทน data.get('items') โดยตรง
    items = _safe_items(data)

    tot_amt = sum(_pf(it.get('amount')) for it in items)
    tot_fee = sum(_pf(it.get('fee'))    for it in items)

    # Column widths — landscape มีพื้นที่กว้างกว่า portrait มาก
    col_raw = [22, 62, 65, 200, 40, 58, 58, 30, 80, 80]
    sc  = CW / sum(col_raw)
    cw  = [w * sc for w in col_raw]

    row_h = 30; hdr_h = 22
    fp_max = 10   # รายการสูงสุดหน้าแรก (มี header)
    np_max = 18   # รายการสูงสุดหน้าถัดไป

    # แบ่งหน้า
    pages = []; rem = items[:]
    pages.append(rem[:fp_max]); rem = rem[fp_max:]
    while rem:
        pages.append(rem[:np_max]); rem = rem[np_max:]
    tp = len(pages)

    for pi, pg_items in enumerate(pages):
        is_first = pi == 0
        is_last  = pi == tp - 1
        cv.setPageSize(landscape(A4))
        pw, ph = L_W, L_H
        y  = ph - MT; tx = ML

        if is_first:
            # ── Company Header ──
            # ★ font sizes +2pt: 10→12, 6→8, 5.5→7.5, 12→14, 7→9, 7.5→9.5
            _tx(cv, pw/2, y, _co(data, 'companyName'), FB, 12, CH, 'center'); y -= 13
            en = _co(data, 'companyNameEn')
            if en != '-':
                _tx(cv, pw/2, y, f"{en} (สำนักงานใหญ่)", F, 8, CM, 'center'); y -= 10
            adr = _co(data, 'address')
            if adr != '-':
                _tx(cv, pw/2, y, adr, F, 7.5, CL, 'center'); y -= 9
            inf = (f"โทร. {_co(data, 'phone')}  "
                   f"แฟกซ์: {_co(data, 'fax')}  "
                   f"เลขประจำตัวผู้เสียภาษี: {_co(data, 'taxId')}")
            _tx(cv, pw/2, y, inf, F, 7.5, CL, 'center'); y -= 14

            _ln(cv, ML, y, pw-MR, y, CH, 1.2); y -= 16
            _tx(cv, pw/2, y, 'Request Approve LG (ขออนุมัติหนังสือค้ำประกัน)', FB, 14, CH, 'center'); y -= 10
            _ln(cv, ML, y, pw-MR, y, CH, 1.2); y -= 16

            # ── Info row ──
            c1 = ML; c1v = ML + 55; c2 = pw/2 + 10; c2v = pw/2 + 85
            _tx(cv, c1,  y, 'Date :',          FB, 9, CM)
            _tx(cv, c1v, y, _s(data.get('date', _tbe())), F, 9.5, CT)
            _tx(cv, c2,  y, 'Create LG By :',  FB, 9, CM)
            _tx(cv, c2v, y, _s(data.get('createdBy'), ''), F, 9.5, CT); y -= 13

            _tx(cv, c1,  y, 'จำนวนรายการ :',   FB, 9, CM)
            _tx(cv, c1v, y, f"{len(items)} รายการ", F, 9.5, CT)
            _tx(cv, c2,  y, 'รวมวงเงินทั้งหมด :', FB, 9, CM)
            _tx(cv, c2v, y, f"{_fm(tot_amt)} บาท", FB, 9.5, CA); y -= 16
        else:
            # ── Continuation header ──
            _tx(cv, ML, y, 'Request Approve LG (ต่อ)', FB, 10, CH)    # ★ 8→10
            _tx(cv, pw-MR, y, f"หน้า {pi+1}/{tp}", F, 7.5, CL, 'right')  # ★ 5.5→7.5
            y -= 6
            _ln(cv, ML, y, pw-MR, y, CB, 0.5); y -= 14

        # ── TABLE HEADER ──
        thy = y
        _rc(cv, tx, thy - hdr_h, CW, hdr_h, fi=HexColor('#eeeeee'), st=CB, sw=0.5)
        hds = ['No.', 'SR No.', 'เลขสัญญา', 'ชื่อโครงการ / คู่สัญญา',
               'สถานะ', 'เริ่มต้น', 'สิ้นสุด', 'เดือน', 'วงเงิน BG', 'ค่าธรรมเนียม']
        hal = ['center', 'left', 'left', 'left', 'center', 'left', 'left', 'center', 'right', 'right']
        cx = tx
        # ★ header font 6→8
        for hd, ha, w in zip(hds, hal, cw):
            hx = (cx + w/2 if ha == 'center' else
                  cx + 3   if ha == 'left'   else
                  cx + w - 3)
            _tx(cv, hx, thy - hdr_h + 7, hd, FB, 8, CH, ha)
            cx += w
        cx = tx
        for w in cw:
            cx += w
            if cx < tx + CW - 1:
                _ln(cv, cx, thy, cx, thy - hdr_h, CB, 0.3)
        y = thy - hdr_h

        # ── DATA ROWS ──
        si = 0 if pi == 0 else fp_max + (pi - 1) * np_max
        for ri, item in enumerate(pg_items):
            ai  = si + ri
            ry  = y - row_h
            bg  = CRA if ri % 2 == 1 else None
            _rc(cv, tx, ry, CW, row_h, fi=bg, st=CB2, sw=0.3)
            cx = tx
            for w in cw:
                cx += w
                if cx < tx + CW - 1:
                    _ln(cv, cx, y, cx, ry, CB2, 0.3)

            cx = tx; ty1 = ry + row_h - 10; ty2 = ry + row_h - 21

            # ★ data font: 6.5→8.5, 5.5→7.5, 6→8, 5→7
            _tx(cv, cx + cw[0]/2, ty1, str(ai+1), F, 8.5, CT, 'center'); cx += cw[0]
            _tx(cv, cx + 3, ty1, _trunc(cv, _s(item.get('sr'),       '-'), F, 8.5, cw[1]-6), F, 8.5, CT); cx += cw[1]
            _tx(cv, cx + 3, ty1, _trunc(cv, _s(item.get('contract'), '-'), F, 8.5, cw[2]-6), F, 8.5, CT); cx += cw[2]

            # ชื่อโครงการ (wrap 2 lines) + คู่สัญญา
            proj_lines = _wrap(cv, _s(item.get('project'), '-'), FB, 8.5, cw[3] - 6, 2)
            _tx(cv, cx + 3, ty1, proj_lines[0], FB, 8.5, CT)
            if len(proj_lines) > 1:
                _tx(cv, cx + 3, ty2, proj_lines[1], FB, 7.5, CT)
            else:
                cust = _s(item.get('customer'), '')
                if cust and cust != '-':
                    _tx(cv, cx + 3, ty2, _trunc(cv, cust, F, 7.5, cw[3]-6), F, 7.5, CM)
            cx += cw[3]

            urg = item.get('urgent') in [True, 'TRUE', 'true', '1']
            if urg:
                _rc(cv, cx + (cw[4]-26)/2, ty1-2, 26, 11,
                    fi=HexColor('#ffebee'), st=HexColor('#ef9a9a'), sw=0.3, r=2)
                _tx(cv, cx + cw[4]/2, ty1, 'ด่วน', FB, 7, CR, 'center')   # ★ 5→7
            else:
                _tx(cv, cx + cw[4]/2, ty1, 'ปกติ', F,  7, CL, 'center')   # ★ 5→7
            cx += cw[4]

            _tx(cv, cx + 3, ty1, _s(item.get('start'), '-'), F, 8, CT); cx += cw[5]  # ★ 6→8
            _tx(cv, cx + 3, ty1, _s(item.get('end'),   '-'), F, 8, CT); cx += cw[6]  # ★ 6→8
            _tx(cv, cx + cw[7]/2, ty1, _s(item.get('duration'), '-'), F, 8.5, CT, 'center'); cx += cw[7]  # ★ 6.5→8.5
            _tx(cv, cx + cw[8]-3, ty1, _fm(item.get('amount')), F, 8.5, CT, 'right'); cx += cw[8]         # ★ 6.5→8.5
            _tx(cv, cx + cw[9]-3, ty1, _fm(item.get('fee')),    F, 8.5, CT, 'right')                      # ★ 6.5→8.5

            y = ry

        if is_last:
            # ── Total row ──
            # ★ total/summary font: 7→9, 10→12, 5.5→7.5, 6.5→8.5
            th = 18; ty = y - th
            _rc(cv, tx, ty, CW, th, fi=CBG2, st=CB, sw=0.5)
            lx = tx
            for i in range(8): lx += cw[i]
            _tx(cv, lx - 5,              ty + 5, 'รวมทั้งหมด',   FB, 9,   CH, 'right')
            _tx(cv, tx + sum(cw[:9]) - 3, ty + 5, _fm(tot_amt),  FB, 9,   CH, 'right')
            _tx(cv, tx + sum(cw[:10])- 3, ty + 5, _fm(tot_fee),  FB, 9,   CH, 'right')
            y = ty - 8

            # ── Grand total box ──
            _rc(cv, ML + CW*0.5, y-24, CW*0.5, 24, fi=CBG2, st=CB2, sw=0.3, r=4)
            _tx(cv, pw-MR-8, y-15, f"Total Fee : {_fm(tot_fee)} บาท", FB, 12, CP, 'right')  # ★ 10→12
            y -= 34

            # ── หมายเหตุ ──
            note = _s(data.get('note', ''), '')
            if note and note != '-':
                _tx(cv, ML, y, 'หมายเหตุ :', FB, 9, CM); y -= 12   # ★ 7→9
                _tx(cv, ML + 5, y, note,      F,  9.5, CT); y -= 16  # ★ 7.5→9.5

            # ── Signature ──
            y -= 8; sgw = CW / 2 - 15
            for sx, lbl in [(ML, 'ผู้ขอ (Requested By)'), (ML + sgw + 30, 'ผู้อนุมัติ (Approved By)')]:
                _tx(cv, sx, y, lbl, FB, 8.5, CM)                           # ★ 6.5→8.5
                _ln(cv, sx, y-30, sx+sgw-10, y-30, CB, 0.5, (2, 2))
                _tx(cv, sx, y-40, 'ลงชื่อ ...................................', F, 7.5, CL)   # ★ 5.5→7.5
                _tx(cv, sx, y-50, 'วันที่ ......../........./............',    F, 7.5, CL)   # ★ 5.5→7.5

        # ── Footer ──
        _ln(cv, ML, MB+10, pw-MR, MB+10, CB2, 0.3)
        _tx(cv, pw/2, MB+2,
            f"Request Approve LG — Contract Tracker Pro  |  Generated: {_tbe()}  |  หน้า {pi+1}/{tp}",
            F, 6.5, CL, 'center')  # ★ 4.5→6.5

        if not is_last:
            cv.showPage()

    cv.save(); buf.seek(0)
    return buf.getvalue()


# ════════════════════════════════════════════════════════════
# 2. PETTY CASH — Landscape A4
# ════════════════════════════════════════════════════════════

def generate_pettycash_pdf(data):
    """
    สร้าง PDF เอกสารขออนุมัติเบิกจ่ายเงินสดย่อย (Petty Cash)
    Layout: Landscape A4
    """
    _register_fonts()
    buf = io.BytesIO()
    cv  = canvas.Canvas(buf, pagesize=landscape(A4))
    pw, ph = L_W, L_H

    # ★ แก้ไข #3: ใช้ _safe_items
    items = data.get('items', [])
    if not isinstance(items, list):
        logger.warning(f"petty cash 'items' ได้รับ {type(items).__name__} — ใช้ list ว่าง")
        items = []

    payee      = _s(data.get('payee'), '')
    pay_method = data.get('payMethod', 'cash')
    pay_date   = _s(data.get('payDate', _tbe()))
    doc_ref    = _s(data.get('docRef'), '')

    ta = sum(_pf(it.get('amount')) for it in items)
    tv = sum(_pf(it.get('vat'))    for it in items)
    tw = sum(_pf(it.get('wht'))    for it in items)
    tn = sum(_pf(it.get('net'))    for it in items)

    y = ph - MT; tx = ML

    # ── HEADER ──
    # ★ font sizes +2pt: 10→12, 6.5→8.5, 5.5→7.5, 9→11
    _ln(cv, ML, y+2, pw-MR, y+2, CP, 2)
    _tx(cv, pw/2, y-10, _co(data, 'companyName'), FB, 12, CP, 'center')   # ★ 10→12
    en = _co(data, 'companyNameEn')
    if en != '-':
        _tx(cv, pw/2, y-22, f"{en} (สำนักงานใหญ่)", F, 8.5, CM, 'center')      # ★ 6.5→8.5
    adr = _co(data, 'address')
    if adr != '-':
        _tx(cv, pw/2, y-32, adr, F, 7.5, CL, 'center')                          # ★ 5.5→7.5
    inf = (f"โทร. {_co(data, 'phone')}  "
           f"แฟกซ์: {_co(data, 'fax')}  "
           f"เลขประจำตัวผู้เสียภาษี: {_co(data, 'taxId')}")
    _tx(cv, pw/2, y-41, inf, F, 7.5, CL, 'center')                              # ★ 5.5→7.5
    y -= 50
    _ln(cv, ML, y, pw-MR, y, CP, 1.5); y -= 18

    # ── TITLE ──
    _rc(cv, ML, y-17, CW, 17, fi=CBG, st=CB2, sw=0.3, r=3)
    _tx(cv, pw/2, y-13, 'เอกสารขออนุมัติเบิกจ่าย เงินสดย่อย ( Petty Cash )', FB, 11, CP, 'center')  # ★ 9→11
    y -= 26

    # ── INFO SECTION ──
    # ★ 7→9, 7.5→9.5
    _tx(cv, ML, y, 'จ่ายให้ บมจ./บจก./หจก./หสม./บุคคลธรรมดา', FB, 9, CM)
    _tx(cv, ML+200, y, payee if payee != '-' else '', F, 9.5, CT)
    _ln(cv, ML+198, y-2, pw-MR, y-2, CB, 0.5, (1, 2)); y -= 16

    _tx(cv, ML, y, 'ชำระโดย', FB, 9, CM)
    cbx = ML + 42
    _rc(cv, cbx, y-2, 10, 10, st=CH, sw=0.5)
    if pay_method == 'cheque':
        _tx(cv, cbx+5, y, '✓', FB, 7, CP, 'center')   # ★ 5→7
    _tx(cv, cbx+13, y, 'เช็ค', F, 9, CT)              # ★ 7→9

    cbx2 = cbx + 45
    _rc(cv, cbx2, y-2, 10, 10, st=CH, sw=0.5)
    if pay_method == 'cash':
        _tx(cv, cbx2+5, y, '✓', FB, 7, CP, 'center')  # ★ 5→7
    _tx(cv, cbx2+13, y, 'เงินสด', F, 9, CT)           # ★ 7→9

    dlx = cbx2 + 60
    _tx(cv, dlx, y, 'ลงวันที่', FB, 9, CM)
    _tx(cv, dlx+40, y, pay_date, F, 9.5, CT)
    _ln(cv, dlx+38, y-2, dlx+120, y-2, CB, 0.5, (1, 2))
    rlx = dlx + 130
    _tx(cv, rlx, y, 'เลขที่', FB, 9, CM)
    _tx(cv, rlx+30, y, doc_ref if doc_ref != '-' else '', F, 9.5, CT)
    _ln(cv, rlx+28, y-2, pw-MR, y-2, CB, 0.5, (1, 2))
    y -= 16

    # ── สัญญาอ้างอิง ──
    cn = _s(data.get('contractName'), '')
    ci = _s(data.get('contractId'),   '')
    if cn and cn != '-':
        _tx(cv, ML, y, 'สัญญา :', FB, 9, CM)
        _tx(cv, ML+42, y, _trunc(cv, cn, F, 9.5, pw/2-ML-50), F, 9.5, CT)
        _tx(cv, pw/2+20, y, 'เลขที่สัญญา :', FB, 9, CM)
        _tx(cv, pw/2+90, y, ci if ci != '-' else '', F, 9.5, CT)
        y -= 14

    # ── TABLE ──
    row_h = 24; hdr_h = 26
    pc_raw = [28, 50, 250, 72, 80, 58, 72, 80]
    pc_sc  = CW / sum(pc_raw)
    pcw    = [w * pc_sc for w in pc_raw]

    thy = y
    _rc(cv, tx, thy-hdr_h, CW, hdr_h, fi=CP, st=CP, sw=0.5)

    # ★ header font 6→8, 5.5→7.5
    hds = [
        ('ลำดับ',), ('รหัสงาน',), ('รายการ',), ('เลขที่เอกสาร',),
        ('รายจ่ายก่อน', 'หักภาษี'),
        ('ภาษีซื้อ',),
        ('ภาษีหัก ณ', 'ที่จ่าย (__%)'),
        ('จำนวนเงิน', 'สุทธิ')
    ]
    cx = tx
    for ht, w in zip(hds, pcw):
        if len(ht) == 2:
            _tx(cv, cx + w/2, thy - 9,        ht[0], FB, 8,   white, 'center')  # ★ 6→8
            _tx(cv, cx + w/2, thy - hdr_h + 6, ht[1], FB, 7.5, white, 'center')  # ★ 5.5→7.5
        else:
            _tx(cv, cx + w/2, thy - hdr_h + 8, ht[0], FB, 8,   white, 'center')  # ★ 6→8
        cx += w
    y = thy - hdr_h

    # ── DATA ROWS ──
    LINE_H = 10
    dn = max(len(items), 6)
    for ri in range(dn):
        item = items[ri] if ri < len(items) else {}

        desc = _s(item.get('description'), '') if item.get('description') else ''
        # ★ 6.5→8.5
        desc_lines  = _wrap(cv, desc, F, 8.5, pcw[2] - 6, 3) if desc else ['']
        n_lines     = len(desc_lines)
        rh_actual   = max(row_h, 12 + n_lines * LINE_H)

        ry = y - rh_actual
        bg = CRA if ri % 2 == 1 else None
        _rc(cv, tx, ry, CW, rh_actual, fi=bg, st=CB2, sw=0.3)
        cx = tx
        for w in pcw:
            cx += w
            if cx < tx + CW - 1:
                _ln(cv, cx, y, cx, ry, CB2, 0.3)

        cx  = tx; tty = ry + rh_actual - 10
        seq = item.get('seq', ri + 1) if item else ri + 1

        # ★ data font: 6.5→8.5, 6→8
        _tx(cv, cx + pcw[0]/2, tty, str(seq) if item else '', F, 8.5, CT, 'center'); cx += pcw[0]
        _tx(cv, cx + 3, tty, _s(item.get('jobCode'), '') if item.get('jobCode') else '', F, 8.5, CT); cx += pcw[1]

        for li, ln in enumerate(desc_lines):
            _tx(cv, cx + 3, tty - li * LINE_H, ln, F, 8.5, CT)
        cx += pcw[2]

        dn_txt = _s(item.get('docNo'), '') if item.get('docNo') else ''
        _tx(cv, cx + 3, tty, _trunc(cv, dn_txt, F, 8, pcw[3]-6), F, 8, CT); cx += pcw[3]  # ★ 6→8
        _tx(cv, cx + pcw[4]-3, tty, _fmb(item.get('amount')), F, 8.5, CT, 'right'); cx += pcw[4]  # ★ 6.5→8.5
        _tx(cv, cx + pcw[5]-3, tty, _fmb(item.get('vat')),    F, 8.5, CT, 'right'); cx += pcw[5]  # ★ 6.5→8.5
        _tx(cv, cx + pcw[6]-3, tty, _fmb(item.get('wht')),    F, 8.5, CT, 'right'); cx += pcw[6]  # ★ 6.5→8.5
        _tx(cv, cx + pcw[7]-3, tty, _fmb(item.get('net')),    F, 8.5, CT, 'right')               # ★ 6.5→8.5
        y = ry

    # ── TOTAL ROW ──
    # ★ 7→9, 6.5→8.5, 10→12
    tth = 22; tty = y - tth
    _rc(cv, tx, tty, CW, tth, fi=CBG2, st=CB, sw=0.5)
    _tx(cv, tx + sum(pcw[:4])/2, tty+6, 'รวมทั้งหมด',        FB, 9,   CP, 'center')  # ★ 7→9
    _tx(cv, tx + sum(pcw[:5])-3, tty+6, _fm(ta) if ta else '', FB, 8.5, CP, 'right')  # ★ 6.5→8.5
    _tx(cv, tx + sum(pcw[:6])-3, tty+6, _fm(tv) if tv else '', FB, 8.5, CP, 'right')  # ★ 6.5→8.5
    _tx(cv, tx + sum(pcw[:7])-3, tty+6, _fm(tw) if tw else '', FB, 8.5, CP, 'right')  # ★ 6.5→8.5
    _tx(cv, tx + sum(pcw[:8])-3, tty+6, _fm(tn) if tn else '', FB, 8.5, CG, 'right')  # ★ 6.5→8.5
    y = tty - 10

    # ── Grand total box ──
    _rc(cv, ML + CW*0.45, y-22, CW*0.55, 22, fi=CBG2, st=CB2, sw=0.3, r=4)
    _tx(cv, pw-MR-8, y-14,
        f"จำนวนเงินสุทธิ : {_fm(tn) if tn else '-'} บาท",
        FB, 12, CG, 'right')  # ★ 10→12
    y -= 34

    # ── SIGNATURES (4 ช่อง 2x2) ──
    # ★ 6.5→8.5, 5.5→7.5
    sgw = CW / 2 - 15
    sigs = [
        ('ผู้ขอเบิก',   data.get('requester', '')),
        ('ผู้รับเงิน',  data.get('receiver',  '')),
        ('ฝ่ายบัญชี',  data.get('accounting', '')),
        ('ผู้อนุมัติ',  data.get('approver',  '')),
    ]
    for si, (lbl, name) in enumerate(sigs):
        sx = ML             if si % 2 == 0 else ML + sgw + 30
        sy = y              if si < 2      else y - 52
        _tx(cv, sx, sy, lbl, FB, 8.5, CM)          # ★ 6.5→8.5
        if name:
            _tx(cv, sx+5, sy-12, _s(name, ''), F, 8.5, CT)
        _ln(cv, sx, sy-28, sx+sgw-10, sy-28, CB, 0.5, (2, 2))
        _tx(cv, sx, sy-36, 'ลงชื่อ ...........................  วันที่ ......../........./............', F, 7.5, CL)  # ★ 5.5→7.5

    # ── Footer ──
    _ln(cv, ML, MB+10, pw-MR, MB+10, CB2, 0.3)
    _tx(cv, pw/2, MB+2,
        f"เอกสารขออนุมัติเบิกจ่ายเงินสดย่อย (Petty Cash) — Contract Tracker Pro  |  Generated: {_tbe()}",
        F, 6.5, CL, 'center')  # ★ 4.5→6.5

    cv.save(); buf.seek(0)
    return buf.getvalue()
