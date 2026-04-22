# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
signature_stamp.py — Digital Signature + Company Stamp helpers
═══════════════════════════════════════════════════════════════
VERSION: v5-layout-0303-match (22/04/69)

★ สำหรับใส่ลายเซ็นและตราประทับลงบน PDF forms (WeasyPrint-compatible)

[v5 Changelog]
  • เปลี่ยน layout จาก 3-col → 2-col (50/50) ตรงกับตัวอย่าง INET_LGD_0303
  • ตราประทับ: ซ้าย (50%) — center align
  • ลายเซ็น: ขวา (50%) — วางทับเส้นลายเซ็น (margin-bottom negative)
  • "ขอแสดงความนับถือ" ชิดขวา (ตรงกับ column ลายเซ็น)
  • ลด size: sig 48→40mm, stamp 55→50mm (ตาม proportion ตัวอย่าง)
  • เพิ่ม logger.info เพื่อ debug ง่ายขึ้น

[v4 kept features]
  ✓ Triple-path fallback: assets/xxx/yyy.png | yyy.png | assets:xxx:yyy.png
  ✓ White background container + z-index สูง (ไม่ถูก watermark กลบ)
  ✓ opacity:1.0 เพื่อให้ชัดเจน
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

SIGNATURES = {
    'pitichai': {
        'filename': 'pitichai.png',
        'name': 'นายปิติชัย พัฒนกิจกุล',
        'title': 'Corporate Lawyers',
        'width_mm': 40,   # v5: ลดจาก 48 → 40
        'height_mm': 22,
    },
}


# ═══════════════════════════════════════════════════════════════
# [REGISTRY] Stamps — ตราประทับบริษัท
# ═══════════════════════════════════════════════════════════════

STAMPS = {
    'scm_technologies': {
        'filename': 'scm_technologies.png',
        'name': 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด',
        'width_mm': 50,   # v5: ลดจาก 55 → 50
        'height_mm': 28,
    },
}


# ═══════════════════════════════════════════════════════════════
# [HELPERS] Path resolution
# ═══════════════════════════════════════════════════════════════

def get_signature_path(key):
    """หา path ของ signature — triple-path fallback"""
    if not key or key not in SIGNATURES:
        return None
    filename = SIGNATURES[key]['filename']
    candidates = [
        os.path.join(ASSETS_DIR, 'signatures', filename),
        os.path.join(BASE_DIR, filename),
        os.path.join(BASE_DIR, f'assets:signatures:{filename}'),
    ]
    for p in candidates:
        if os.path.exists(p):
            logger.info(f'[SIG] Found at: {p}')
            return p
    logger.warning(f'[SIG] File not found: {filename} (tried: {candidates})')
    return None


def get_stamp_path(key):
    """หา path ของ stamp — triple-path fallback"""
    if not key or key not in STAMPS:
        return None
    filename = STAMPS[key]['filename']
    candidates = [
        os.path.join(ASSETS_DIR, 'stamps', filename),
        os.path.join(BASE_DIR, filename),
        os.path.join(BASE_DIR, f'assets:stamps:{filename}'),
    ]
    for p in candidates:
        if os.path.exists(p):
            logger.info(f'[STAMP] Found at: {p}')
            return p
    logger.warning(f'[STAMP] File not found: {filename} (tried: {candidates})')
    return None


# ═══════════════════════════════════════════════════════════════
# [HELPERS] Base64 encoder
# ═══════════════════════════════════════════════════════════════

def _img_to_base64_uri(path):
    """แปลงภาพ PNG → data URI base64"""
    try:
        with open(path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        return f'data:image/png;base64,{b64}'
    except Exception as e:
        logger.error(f'ไม่สามารถอ่านไฟล์ภาพ {path}: {e}')
        return ''


# ═══════════════════════════════════════════════════════════════
# [MAIN HELPER] build_sig_closing_with_image (v5 — 0303 layout)
# ═══════════════════════════════════════════════════════════════

def build_sig_closing_with_image(signer, position='Corporate Lawyers',
                                  signature_key=None, stamp_key=None):
    """
    สร้าง HTML block ลายเซ็นท้ายเอกสาร พร้อมใส่ภาพลายเซ็น + ตราประทับ

    [Layout v5 — ตรงกับตัวอย่าง INET_LGD_0303]
      ┌─────────────────────────────────────────────┐
      │                       ขอแสดงความนับถือ       │
      │                                             │
      │  ┌───────────────┬──────────────────────┐  │
      │  │               │     [ลายเซ็น]         │  │
      │  │  [ตรา SCM]    │  ────────────────     │  │ 50% | 50%
      │  │               │  (นายปิติชัย)         │  │
      │  │               │  Corporate Lawyers    │  │
      │  └───────────────┴──────────────────────┘  │
      └─────────────────────────────────────────────┘

    Returns:
        str: HTML block (ready to inject in template)
    """
    sig_path = get_signature_path(signature_key) if signature_key else None
    stamp_path = get_stamp_path(stamp_key) if stamp_key else None

    sig_uri = _img_to_base64_uri(sig_path) if sig_path else ''
    stamp_uri = _img_to_base64_uri(stamp_path) if stamp_path else ''

    # Debug logs
    logger.info(f'[SIG_CLOSING] sig_key={signature_key} sig_uri_len={len(sig_uri)}')
    logger.info(f'[SIG_CLOSING] stamp_key={stamp_key} stamp_uri_len={len(stamp_uri)}')

    sig_meta = SIGNATURES.get(signature_key, {}) if signature_key else {}
    stamp_meta = STAMPS.get(stamp_key, {}) if stamp_key else {}
    sig_w = sig_meta.get('width_mm', 40)
    stamp_w = stamp_meta.get('width_mm', 50)

    # ─── Build image HTML ───
    stamp_img_html = ''
    if stamp_uri:
        stamp_img_html = (
            f'<img src="{stamp_uri}" '
            f'style="width:{stamp_w}mm; height:auto; opacity:1.0; display:inline-block;" '
            f'alt="company stamp"/>'
        )

    # ลายเซ็นทับเส้นใต้ชื่อ — ใช้ margin-bottom negative
    sig_img_html = ''
    if sig_uri:
        sig_img_html = (
            f'<img src="{sig_uri}" '
            f'style="width:{sig_w}mm; height:auto; opacity:1.0; '
            f'display:block; margin:0 auto -12mm auto;" '
            f'alt="signature"/>'
        )

    # ─── Assemble HTML ───
    html = f'''
<div class="sig-closing" style="margin-top:10mm; page-break-inside:avoid;
    background-color:#ffffff; padding:6mm 4mm;
    border-radius:2mm; position:relative; z-index:100;">
  <div style="text-align:right; padding-right:18mm; margin-bottom:2mm;
              font-size:inherit; position:relative; z-index:101;">
    ขอแสดงความนับถือ
  </div>
  <table style="width:100%; border-collapse:collapse;
                position:relative; z-index:101;">
    <tr>
      <td style="width:50%; vertical-align:middle; text-align:center;
                 padding:8mm 0 0 0; background:#fff;">
        {stamp_img_html}
      </td>
      <td style="width:50%; vertical-align:bottom; text-align:center;
                 padding:0 0 0 0; background:#fff;">
        {sig_img_html}
        <div style="border-top:1px solid #000; padding-top:1mm;
                    margin:0 auto; min-width:70mm; display:inline-block;
                    background:#fff;">
          <div style="font-weight:bold;">({signer})</div>
          <div style="color:#444;">{position}</div>
        </div>
      </td>
    </tr>
  </table>
</div>
'''
    return html


# ═══════════════════════════════════════════════════════════════
# [METADATA API] — สำหรับ GAS สร้าง UI
# ═══════════════════════════════════════════════════════════════

def list_available_signatures():
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
    result = []
    for key, meta in STAMPS.items():
        if get_stamp_path(key):
            result.append({
                'key': key,
                'name': meta['name'],
            })
    return result


def get_signature_stamp_options():
    return {
        'signatures': list_available_signatures(),
        'stamps': list_available_stamps(),
    }


# ═══════════════════════════════════════════════════════════════
# [VALIDATION]
# ═══════════════════════════════════════════════════════════════

def validate_signature_key(key):
    if not key:
        return True, ''
    if key not in SIGNATURES:
        return False, f'ไม่รู้จัก signature key: {key}'
    if not get_signature_path(key):
        return False, f'ไม่พบไฟล์ signature: {key}'
    return True, ''


def validate_stamp_key(key):
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
    print('=== Signature Stamp Helper v5 — Debug ===\n')
    print(f'BASE_DIR: {BASE_DIR}')
    print(f'ASSETS_DIR: {ASSETS_DIR}')
    print(f'ASSETS_DIR exists: {os.path.isdir(ASSETS_DIR)}\n')

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
