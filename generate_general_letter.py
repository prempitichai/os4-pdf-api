#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: v1
"""
generate_general_letter.py — หนังสือทั่วไป (General Letter)
═══════════════════════════════════════════════════════════
ใช้ template_utils shared module (WeasyPrint + entity template overlay)
Layout อิงจาก หนังสือขอถอนหลักประกัน (BG Withdraw)

POST /generate_general_letter
  Input: {
    entityKey,        — sheet name เช่น "SCM T", "SCM C"
    title,            — หัวข้อหนังสือ (กลาง, bold)
    docNumber,        — เลขที่หนังสือ (บนซ้าย)
    docDate,          — วันที่ เช่น "7 เมษายน พ.ศ.2569"
    writtenAt,        — ทำที่ เช่น "บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด"
    subject,          — เรื่อง
    recipientName,    — เรียน
    bodyParagraphs,   — เนื้อหา (string หลายย่อหน้า แบ่งด้วย \\n)
    signerName,       — ชื่อผู้ลงนาม
    signerPosition,   — ตำแหน่ง
  }
  Output: { success, pdfBase64, fileName }

★ เนื้อหาเยอะ → ลายเซ็นเลื่อนลงตาม (WeasyPrint จัดให้อัตโนมัติ)
★ overlay บน entity template (logo + watermark ตามบริษัท)
"""

import base64
import logging
from datetime import datetime
from flask import request, jsonify
from template_utils import (
    merge_on_template, html_to_pdf, build_css, build_html,
    fmt, fmt_date_th, sig_closing
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
# BUILD HTML — layout เหมือนหนังสือขอถอน BG
# ══════════════════════════════════════════════════════════════════════

def _build_general_letter_html(data):
    """สร้าง HTML หนังสือทั่วไป — ใช้ class จาก build_css() ของ template_utils"""
    entity_key = str(data.get('entityKey', '') or '')
    entity_name = data.get('writtenAt') or _resolve_entity_name(entity_key)

    title       = _esc(data.get('title', 'หนังสือ'))
    doc_number  = _esc(data.get('docNumber', ''))
    doc_date    = _esc(data.get('docDate', '') or _today_th())
    subject     = _esc(data.get('subject', ''))
    recipient   = _esc(data.get('recipientName', ''))
    signer_name = data.get('signerName', '')
    signer_pos  = data.get('signerPosition', 'Corporate Lawyers')

    # ── เนื้อหา: แบ่งย่อหน้าด้วย \n ──
    body_raw = str(data.get('bodyParagraphs', '') or '').strip()
    if body_raw:
        paras = [p.strip() for p in body_raw.split('\n') if p.strip()]
    else:
        paras = ['(กรุณาระบุเนื้อหา)']

    body_html = '\n'.join(f'  <p class="para">{_esc(p)}</p>' for p in paras)

    # ── ลายเซ็น ──
    sig_html = sig_closing(signer_name, signer_pos) if signer_name else ''

    # ── สร้าง page HTML (ใช้ class จาก template_utils build_css) ──
    css = build_css()
    page = f"""<div class="page">
  {'<div class="doc-number">เลขที่ ' + doc_number + '</div>' if doc_number else ''}
  <div class="title">{title}</div>
  <div class="written-at">เขียนที่ {_esc(entity_name)}<br>วันที่ {doc_date}</div>
  {'<div class="subject-line"><span class="subject-label">เรื่อง</span><span class="subject-value">' + subject + '</span></div>' if subject else ''}
  {'<div class="subject-line"><span class="subject-label">เรียน</span><span class="subject-value">' + recipient + '</span></div>' if recipient else ''}
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
    return merge_on_template(content_bytes, entity_key)


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
            pdf_b64   = base64.b64encode(pdf_bytes).decode('utf-8')

            # ชื่อไฟล์จาก title
            safe_title = ''.join(
                ch for ch in (data.get('title', 'letter') or 'letter')[:40]
                if ch.isalnum() or ch in '_- ' or '\u0e00' <= ch <= '\u0e7f'
            ).strip() or 'letter'
            filename = f'{safe_title}.pdf'

            return jsonify({
                'success':   True,
                'pdfBase64': pdf_b64,
                'fileName':  filename,
            })
        except Exception as e:
            logger.error(f'generate_general_letter error: {e}')
            from app import _safe_error
            return jsonify(_safe_error(e, 'generate_general_letter')), 500
