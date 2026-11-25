#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
letterhead_overlay.py — วาง PDF ที่สร้างที่อื่นลงบนหัวกระดาษบริษัท [2026-11-25]
POST /letterhead_overlay  { pdfBase64, entityKey } → { success, pdfBase64, pages }
ใช้กับ: รายงานการประชุม (GAS แปลงจาก Google Docs เป็น PDF แล้วส่งมา) — ได้โลโก้ / ลายน้ำ 12% / ท้ายกระดาษ
ชุดเดียวกับหนังสืออื่นของระบบ (merge_on_template) ; รับเฉพาะไฟล์ PDF ไม่ดึง URL ใด ๆ
"""

import base64
import binascii
import logging
from io import BytesIO
from flask import request, jsonify
from pypdf import PdfReader
from template_utils import merge_on_template

logger = logging.getLogger(__name__)
_MAX_BYTES = 15 * 1024 * 1024


def register_letterhead_routes(app):
    @app.route('/letterhead_overlay', methods=['POST'])
    def api_letterhead_overlay():
        try:
            from app import _check_key
            err = _check_key()
            if err:
                return err
            data = request.get_json() or {}
            try:
                raw = base64.b64decode(str(data.get('pdfBase64') or ''), validate=True)
            except (binascii.Error, ValueError):
                raw = b''
            if not raw.startswith(b'%PDF') or len(raw) > _MAX_BYTES:
                return jsonify({'success': False, 'message': 'ไม่ใช่ไฟล์ PDF หรือใหญ่เกินไป'}), 400
            out = merge_on_template(raw, str(data.get('entityKey') or ''))
            return jsonify({'success': True, 'pdfBase64': base64.b64encode(out).decode('utf-8'),
                            'pages': len(PdfReader(BytesIO(out)).pages)})
        except Exception as e:
            logger.error('letterhead_overlay error: %s', e)
            from app import _safe_error
            return jsonify(_safe_error(e, 'letterhead_overlay')), 500
