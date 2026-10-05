#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: v4-multipage
"""
generate_general_letter.py — หนังสือทั่วไป (General Letter)
═══════════════════════════════════════════════════════════
ใช้ template_utils shared module (WeasyPrint + entity template overlay)
Layout อิงจาก หนังสือขอถอนหลักประกัน (BG Withdraw)

★ v2 (22/04/69) — Digital Signature + Stamp:
  - เพิ่ม params: signatureKey, stampKey
  - ใช้ build_sig_closing_with_image() แทน sig_closing()

★ v3 (24/04/69) [S41] — Defense-in-Depth Field Aliases:
  รับ field ได้ทั้งชื่อเก่าและชื่อใหม่จาก GAS:
    title              ← title | subject | letterSubject  (fallback 3 ชั้น)
    recipientName      ← recipientName | letterRecipient | recipient
    bodyParagraphs     ← bodyParagraphs | letterBody | body
    signatureKey       ← signatureKey  (ถ้า useSignature=true → 'pitichai')
    stampKey           ← stampKey | stampType
  ถ้า GAS ยังไม่ได้ map → ฝั่ง Python ก็ยัง handle ได้ (defense)

POST /generate_general_letter
  Input (เลือกได้ตามชุดไหน):
    entityKey, docNumber, docDate, writtenAt,
    title | subject | letterSubject,
    subject,
    recipientName | letterRecipient | recipient,
    bodyParagraphs | letterBody | body,
    references | letterReferences,           — "อ้างถึง": list หรือข้อความหลายบรรทัด
    signerName, signerPosition,
    signatureKey,                            — string key ของลายเซ็น
    useSignature (bool) → signatureKey='pitichai' (ถ้าเดินเข้ามา),
    stampKey | stampType,
  Output: { success, pdfBase64, fileName, features }

★ เนื้อหาเยอะ → ลายเซ็นเลื่อนลงตาม (WeasyPrint จัดให้อัตโนมัติ)
★ overlay บน entity template (logo + watermark ตามบริษัท)

★ v4 (2026-10) — หนังสือยาวเกิน 1 หน้า:
  เดิมซ้อนหัวกระดาษเฉพาะหน้าแรกของเนื้อหา → ส่วนที่เกินหน้า 1 (รวมคำลงท้าย/ลายเซ็น) หายจาก PDF
  และข้อความท้ายหน้าทับแถบที่อยู่ของหัวกระดาษ
  ตอนนี้ถ้าเนื้อหาเกิน 1 หน้า จะจัดหน้าใหม่ด้วยขอบกระดาษจริง แล้วซ้อนหัวกระดาษทุกหน้า
  (หนังสือหน้าเดียวใช้ทางเดิมทุกประการ)
"""

import base64
import logging
from datetime import datetime
from flask import request, jsonify
from template_utils import (
    merge_on_template, html_to_pdf, build_css, build_html,
    fmt, fmt_date_th, sig_closing
)

# ★ v2 — import signature/stamp helper
from signature_stamp import (
    build_sig_closing_with_image,
    validate_signature_key,
    validate_stamp_key,
)

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# ENTITY DEFAULTS
# ══════════════════════════════════════════════════════════════════════
_ENTITY_NAME_MAP = {
    'scm t':    'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด',
    'scmtech':  'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด',
    'scm s':    'บริษัท เอส ซี เอ็ม เอส เทคโนโลจีส์ จำกัด',
    'scms':     'บริษัท เอส ซี เอ็ม เอส เทคโนโลจีส์ จำกัด',
    'scm c':    'บริษัท เอส ซี เอ็ม ซี เทคโนโลจีส์ จำกัด',
    'scmc':     'บริษัท เอส ซี เอ็ม ซี เทคโนโลจีส์ จำกัด',
    'cyber':    'บริษัท เอส ซี เอ็ม ไซเบอร์ จำกัด',
    'bc':       'บริษัท เอส ซี เอ็ม บิสิเนส คอนเนค จำกัด',
    'b2b':      'บริษัท เอส ซี เอ็ม บีทูบี จำกัด',
    'holding':  'บริษัท เอส ซี เอ็ม โฮลดิ้ง จำกัด',
    'fahcloud': 'บริษัท ฟาห์คลาวด์ จำกัด',
}

_DEFAULT_ENTITY_NAME = 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด'


def _resolve_entity_name(entity_key):
    """แปลง entity key → ชื่อบริษัทภาษาไทย"""
    key = str(entity_key or '').lower().strip()
    return _ENTITY_NAME_MAP.get(key, _DEFAULT_ENTITY_NAME)


def _today_th():
    """วันที่ปัจจุบัน format Thai เต็ม"""
    now = datetime.now()
    months = [
        'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
        'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'
    ]
    return f'{now.day} {months[now.month - 1]} พ.ศ.{now.year + 543}'


def _esc(s):
    """Escape HTML"""
    return (str(s or '')
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


# ══════════════════════════════════════════════════════════════════════
# [S41 v3] HELPER — Pick first non-empty value from multiple aliases
# ══════════════════════════════════════════════════════════════════════

def _pick(data, *keys):
    """
    คืนค่าแรกที่ไม่ว่างจาก keys ที่ระบุ (Defense-in-Depth)

    Example:
        recipient = _pick(data, 'recipientName', 'letterRecipient', 'recipient')
        → คืนค่าแรกที่ข้อมูลไม่ว่าง หรือ '' ถ้าทั้งหมดว่าง
    """
    for k in keys:
        v = data.get(k)
        if v is not None and str(v).strip():
            return v
    return ''


# ══════════════════════════════════════════════════════════════════════
# "อ้างถึง" — เดิม GAS ส่ง references มาแต่ไม่ถูกพิมพ์ใน PDF
# ══════════════════════════════════════════════════════════════════════

# ความสามารถที่ route นี้รองรับ — ส่งกลับใน response ให้ GAS รู้ว่าบริการรุ่นนี้พิมพ์ "อ้างถึง" ได้
# และหนังสือยาวหลายหน้าได้ ('multipage')
FEATURES = ['references', 'multipage']


def _paged_css(doc_number):
    """CSS เพิ่มสำหรับหนังสือที่ยาวเกิน 1 หน้า — ใช้ขอบกระดาษจริงแทน padding ของ .page
    (padding มีผลเฉพาะต้น/ท้ายกล่อง หน้า 2 จึงเริ่มชิดขอบบนและหน้าแรกล้นทับแถบที่อยู่)
    พื้นที่เนื้อหาของหน้าแรกเท่าเดิมทุกประการ ; หน้า 2 เป็นต้นไปมี "เลขที่ … · หน้า x / y" ที่ขอบบน"""
    num = str(doc_number or '').replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', ' ').strip()
    head = ('"เลขที่ %s    ·    หน้า " counter(page) " / " counter(pages)' % num) if num \
        else '"หน้า " counter(page) " / " counter(pages)'
    return """
    @page {
        size: A4;
        margin: 32mm 20mm 25mm 25mm;
        @top-left {
            content: %s;
            font-family: 'THSarabunNew', 'TH Sarabun New', serif; font-size: 10pt; color: #333;
            white-space: pre; vertical-align: bottom; padding-bottom: 4mm;
        }
    }
    @page :first { @top-left { content: none; } }
    .page { width: auto; min-height: 0; padding: 0; }
    .para { orphans: 2; widows: 2; }
    .closing-area, .sig-closing { page-break-inside: avoid; }
    .keep-tail { page-break-inside: avoid; }   /* ย่อหน้าสุดท้าย + คำลงท้าย/ลายเซ็น อยู่หน้าเดียวกัน */
    """ % head


def _references(data):
    """รายการอ้างถึง: list หรือข้อความหลายบรรทัด → list ของข้อความที่ไม่ว่าง (สูงสุด 20)"""
    raw = data.get('references')
    if raw is None or raw == '':
        raw = data.get('letterReferences') or []
    if isinstance(raw, str):
        raw = raw.splitlines()
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(r).strip() for r in raw if r is not None and str(r).strip()][:20]


def _references_html(refs):
    """บรรทัด "อ้างถึง" ใต้ "เรียน" — รายการเดียวไม่ใส่เลขลำดับ"""
    if not refs:
        return ''
    if len(refs) == 1:
        value = _esc(refs[0])
    else:
        value = '<br>'.join(f'{i}. {_esc(r)}' for i, r in enumerate(refs, 1))
    return ('<div class="subject-line"><span class="subject-label">อ้างถึง</span>'
            f'<span class="subject-value">{value}</span></div>')


# ══════════════════════════════════════════════════════════════════════
# BUILD HTML — layout เหมือนหนังสือขอถอน BG
# ══════════════════════════════════════════════════════════════════════

def _build_general_letter_html(data, paged=False):
    """สร้าง HTML หนังสือทั่วไป — ใช้ class จาก build_css() ของ template_utils
    paged=True → จัดหน้าแบบหลายหน้า (ดู _paged_css)"""

    entity_key = str(data.get('entityKey', '') or '')
    entity_name = _pick(data, 'writtenAt') or _resolve_entity_name(entity_key)

    # ─────────────────────────────────────────────────────────────────
    # [S41 v3] Defense-in-Depth: รับ field ได้ทั้งชื่อเก่าและใหม่
    # ─────────────────────────────────────────────────────────────────

    # title: กลางเอกสาร (bold ใหญ่)
    title = _pick(data, 'title', 'subject', 'letterSubject') or 'หนังสือทั่วไป'
    title = _esc(title)

    # doc_number / doc_date: เหมือนเดิม
    doc_number = _esc(data.get('docNumber', ''))
    doc_date = _esc(data.get('docDate', '') or _today_th())

    # subject: "เรื่อง"
    subject = _esc(_pick(data, 'subject', 'letterSubject'))

    # recipientName: "เรียน" — รับได้ 3 ชื่อ
    recipient = _esc(_pick(data, 'recipientName', 'letterRecipient', 'recipient'))

    # references: "อ้างถึง" — รับ list หรือข้อความหลายบรรทัด (GAS ส่ง list)
    refs = _references(data)

    # signerName / signerPosition
    signer_name = _pick(data, 'signerName', 'companySignerName', 'signer1')
    signer_pos = data.get('signerPosition', '') or 'Corporate Lawyers'

    # ─────────────────────────────────────────────────────────────────
    # [S41 v3] signature_key: รองรับทั้ง signatureKey โดยตรง
    #          + convert useSignature (bool) → signatureKey='pitichai'
    # ─────────────────────────────────────────────────────────────────
    sig_key = str(data.get('signatureKey', '') or '').strip() or None

    # ★ ถ้าไม่มี signatureKey แต่มี useSignature=True → default pitichai
    if not sig_key:
        use_sig_raw = data.get('useSignature')
        # รับหลายรูปแบบ: True, 'true', 'TRUE', 1
        is_use_sig = (
            use_sig_raw is True
            or str(use_sig_raw).lower() == 'true'
            or use_sig_raw == 1
        )
        if is_use_sig:
            sig_key = 'pitichai'
            logger.info('[S41] useSignature=true → signatureKey=pitichai (default)')

    # ─────────────────────────────────────────────────────────────────
    # [S41 v3] stamp_key: รับได้ทั้ง stampKey และ stampType
    # ─────────────────────────────────────────────────────────────────
    stamp_key = str(_pick(data, 'stampKey', 'stampType')).strip() or None

    # Validate — ถ้า key ผิด → log warning แต่ไม่ fail (fallback = ไม่ใส่)
    sig_ok, sig_err = validate_signature_key(sig_key)
    if not sig_ok:
        logger.warning(f'general_letter signature_key error: {sig_err}')
        sig_key = None
    stamp_ok, stamp_err = validate_stamp_key(stamp_key)
    if not stamp_ok:
        logger.warning(f'general_letter stamp_key error: {stamp_err}')
        stamp_key = None

    # ─────────────────────────────────────────────────────────────────
    # [S41 v3] body: รับได้ 3 ชื่อ — bodyParagraphs / letterBody / body
    # ─────────────────────────────────────────────────────────────────
    body_raw = str(_pick(data, 'bodyParagraphs', 'letterBody', 'body')).strip()
    if body_raw:
        paras = [p.strip() for p in body_raw.split('\n') if p.strip()]
    else:
        paras = ['(กรุณาระบุเนื้อหา)']

    para_html = [f'  <p class="para">{_esc(p)}</p>' for p in paras]
    body_html = '\n'.join(para_html)

    # ─────────────────────────────────────────────────────────────────
    # Sig closing: เลือก variant ตามว่ามี signature/stamp หรือไม่
    # ─────────────────────────────────────────────────────────────────
    if signer_name:
        if sig_key or stamp_key:
            sig_html = build_sig_closing_with_image(
                signer=signer_name,
                position=signer_pos,
                signature_key=sig_key,
                stamp_key=stamp_key,
            )
        else:
            sig_html = sig_closing(signer_name, signer_pos)
    else:
        sig_html = ''

    # ─────────────────────────────────────────────────────────────────
    # Log final payload (debug)
    # ─────────────────────────────────────────────────────────────────
    logger.info(
        f'[S41] GL resolved: title={title[:30]} | recipient={recipient[:30]} | '
        f'body_len={len(body_raw)} | sig={sig_key or "-"} | stamp={stamp_key or "-"}'
    )

    # ── สร้าง page HTML ──
    css = build_css()
    if paged:
        css += _paged_css(data.get('docNumber', ''))
        # ลายเซ็นไม่ไปอยู่หน้าสุดท้ายลำพัง — ผูกกับย่อหน้าสุดท้าย
        if sig_html:
            body_html = '\n'.join(para_html[:-1])
            sig_html = '<div class="keep-tail">\n' + para_html[-1] + '\n' + sig_html + '\n</div>'
    page = f"""<div class="page">
  {'<div class="doc-number">เลขที่ ' + doc_number + '</div>' if doc_number else ''}
  <div class="title">{title}</div>
  <div class="written-at">เขียนที่ {_esc(entity_name)}<br>วันที่ {doc_date}</div>
  {'<div class="subject-line"><span class="subject-label">เรื่อง</span><span class="subject-value">' + subject + '</span></div>' if subject else ''}
  {'<div class="subject-line"><span class="subject-label">เรียน</span><span class="subject-value">' + recipient + '</span></div>' if recipient else ''}
  {_references_html(refs)}
{body_html}
  {sig_html}
  <div class="clearfix"></div>
</div>"""

    return build_html(css, page)


# ══════════════════════════════════════════════════════════════════════
# GENERATE PDF
# ══════════════════════════════════════════════════════════════════════

def generate_general_letter_pdf(data):
    """สร้าง General Letter PDF → overlay บน entity template
    Returns: PDF bytes
    """
    html = _build_general_letter_html(data)
    content_bytes = html_to_pdf(html)

    # overlay บน entity template (logo + watermark ตามบริษัท)
    entity_key = data.get('entityKey', '')
    if _page_count(content_bytes) > 1:
        # เนื้อหาเกิน 1 หน้า → จัดหน้าใหม่แบบหลายหน้า แล้วซ้อนหัวกระดาษทุกหน้า
        from hr_doc_layout import merge_multi_page
        content_bytes = html_to_pdf(_build_general_letter_html(data, paged=True))
        return merge_multi_page(content_bytes, entity_key)
    return merge_on_template(content_bytes, entity_key)


def _page_count(pdf_bytes):
    from io import BytesIO
    from pypdf import PdfReader
    try:
        return len(PdfReader(BytesIO(pdf_bytes)).pages)
    except Exception:
        return 1


# ══════════════════════════════════════════════════════════════════════
# FLASK ROUTE REGISTRATION
# ══════════════════════════════════════════════════════════════════════

def register_general_letter_routes(app):
    """ลงทะเบียน route สำหรับหนังสือทั่วไป"""

    @app.route('/generate_general_letter', methods=['POST'])
    def api_generate_general_letter():
        try:
            from app import _check_key, _safe_error
            err = _check_key()
            if err:
                return err

            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'No JSON body'}), 400

            pdf_bytes = generate_general_letter_pdf(data)
            pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

            # ชื่อไฟล์จาก title (fallback: subject → letter)
            title_raw = _pick(data, 'title', 'subject', 'letterSubject') or 'letter'
            safe_title = ''.join(
                ch for ch in str(title_raw)[:40]
                if ch.isalnum() or ch in '_- ' or '\u0e00' <= ch <= '\u0e7f'
            ).strip() or 'letter'
            filename = f'{safe_title}.pdf'

            return jsonify({
                'success':   True,
                'pdfBase64': pdf_b64,
                'fileName':  filename,
                'features':  FEATURES,
            })
        except Exception as e:
            logger.error(f'generate_general_letter error: {e}')
            from app import _safe_error
            return jsonify(_safe_error(e, 'generate_general_letter')), 500
