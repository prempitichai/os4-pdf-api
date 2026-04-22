# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
signature_stamp.py — Digital Signature + Company Stamp helpers
═══════════════════════════════════════════════════════════════
VERSION: v3-table-layout (22/04/69)

★ สำหรับใส่ลายเซ็นและตราประทับลงบน PDF forms (WeasyPrint-compatible)

[Why table-based instead of absolute positioning?]
WeasyPrint ไม่รองรับ position:absolute + transform:translateX() ดีเท่า
browser — ทำให้ภาพไม่ render ถูกตำแหน่ง → เปลี่ยนเป็น HTML table layout
(3 columns: stamp | signature | spacer) ซึ่ง WeasyPrint รองรับเต็มรูปแบบ

Registry:
  SIGNATURES = { 'pitichai': {...} }
  STAMPS = { 'scm_technologies': {...} }

Public API:
  build_sig_closing_with_image(signer, position, signature_key, stamp_key)
    → คืน HTML block สำหรับวาง sig closing พร้อมรูป

  validate_signature_key(key) → (bool, err_msg)
  validate_stamp_key(key) → (bool, err_msg)

  list_available_signatures() → [{key, name, title}, ...]
  list_available_stamps() → [{key, name}, ...]
  get_signature_stamp_options() → { signatures: [...], stamps: [...] }

Dependencies: stdlib only (os, base64, logging) — ไม่เพิ่ม package
"""

import os
import base64
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# [CONFIG] Paths
# ═══════════════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')


# ═══════════════════════════════════════════════════════════════
# [REGISTRY] Signatures — ลายเซ็นบุคคล
# ═══════════════════════════════════════════════════════════════
# เพิ่มลายเซ็นใหม่: ใส่ภาพใน ./assets/signatures/ + register ที่นี่

SIGNATURES = {
    'pitichai': {
        'filename': 'pitichai.png',
        'name': 'นายปิติชัย พัฒนกิจกุล',
        'title': 'Corporate Lawyers',
        # ขนาดในหน่วย mm บน PDF
        'width_mm': 48,
        'height_mm': 26,
    },
    # 'other_person': { ... },   # future
}


# ═══════════════════════════════════════════════════════════════
# [REGISTRY] Stamps — ตราประทับบริษัท
# ═══════════════════════════════════════════════════════════════
# เพิ่มตราใหม่: ใส่ภาพใน ./assets/stamps/ + register ที่นี่

STAMPS = {
    'scm_technologies': {
        'filename': 'scm_technologies.png',
        'name': 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด',
        # ขนาดในหน่วย mm บน PDF
        'width_mm': 55,
        'height_mm': 31,
    },
    # 'scm_s':    { 'filename': 'scm_s.png', 'name': '...', 'width_mm': 45, 'height_mm': 26 },
    # 'scm_t':    { ... },
    # 'scm_c':    { ... },
    # 'holding':  { ... },
    # 'cyber':    { ... },
    # 'bc':       { ... },
    # 'b2b':      { ... },
    # 'fahcloud': { ... },
}


# ═══════════════════════════════════════════════════════════════
# [HELPERS] Path resolution
# ═══════════════════════════════════════════════════════════════

def get_signature_path(key):
    """หา path ของ signature ตาม key — คืน None ถ้าไม่พบ"""
    if not key or key not in SIGNATURES:
        return None
    filename = SIGNATURES[key]['filename']
    path = os.path.join(ASSETS_DIR, 'signatures', filename)
    return path if os.path.exists(path) else None


def get_stamp_path(key):
    """หา path ของ stamp ตาม key — คืน None ถ้าไม่พบ"""
    if not key or key not in STAMPS:
        return None
    filename = STAMPS[key]['filename']
    path = os.path.join(ASSETS_DIR, 'stamps', filename)
    return path if os.path.exists(path) else None


# ═══════════════════════════════════════════════════════════════
# [HELPERS] Base64 encoder — สำหรับ WeasyPrint
# ═══════════════════════════════════════════════════════════════
# ใช้ data:image/png;base64 แทน file:// URI เพราะ portable + fast

def _img_to_base64_uri(path):
    """แปลงภาพ PNG → data URI base64

    Args:
        path (str): full path
    Returns:
        str: 'data:image/png;base64,...' หรือ '' ถ้า error
    """
    try:
        with open(path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        return f'data:image/png;base64,{b64}'
    except Exception as e:
        logger.error(f'ไม่สามารถอ่านไฟล์ภาพ {path}: {e}')
        return ''


# ═══════════════════════════════════════════════════════════════
# [MAIN HELPER] build_sig_closing_with_image (v3 — table-based)
# ═══════════════════════════════════════════════════════════════

def build_sig_closing_with_image(signer, position='Corporate Lawyers',
                                  signature_key=None, stamp_key=None):
    """
    สร้าง HTML block ลายเซ็นท้ายเอกสาร พร้อมใส่ภาพลายเซ็น + ตราประทับ (ถ้ามี)

    [Layout — table 3 columns]
      ┌────────────────────────────────────────┐
      │            ขอแสดงความนับถือ             │
      │                                        │
      │  ┌─────────┬─────────────┬─────────┐  │
      │  │ [ตรา]   │ [ลายเซ็น]   │         │  │ 32% | 40% | 28%
      │  └─────────┴─────────────┴─────────┘  │
      │           ___________________          │
      │           (นายปิติชัย พัฒนกิจกุล)       │
      │           Corporate Lawyers            │
      └────────────────────────────────────────┘

    Args:
        signer (str): ชื่อผู้ลงนาม
        position (str): ตำแหน่ง
        signature_key (str | None): key ลายเซ็น
        stamp_key (str | None): key ตรา

    Returns:
        str: HTML block (ready to inject in template)
    """
    sig_path = get_signature_path(signature_key) if signature_key else None
    stamp_path = get_stamp_path(stamp_key) if stamp_key else None

    sig_uri = _img_to_base64_uri(sig_path) if sig_path else ''
    stamp_uri = _img_to_base64_uri(stamp_path) if stamp_path else ''

    # ขนาดจาก registry (fallback ถ้าไม่มี key)
    sig_meta = SIGNATURES.get(signature_key, {}) if signature_key else {}
    stamp_meta = STAMPS.get(stamp_key, {}) if stamp_key else {}
    sig_w = sig_meta.get('width_mm', 48)
    stamp_w = stamp_meta.get('width_mm', 45)

    # ─── Build table cells ───
    stamp_cell_html = ''
    if stamp_uri:
        stamp_cell_html = (
            f'<img src="{stamp_uri}" '
            f'style="width:{stamp_w}mm; height:auto; opacity:0.88;" '
            f'alt="company stamp"/>'
        )

    sig_cell_html = ''
    if sig_uri:
        sig_cell_html = (
            f'<img src="{sig_uri}" '
            f'style="width:{sig_w}mm; height:auto;" '
            f'alt="signature"/>'
        )

    # ─── Assemble HTML ───
    # Table columns: 32% | 40% | 28%
    # margin-bottom: -8mm เพื่อให้ลายเซ็นทับเส้นลายเซ็น
    html = f'''
<div class="sig-closing" style="margin-top:8mm; page-break-inside:avoid;">
  <div style="text-align:center; margin-bottom:4mm; font-size:inherit;">ขอแสดงความนับถือ</div>
  <table style="width:100%; border-collapse:collapse; margin-bottom:-8mm;">
    <tr>
      <td style="width:32%; vertical-align:middle; text-align:center; padding:0;">{stamp_cell_html}</td>
      <td style="width:40%; vertical-align:bottom; text-align:center; padding:0;">{sig_cell_html}</td>
      <td style="width:28%; padding:0;">&nbsp;</td>
    </tr>
  </table>
  <div style="text-align:center;">
    <div style="display:inline-block; border-top:1px solid #000; padding-top:1mm; min-width:75mm;">
      <div style="font-weight:bold;">({signer})</div>
      <div style="color:#444;">{position}</div>
    </div>
  </div>
</div>
'''
    return html


# ═══════════════════════════════════════════════════════════════
# [METADATA API] — สำหรับ GAS สร้าง UI
# ═══════════════════════════════════════════════════════════════

def list_available_signatures():
    """คืน list ของลายเซ็นที่ใช้งานได้ (มีไฟล์อยู่จริง)"""
    result = []
    for key, meta in SIGNATURES.items():
        if get_signature_path(key):
            result.append({
                'key': key,
                'name': meta['name'],
                'title': meta.get('title', ''),
            })
    return result


def list_available_stamps():
    """คืน list ของตราประทับที่ใช้งานได้ (มีไฟล์อยู่จริง)"""
    result = []
    for key, meta in STAMPS.items():
        if get_stamp_path(key):
            result.append({
                'key': key,
                'name': meta['name'],
            })
    return result


def get_signature_stamp_options():
    """คืน options ทั้งหมดสำหรับ GAS → สร้าง UI"""
    return {
        'signatures': list_available_signatures(),
        'stamps': list_available_stamps(),
    }


# ═══════════════════════════════════════════════════════════════
# [VALIDATION]
# ═══════════════════════════════════════════════════════════════

def validate_signature_key(key):
    """ตรวจ signature key — (is_valid, error_message)"""
    if not key:
        return True, ''
    if key not in SIGNATURES:
        return False, f'ไม่รู้จัก signature key: {key}'
    if not get_signature_path(key):
        return False, f'ไม่พบไฟล์ signature: {key}'
    return True, ''


def validate_stamp_key(key):
    """ตรวจ stamp key — (is_valid, error_message)"""
    if not key:
        return True, ''
    if key not in STAMPS:
        return False, f'ไม่รู้จัก stamp key: {key}'
    if not get_stamp_path(key):
        return False, f'ไม่พบไฟล์ stamp: {key}'
    return True, ''


# ═══════════════════════════════════════════════════════════════
# [DEBUG] — Test module standalone
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print('=== Signature Stamp Helper v3 — Debug ===\n')
    print('Available signatures:')
    for sig in list_available_signatures():
        print(f'  • {sig["key"]}: {sig["name"]} ({sig["title"]})')
    print('\nAvailable stamps:')
    for stamp in list_available_stamps():
        print(f'  • {stamp["key"]}: {stamp["name"]}')

    print('\n=== Test build_sig_closing_with_image ===')
    html = build_sig_closing_with_image(
        signer='นายปิติชัย พัฒนกิจกุล',
        position='Corporate Lawyers',
        signature_key='pitichai',
        stamp_key='scm_technologies'
    )
    print('HTML length:', len(html))
