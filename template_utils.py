#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
template_utils.py — Shared PDF Template Utilities
══════════════════════════════════════════════════
ใช้ร่วมกันทุกฟอร์ม PDF ที่ overlay บน entity template

Usage:
    from template_utils import merge_on_template, html_to_pdf, build_css, fmt, fmt_date_th

    html = f'<div class="page">...</div>'
    css  = build_css()
    full_html = f'<!DOCTYPE html><html><head><style>{css}</style></head><body>{html}</body></html>'
    final_pdf = merge_on_template(html_to_pdf(full_html), entity_key='SCM Tech')

Functions:
    merge_on_template(content_bytes, entity_key) → PDF bytes ที่ overlay บน template
    html_to_pdf(html_string) → PDF bytes จาก HTML (ใช้ WeasyPrint)
    build_css(fonts=None) → CSS string พร้อม font-face + page layout
    fmt(value) → format ตัวเลข comma + 2 decimal ("1,439,000.00")
    fmt_date_th(date_str) → format วันที่ Thai เต็ม ("28 กุมภาพันธ์ พ.ศ.2568")
    font_b64() → dict ของ font base64 สำหรับ embed ใน CSS
    resolve_template(entity_key) → template filename
"""

import os
import re
import base64
import logging
from functools import lru_cache
from io import BytesIO
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# NUMBER & DATE FORMATTERS
# ══════════════════════════════════════════════════════════════════════

def fmt(v):
    """แปลงตัวเลข → format xxx,xxx.xx (comma + 2 decimal)
    ตัวอย่าง: 1439000 → '1,439,000.00' / 0 → '' / None → ''
    """
    if not v:
        return ''
    try:
        n = float(str(v).replace(',', ''))
        if n == 0:
            return ''
        return f'{n:,.2f}'
    except (ValueError, TypeError):
        return str(v)


_TH_MONTHS = [
    'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
    'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'
]

def fmt_date_th(v):
    """แปลง dd/mm/yyyy (พ.ศ.) → 'd เดือน พ.ศ.yyyy'
    ตัวอย่าง: '28/02/2568' → '28 กุมภาพันธ์ พ.ศ.2568'
    ถ้า format ไม่ตรง → คืนค่าเดิม (ไม่ crash)
    """
    if not v:
        return ''
    s = str(v).strip()
    parts = s.split('/')
    if len(parts) != 3:
        return s  # อาจเป็นแบบเต็มอยู่แล้ว
    try:
        d = int(parts[0])
        m = int(parts[1])
        y = parts[2]
        if m < 1 or m > 12:
            return s
        return f'{d} {_TH_MONTHS[m-1]} พ.ศ.{y}'
    except (ValueError, IndexError):
        return s


# ══════════════════════════════════════════════════════════════════════
# FONT UTILITIES
# ══════════════════════════════════════════════════════════════════════

def font_b64():
    """โหลด THSarabunNew เป็น base64 สำหรับ embed ใน CSS @font-face"""
    base = os.path.dirname(os.path.abspath(__file__))
    result = {}
    for fn in ['THSarabunNew.ttf', 'THSarabunNew-Bold.ttf']:
        p = os.path.join(base, 'fonts', fn)
        if os.path.exists(p):
            with open(p, 'rb') as f:
                result[fn] = base64.b64encode(f.read()).decode()
    return result


# ══════════════════════════════════════════════════════════════════════
# ขนาดตัวอักษรมาตรฐานของทุกฟอร์ม — "TH Sarabun New 14" แบบเดียวกับใน Word
# ══════════════════════════════════════════════════════════════════════
# ไฟล์ fonts/THSarabunNew*.ttf ของบริการนี้เป็น TH Sarabun New ที่ตัวอักษร "ใหญ่กว่า" ฟอนต์ต้นฉบับที่ขนาด pt เดียวกัน:
#   ความสูงตัวพิมพ์ใหญ่ (H) 0.728 em  เทียบกับ 0.476 em ของ TH Sarabun New v1.35 / TH SarabunPSK ที่ Word ใช้
#   → ตัวอักษรใหญ่กว่า 1.53 เท่า (วัดซ้ำด้วยความกว้างบรรทัดจริงแล้วตรงกัน)
# ดังนั้น "10pt" ในโค้ดเดิม = 15.3pt ใน Word และแต่ละฟอร์มเคยใช้ขนาดจริงต่างกันตั้งแต่ 9 ถึง 24pt
# ทุกฟอร์มจึงต้องกำหนดขนาดผ่าน th_pt() — ใส่ขนาดแบบที่เห็นใน Word แล้วได้ค่า pt ของไฟล์ฟอนต์นี้
FONT_SCALE = 0.728 / 0.476


def th_pt(word_pt):
    """ขนาดตัวอักษรแบบ Word (เช่น 14) → ค่า pt ที่ต้องใช้กับไฟล์ฟอนต์ของบริการนี้"""
    return round(word_pt / FONT_SCALE, 2)


BODY_PT  = th_pt(14)    # เนื้อหา ป้าย ช่องกรอก ตาราง — ทุกฟอร์ม
TITLE_PT = th_pt(16)    # ชื่อเอกสาร (ตัวหนา)
SMALL_PT = th_pt(8)     # ข้อความขอบกระดาษ: เลขที่/เลขหน้า, ข้อความท้ายฟอร์ม (ผู้ใช้กำหนด 8 เมื่อ 2026-10-06)
LINE_PT  = 18           # ระยะบรรทัดของหนังสือ (pt จริง) ≈ ระยะบรรทัดเดี่ยวของ TH Sarabun New 14 ใน Word (18.6)
LINE_H   = round(LINE_PT / BODY_PT, 3)   # ค่า line-height ของ CSS

_FONT_FACE_CACHE = {}


def font_face_css():
    """@font-face ของ THSarabunNew (ฝัง base64) — ใช้ร่วมกันทุกฟอร์มที่สร้างจาก HTML"""
    if 'css' not in _FONT_FACE_CACHE:
        fonts = font_b64()
        css = ''
        for weight, fn in (('normal', 'THSarabunNew.ttf'), ('bold', 'THSarabunNew-Bold.ttf')):
            if fonts.get(fn):
                css += ("@font-face { font-family: 'THSarabunNew'; font-weight: %s; "
                        "src: url('data:font/truetype;base64,%s') format('truetype'); }\n" % (weight, fonts[fn]))
        _FONT_FACE_CACHE['css'] = css
    return _FONT_FACE_CACHE['css']


def checkbox_svg(checked, mark='tick', size_mm=3.6):
    """ช่องตัวเลือกแบบ SVG (ไม่ขึ้นกับฟอนต์สำรองของเครื่อง — THSarabunNew ไม่มีอักขระ ☐ ☒ ✓)
    mark: 'tick' = ✓ , 'cross' = ✕"""
    if not checked:
        m = ''
    elif mark == 'cross':
        m = '<path d="M3 3 L9 9 M9 3 L3 9" stroke="#000" stroke-width="1.5" stroke-linecap="round"/>'
    else:
        m = '<path d="M2.6 6.3 L5 8.8 L9.5 3.2" fill="none" stroke="#000" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
    return ('<svg class="cbx" viewBox="0 0 12 12" width="%smm" height="%smm" xmlns="http://www.w3.org/2000/svg">'
            '<rect x="0.7" y="0.7" width="10.6" height="10.6" fill="#fff" stroke="#000" stroke-width="1.1"/>%s</svg>'
            % (size_mm, size_mm, m))


# ══════════════════════════════════════════════════════════════════════
# รอยต่อคำภาษาไทย — ใช้ทั้งการจัดชิดขอบสองด้าน (HTML) และการตัดบรรทัดในช่องตาราง (ReportLab)
# ══════════════════════════════════════════════════════════════════════

def _is_thai(ch):
    return '฀' <= ch <= '๿'


@lru_cache(maxsize=4096)
def thai_breaks(text):
    """ตำแหน่ง (index) ที่ขึ้นบรรทัดใหม่ได้ตามตัวตัดคำของ Pango/libthai — ชุดเดียวกับที่ WeasyPrint ใช้ตัดบรรทัด
    คืน frozenset ; ใช้ไม่ได้ (ไม่มี WeasyPrint / ฟังก์ชันภายในเปลี่ยน) → None แล้วผู้เรียกใช้วิธีสำรอง"""
    try:
        from weasyprint.text.line_break import get_log_attrs
        attrs = get_log_attrs(text, 'th')
        if isinstance(attrs, tuple):          # WeasyPrint รุ่นเก่าคืน (bytestring, log_attrs)
            attrs = attrs[-1]
        return frozenset(i for i in range(1, len(text)) if attrs[i].is_line_break)
    except Exception as e:                    # pragma: no cover - ขึ้นกับสภาพแวดล้อม
        logger.warning(f'thai_breaks ใช้ไม่ได้ ({type(e).__name__}: {e}) — ใช้วิธีสำรอง')
        return None


# ── จัดชิดขอบสองด้าน (กระจายแบบไทย) ──
# WeasyPrint กระจายช่องไฟได้เฉพาะที่อักขระช่องว่าง (U+0020 / U+00A0) — ข้อความไทยมีช่องว่างบรรทัดละ 0–3 จุด
# text-align: justify เฉย ๆ จึงได้ช่องโหว่กว้างตรงช่องว่าง และบรรทัดที่ไม่มีช่องว่างไม่ถูกจัดเลย
# วิธีที่ใช้: แทรกช่องว่าง "กว้างศูนย์" (word-spacing ติดลบเท่าความกว้างช่องว่างของฟอนต์พอดี) ระหว่างตัวอักษรไทย
#   • ที่รอยต่อคำ (thai_breaks)  → U+0020 : ขึ้นบรรทัดใหม่ได้ + เป็นจุดกระจาย
#   • ภายในคำ                  → U+00A0 : ขึ้นบรรทัดใหม่ไม่ได้ + เป็นจุดกระจาย
#   → บรรทัดชิดขอบขวาเสมอกัน ช่องไฟเพิ่มกระจายเท่ากันทั้งบรรทัด (แบบ "กระจายแบบไทย" ของ Word) และไม่ตัดกลางคำ
#   ไม่แทรกหน้าสระ/วรรณยุกต์ที่ซ้อนบน-ล่าง และหน้า "ำ" (นิคหิตของ ำ ต้องเกาะพยัญชนะตัวหน้า)
# ช่องว่างจริงในข้อความอยู่ใน <span class="sp"> ซึ่งคืน word-spacing ปกติ จึงกว้างเท่าเดิม
# ผลข้างเคียง: ข้อความที่คัดลอกจาก PDF มีช่องว่างแทรกระหว่างตัวอักษรไทย
#   (ชั้นข้อความของเอกสารที่ซ้อนหัวกระดาษอ่านไม่ได้อยู่ก่อนแล้ว — "า" ถูกอ่านเป็น "ำ" จากไฟล์ฟอนต์นี้ และหลังซ้อนหัวกระดาษตัวอ่านข้อความคืนเฉพาะข้อความของหัวกระดาษ)
JUSTIFY = 'letter'                              # 'letter' = กระจายระหว่างตัวอักษร ; 'word' = เฉพาะรอยต่อคำ ; '' = ชิดซ้าย
_SPACE_EM      = 675 / 2048                     # ความกว้างช่องว่าง / NBSP ของ THSarabunNew.ttf
_SPACE_EM_BOLD = 706 / 2048                     # ของ THSarabunNew-Bold.ttf
_TOKEN_RE = re.compile(r'(<[^>]+>|&[#\w]+;)')
_TH_ZERO_WIDTH = frozenset('ัิีึืฺุู็่้๊๋์ํ๎')


def justify_css(selectors):
    """CSS ของบล็อกที่จัดชิดขอบสองด้าน — selectors เช่น '.para' หรือ 'p, .cl, .sub'"""
    if not JUSTIFY:
        return '.nw { white-space: nowrap; }'
    sel = [x.strip() for x in selectors.split(',')]
    join = lambda suffix: ', '.join(x + suffix for x in sel)
    return ('%s { text-align: justify; word-spacing: -%.5fem; }\n'
            '    %s { word-spacing: -%.5fem; }\n'
            '    %s { word-spacing: 0; }\n'
            '    .nw { white-space: nowrap; }'
            % (join(''), _SPACE_EM, join(' b') + ', ' + join(' strong'), _SPACE_EM_BOLD, join(' .sp')))


def _justify_chunk(text, breakable=True):
    """ข้อความล้วน (escape แล้ว ไม่มีแท็ก) → แทรกจุดกระจายระหว่างตัวอักษรไทย + ห่อช่องว่างจริง
    breakable=False (ข้อความใน .nw) → ไม่มีจุดขึ้นบรรทัดใหม่"""
    has_thai = any(_is_thai(c) for c in text)
    bp = (thai_breaks(text) if breakable else frozenset()) if has_thai else frozenset()
    if bp is None:
        return None
    letter = JUSTIFY == 'letter'
    out = []
    for i, ch in enumerate(text):
        if i and _is_thai(text[i - 1]) and _is_thai(ch) and ch not in _TH_ZERO_WIDTH and ch != 'ำ':
            if i in bp:
                out.append(' ')
            elif letter:
                out.append(' ')
        out.append('<span class="sp"> </span>' if ch in ' \n\t' else ch)
    return ''.join(out)


def justify_html(html):
    """HTML ของย่อหน้า (ข้อความ escape แล้ว + แท็ก inline) → เตรียมสำหรับบล็อกที่ใช้ justify_css
    ข้อความใน <span class="nw">…</span> (ชื่อ/ที่อยู่ที่ห้ามตัดกลางคำ) ร่วมกระจายช่องไฟแต่ไม่มีจุดขึ้นบรรทัดใหม่
    ตัวตัดคำใช้ไม่ได้ → คืน HTML เดิม (ได้ผลแบบ justify ธรรมดา)"""
    if not JUSTIFY or not html:
        return html
    out, keep = [], 0
    for part in _TOKEN_RE.split(str(html)):
        if not part:
            continue
        if part.startswith('<'):
            if part.startswith('<span class="nw"'):
                keep += 1
            elif part == '</span>' and keep:
                keep -= 1
            out.append(part)
        elif part.startswith('&') and part.endswith(';'):
            out.append(part)
        else:
            j = _justify_chunk(part, breakable=not keep)
            if j is None:
                return html
            out.append(j)
    return ''.join(out)


def nowrap_tokens(text, escape=True):
    """ชื่อบริษัท / ชื่อบุคคล / ที่อยู่ — ขึ้นบรรทัดใหม่ได้เฉพาะตรงช่องว่าง ไม่ตัดกลางชื่อ (เช่น "เทคโน | โลจีส์", "เขตบาง | รัก")
    คำที่ยาวผิดปกติ (เกิน 40 ตัวอักษรไม่มีช่องว่าง) ปล่อยให้ตัดตามรอยต่อคำ กันล้นขอบ"""
    esc = (lambda t: (t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;'))) if escape else (lambda t: t)
    return ' '.join(('<span class="nw">%s</span>' % esc(t)) if len(t) <= 40 else esc(t) for t in str(text or '').split())


# ── ตัดบรรทัดสำหรับฟอร์มที่วาดด้วย ReportLab (ไม่มีตัวตัดคำภาษาไทย) ──
_TH_NO_START = set('ะัาำิีึืฺุู็่้๊๋์ํๅๆฯ')   # สระ/วรรณยุกต์ที่ต้องเกาะตัวอักษรข้างหน้า — ห้ามขึ้นต้นบรรทัด
_TH_NO_END   = set('เแโใไั')                  # สระนำ และไม้หันอากาศ (ต้องมีตัวสะกดตาม) — ห้ามอยู่ท้ายบรรทัด
_TH_TONES    = set('่้๊๋')


def wrap_text(width_of, text, max_w, max_lines=2):
    """ตัดข้อความเป็นไม่เกิน max_lines บรรทัด — width_of(ข้อความ) คืนความกว้างเป็น pt
    ตัดที่ช่องว่างหรือรอยต่อคำไทย (thai_breaks) ที่อยู่ท้ายสุดซึ่งยังพอดีบรรทัด
    ไม่มีรอยต่อคำในช่วงที่พอดี (คำเดียวยาวกว่าช่อง / ตัวตัดคำใช้ไม่ได้) → ตัดระหว่างตัวอักษรโดยไม่แยกสระ/วรรณยุกต์ออกจากพยัญชนะ
    บรรทัดสุดท้ายลงท้ายด้วย '…' ถ้าข้อความยังเหลือ"""
    t = ' '.join(str(text or '').split())
    if not t:
        return ['']
    lines = []
    while t and len(lines) < max_lines:
        if width_of(t) <= max_w:
            lines.append(t)
            break
        last = len(lines) == max_lines - 1
        suffix = '…' if last else ''
        lo, hi = 1, len(t) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if width_of(t[:mid] + suffix) <= max_w:
                lo = mid
            else:
                hi = mid - 1
        cut = lo
        words = thai_breaks(t) or frozenset()
        best = max([i for i in words if i <= cut] + [t.rfind(' ', 0, cut + 1)])
        if best > cut * 0.4:
            cut = best
        else:
            while cut > 1 and (t[cut] in _TH_NO_START or t[cut - 1] in _TH_NO_END
                               or (t[cut - 1] in _TH_TONES and t[cut - 2] == 'ั')):
                cut -= 1
        lines.append(t[:cut].rstrip() + suffix)
        t = t[cut:].lstrip()
    return lines or ['']


def css_str(s):
    """ข้อความสำหรับใส่ใน content: "…" ของ CSS"""
    return (str('' if s is None else s).replace('\\', '\\\\').replace('"', '\\"')
            .replace('\n', ' ').replace('\r', ' '))


def page_head_css(doc_number=''):
    """ค่า content ของหัวกระดาษ: เลขที่ … · หน้า x / y"""
    num = css_str(doc_number).strip()
    return ('"เลขที่ %s    ·    หน้า " counter(page) " / " counter(pages)' % num) if num \
        else '"หน้า " counter(page) " / " counter(pages)'


# ══════════════════════════════════════════════════════════════════════
# CSS BUILDER
# ══════════════════════════════════════════════════════════════════════

def build_css(fonts=None, doc_number=''):
    """CSS ของหนังสือ (หนังสือทั่วไป / ขอถอนหลักประกัน / มอบอำนาจ) — TH Sarabun New 14

    ใช้ขอบกระดาษจริง (@page margin) — เนื้อหายาวเกินหน้าขึ้นหน้าใหม่ได้ และหน้า 2 เป็นต้นไปมี
    "เลขที่ … · หน้า x / y" ที่ขอบบน (เดิมใช้กล่อง .page สูง 297mm + padding: ข้อความที่เกินหน้าแรกหาย)

    class ที่ฟอร์มใช้ร่วมกัน:
        .doc-number    — เลขที่หนังสือ (บนซ้าย)
        .title         — ชื่อหนังสือ (กลาง, bold)
        .written-at    — ทำที่/วันที่ (ขวา)
        .subject-line  — เรื่อง/เรียน (flex)
        .para          — เนื้อหา (indent)
        .closing-area  — ขอแสดงความนับถือ (ขวา)
        .sig-block     — ลายเซ็น (กลาง)
        .sig-col       — ลายเซ็นแบบ column (มอบอำนาจ)
        .sig-right     — ลายเซ็นแต่ละบรรทัด
        .keep-tail     — ย่อหน้าสุดท้าย + ลายเซ็น อยู่หน้าเดียวกัน
    """
    return f"""
    {font_face_css()}
    @page {{
        size: A4;
        margin: 32mm 20mm 25mm 25mm;
        @top-left {{
            content: {page_head_css(doc_number)};
            font-family: 'THSarabunNew', 'TH Sarabun New', serif; font-size: {SMALL_PT}pt; color: #333;
            white-space: pre; vertical-align: bottom; padding-bottom: 4mm;
        }}
    }}
    @page :first {{ @top-left {{ content: none; }} }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
        font-family: 'THSarabunNew', 'TH Sarabun New', serif;
        font-size: {BODY_PT}pt;
        line-height: {LINE_H};
        color: #000;
        background: transparent;
    }}
    /* ── หัวหนังสือ ── */
    .doc-number  {{ margin-bottom: 5mm; }}
    .title       {{ font-size: {TITLE_PT}pt; font-weight: bold; text-align: center; margin-bottom: 7mm; }}
    .written-at  {{ text-align: right; margin-bottom: 5mm; }}
    /* ── เรื่อง/เรียน ── */
    .subject-line  {{ display: flex; margin-bottom: 2.5mm; }}
    .subject-label {{ font-weight: bold; min-width: 18mm; flex-shrink: 0; }}
    .subject-value {{ flex: 1; }}
    /* ── ย่อหน้า ── */
    .para {{
        text-align: left;
        text-indent: 12mm;
        margin-bottom: 3mm;
        orphans: 2; widows: 2;
    }}
    .subject-line + .para {{ margin-top: 4mm; }}
    {justify_css('.para')}
    .keep-tail {{ page-break-inside: avoid; }}
    /* ── ลายเซ็น (ขอถอน — ขวา) ── */
    .closing-area {{
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        margin-top: 8mm;
        page-break-inside: avoid;
    }}
    .sig-closing {{ page-break-inside: avoid; }}
    .closing     {{ margin-bottom: 4mm; text-align: center; width: 75mm; }}
    .sig-block   {{ text-align: center; width: 75mm; }}
    .sig-space   {{ height: 18mm; }}
    .sig-line    {{
        border-top: 0.5pt solid #000;
        width: 75mm;
        margin: 0 auto 0.5mm auto;
        padding-top: 1.5mm;
    }}
    .sig-name    {{ margin-bottom: 0; }}
    /* ── ลายเซ็น (มอบอำนาจ — column ขวา) ── */
    table.poa-sign {{ width: 100%; border-collapse: collapse; margin-top: 6mm; page-break-inside: avoid; }}
    table.poa-sign td {{ vertical-align: bottom; padding: 0; }}
    .sig-col {{ width: 100%; }}
    .sig-right {{
        margin-bottom: 4mm;
        width: 100%;
    }}
    .sig-right .sig-space {{ height: 10mm; }}
    .sig-right .sig-row1 {{
        display: flex;
        align-items: flex-end;
        width: 100%;
    }}
    .sig-right .sig-row1 .prefix {{
        white-space: nowrap;
        flex-shrink: 0;
        padding-right: 1mm;
        line-height: 1.2;
    }}
    .sig-right .sig-row1 .line-cell {{
        flex: 1;
        border-bottom: 0.5pt solid #000;
        height: 5mm;
        min-width: 0;
    }}
    .sig-right .sig-row1 .lbl {{
        white-space: nowrap;
        flex-shrink: 0;
        flex-basis: 24mm;
        width: 24mm;
        text-align: left;
        padding-left: 1.5mm;
        line-height: 1.2;
    }}
    .sig-right .sig-name {{
        margin-top: 1.5mm;
        text-align: center;
        padding-left: 11mm;
        padding-right: 24mm;
    }}
    /* ── อื่นๆ ── */
    .stamp  {{ color: #555; }}
    .clearfix {{ clear: both; }}
    """


# ══════════════════════════════════════════════════════════════════════
# HTML → PDF (WeasyPrint)
# ══════════════════════════════════════════════════════════════════════

def html_to_pdf(html):
    """แปลง HTML string → PDF bytes ด้วย WeasyPrint"""
    from weasyprint import HTML
    return HTML(string=html).write_pdf()


def build_html(css, body_html):
    """สร้าง full HTML document จาก CSS + body content
    ตัวอย่าง:
        css = build_css()
        body = '<div class="page"><div class="title">ทดสอบ</div></div>'
        html = build_html(css, body)
        pdf  = html_to_pdf(html)
    """
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{css}</style></head>
<body>{body_html}</body></html>"""


# ══════════════════════════════════════════════════════════════════════
# ENTITY TEMPLATE MAPPING
# ══════════════════════════════════════════════════════════════════════

# แต่ละ entity มี template PDF แยก (logo + watermark + header/footer)
# ชื่อไฟล์: bg_template_{key}.pdf — วางที่ root ของ repo
# Fallback: bg_template.pdf (SCM Tech เดิม)

_ENTITY_TEMPLATE_MAP = {
    # SCM Technologies (หลัก)
    'scm tech':     'bg_template_scmtech.pdf',
    'scmtech':      'bg_template_scmtech.pdf',
    'scm t':        'bg_template_scmtech.pdf',
    # SCM S
    'scm s':        'bg_template_scms.pdf',
    'scms':         'bg_template_scms.pdf',
    # SCM C
    'scm c':        'bg_template_scmc.pdf',
    'scmc':         'bg_template_scmc.pdf',
    # SCM Cyber
    'cyber':        'bg_template_cyber.pdf',
    'scm cyber':    'bg_template_cyber.pdf',
    # SCM Business Connect
    'bc':           'bg_template_bc.pdf',
    'scm bc':       'bg_template_bc.pdf',
    'business connect': 'bg_template_bc.pdf',
    'scm business connect': 'bg_template_bc.pdf',
    # SCM B2B
    'b2b':          'bg_template_b2b.pdf',
    'scm b2b':      'bg_template_b2b.pdf',
    # SCM Group / Holding
    'group':        'bg_template_group.pdf',
    'scm group':    'bg_template_group.pdf',
    'holding':      'bg_template_group.pdf',
    'scm holding':  'bg_template_group.pdf',
    # Fahcloud — ใช้ SCM Tech เป็น fallback (ยังไม่มี template เฉพาะ)
    'fahcloud':     'bg_template_scmtech.pdf',
}

_DEFAULT_TEMPLATE = 'bg_template.pdf'


def resolve_template(entity_key):
    """แปลง entity key → template filename
    รองรับ: 'SCM Tech', 'scmtech', 'SCM C', 'cyber' ฯลฯ (case-insensitive)
    Fallback: bg_template.pdf
    """
    key = str(entity_key or '').lower().strip()
    return _ENTITY_TEMPLATE_MAP.get(key, _DEFAULT_TEMPLATE)


def merge_on_template(content_bytes, entity_key=''):
    """ซ้อนเนื้อหา "ทุกหน้า" บนหัวกระดาษของบริษัท (logo + watermark + แถบที่อยู่)

    Args:
        content_bytes: PDF bytes ที่ WeasyPrint สร้าง (เนื้อหาหนังสือ)
        entity_key: sheet name หรือ entity key (เช่น 'SCM Tech', 'SCM C')

    Returns:
        PDF bytes ที่ merge แล้ว — จำนวนหน้าเท่ากับเนื้อหา

    เดิมซ้อนเฉพาะหน้าแรกของเนื้อหา: หนังสือที่ยาวเกิน 1 หน้าจึงถูกตัดส่วนที่เหลือ (รวมลายเซ็น) ทิ้ง

    ชื่อฟอนต์ THSarabunNew ของ "เนื้อหา" ถูกเปลี่ยนเป็น THSarabunNewCTN ก่อนซ้อน — template ฝังฟอนต์ชื่อเดียวกัน
    แบบ subset ถ้าชื่อชนกันตัวอักษรอาจเพี้ยน

    Fallback: ถ้า template ไม่พบ → ใช้ bg_template.pdf เดิม ; ไม่มีเลย → คืนเนื้อหาเดิม
    """
    from pypdf.generic import NameObject

    base     = os.path.dirname(os.path.abspath(__file__))
    tpl_name = resolve_template(entity_key)
    tpl_path = os.path.join(base, tpl_name)

    # fallback ถ้าไฟล์ไม่พบ
    if not os.path.exists(tpl_path):
        logger.warning(f'Template ไม่พบ: {tpl_path} → ใช้ default')
        tpl_path = os.path.join(base, _DEFAULT_TEMPLATE)

    if not os.path.exists(tpl_path):
        logger.error(f'Default template ไม่พบ: {tpl_path}')
        return content_bytes  # คืน content เดิมไม่มี template

    def rename(obj, key):
        val = str(obj.get(key, ''))
        if 'THSarabunNew' in val and 'CTN' not in val:
            obj[NameObject(key)] = NameObject('/' + val.replace('THSarabunNew', 'THSarabunNewCTN').lstrip('/'))

    writer = PdfWriter()
    for page in PdfReader(BytesIO(content_bytes)).pages:
        bg = PdfReader(tpl_path).pages[0]
        content_fonts = page.get('/Resources', {}).get('/Font', {})
        for key in list(content_fonts.keys()):
            try:
                font_obj = content_fonts[key].get_object()
                rename(font_obj, '/BaseFont')
                for desc_ref in font_obj.get('/DescendantFonts', []):
                    desc = desc_ref.get_object()
                    rename(desc, '/BaseFont')
                    if '/FontDescriptor' in desc:
                        rename(desc['/FontDescriptor'].get_object(), '/FontName')
                if '/FontDescriptor' in font_obj:
                    rename(font_obj['/FontDescriptor'].get_object(), '/FontName')
            except Exception:
                pass
        bg.merge_page(page)
        writer.add_page(bg)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()


# ══════════════════════════════════════════════════════════════════════
# HELPER: สร้าง signature HTML
# ══════════════════════════════════════════════════════════════════════

def sig_closing(signer_name, signer_position='Corporate Lawyers'):
    """สร้าง HTML ลายเซ็นแบบ 'ขอแสดงความนับถือ' (หนังสือขอถอน)"""
    return f"""<div class="closing-area">
    <div class="closing">ขอแสดงความนับถือ</div>
    <div class="sig-block">
      <div class="sig-space"></div>
      <div class="sig-line"></div>
      <div class="sig-name">({signer_name})</div>
      <div class="sig-pos">{signer_position}</div>
    </div>
  </div>"""


def sig_poa_line(label, name):
    """สร้าง HTML ลายเซ็นแบบ 'ลงชื่อ...ผู้มอบอำนาจ' (หนังสือมอบอำนาจ)"""
    return f"""<div class="sig-right">
      <div class="sig-space"></div>
      <div class="sig-row1">
        <span class="prefix">ลงชื่อ</span>
        <span class="line-cell"></span>
        <span class="lbl">{label}</span>
      </div>
      <div class="sig-name">({name if str(name or '').strip() else '&nbsp;' * 44})</div>
    </div>"""
