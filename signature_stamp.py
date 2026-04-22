# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
signature_stamp.py — Digital Signature + Company Stamp helpers
═══════════════════════════════════════════════════════════════
VERSION: v6 (22/04/69)

★ สำหรับใส่ลายเซ็นและตราประทับลงบน PDF forms (WeasyPrint-compatible)

[v6 Changelog — fine-tune ตามผล test จริง 0337]
  ✓ ตราประทับ: 60mm → 70mm (ใหญ่ขึ้นให้ชัด)
  ✓ ลายเซ็น: 55mm (คงเดิม)
  ✓ ลายเซ็น margin-bottom: -26mm → -15mm
    • -26mm: ลายเซ็น "หลุดลงใต้เส้น" ผลทดสอบใน 0337
    • -15mm: ปลายลายเซ็นทับเส้นพอดี (ตามคำขอ)
  ✓ Layout: natural flow (Option A) — signature เลื่อนตามเนื้อหา
    • ถ้าเนื้อหาสั้น → signature อยู่บน
    • ถ้าเนื้อหายาว → signature เลื่อนลง (ไม่ซ้อนเนื้อหา)

[Baseline features จาก v5-final2]
  ✓ No white background (watermark ทะลุผ่านเป็นธรรมชาติ)
  ✓ No z-index, padding, border-radius
  ✓ Layout: 2-col 50/50 (ตราซ้าย / ลายเซ็นขวา)
  ✓ "ขอแสดงความนับถือ" ชิดขวา

[Technical baseline จาก v4]
  ✓ Triple-path fallback: assets/xxx/yyy.png | yyy.png | assets:xxx:yyy.png
  ✓ Logger debug messages
  ✓ opacity:1.0 (ชัดเจน ไม่จางกลบ watermark)
  ✓ Base64 data URI (portable, no file:// issues)
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
        'width_mm': 55,   # v6: คงเดิมจาก v5-final2
        'height_mm': 30,
    },
}


# ═══════════════════════════════════════════════════════════════
# [REGISTRY] Stamps — ตราประทับบริษัท
# ═══════════════════════════════════════════════════════════════
# เพิ่มตราใหม่: ใส่ภาพใน ./assets/stamps/ + register ที่นี่

STAMPS = {
    'scm_technologies': {
        'filename': 'scm_technologies.png',
        'name': 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด',
        'width_mm': 70,   # v6: 60 → 70 (ใหญ่ขึ้นให้ชัด)
        'height_mm': 40,
    },
    # 'scm_s':    { 'filename': 'scm_s.png', 'name': '...', 'width_mm': 70, 'height_mm': 40 },
    # 'scm_t':    { ... },
    # 'scm_c':    { ... },
    # 'holding':  { ... },
    # 'cyber':    { ... },
    # 'bc':       { ... },
    # 'b2b':      { ... },
    # 'fahcloud': { ... },
}


# ═══════════════════════════════════════════════════════════════
# [HELPERS] Path resolution — Triple-path fallback
# ═══════════════════════════════════════════════════════════════

def get_signature_path(key):
    """หา path ของ signature — triple-path fallback

    1. assets/signatures/xxx.png  (ถูกต้องตามมาตรฐาน)
    2. xxx.png                    (root fallback)
    3. assets:signatures:xxx.png  (⚠️ macOS slash→colon bug)
    """
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
# [HELPERS] Base64 encoder — สำหรับ WeasyPrint
# ═══════════════════════════════════════════════════════════════

def _img_to_base64_uri(path):
    """แปลงภาพ PNG → data URI base64

    ใช้ data:image/png;base64 แทน file:// URI เพราะ:
    - Portable (ไม่ต้องกังวล path)
    - เร็วกว่าเปิดไฟล์ใหม่ทุกครั้ง
    """
    try:
        with open(path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        return f'data:image/png;base64,{b64}'
    except Exception as e:
        logger.error(f'ไม่สามารถอ่านไฟล์ภาพ {path}: {e}')
        return ''


# ═══════════════════════════════════════════════════════════════
# [MAIN HELPER] build_sig_closing_with_image (v6)
# ═══════════════════════════════════════════════════════════════

def build_sig_closing_with_image(signer, position='Corporate Lawyers',
                                  signature_key=None, stamp_key=None):
    """
    สร้าง HTML block ลายเซ็นท้ายเอกสาร พร้อมใส่ภาพลายเซ็น + ตราประทับ

    [Layout v6 — ตรงกับตัวอย่าง INET_LGD_0303]
      ┌─────────────────────────────────────────────┐
      │                       ขอแสดงความนับถือ       │
      │                                             │
      │  ┌───────────────┬──────────────────────┐  │
      │  │               │     [ลายเซ็น 55mm]    │  │
      │  │  [ตรา 70mm]   │  ═══════════════     │  │ 50% | 50%
      │  │               │  (นายปิติชัย)         │  │ ← ปลายซ้อนเส้น
      │  │               │  Corporate Lawyers    │  │
      │  └───────────────┴──────────────────────┘  │
      └─────────────────────────────────────────────┘

    ★ ไม่มี white background — watermark ผ่านทะลุตามธรรมชาติ
    ★ ปลายลายเซ็นทับเส้นเล็กน้อย (margin-bottom:-15mm)
    ★ Natural flow — เลื่อนตามเนื้อหา

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

    # Debug logs
    logger.info(f'[SIG_CLOSING v6] sig_key={signature_key} sig_uri_len={len(sig_uri)}')
    logger.info(f'[SIG_CLOSING v6] stamp_key={stamp_key} stamp_uri_len={len(stamp_uri)}')

    # ขนาดจาก registry (fallback ถ้าไม่มี key)
    sig_meta = SIGNATURES.get(signature_key, {}) if signature_key else {}
    stamp_meta = STAMPS.get(stamp_key, {}) if stamp_key else {}
    sig_w = sig_meta.get('width_mm', 55)
    stamp_w = stamp_meta.get('width_mm', 70)

    # ─── Build image HTML ───
    stamp_img_html = ''
    if stamp_uri:
        stamp_img_html = (
            f'<img src="{stamp_uri}" '
            f'style="width:{stamp_w}mm; height:auto; opacity:1.0; display:inline-block;" '
            f'alt="company stamp"/>'
        )

    # ลายเซ็นทับเส้นใต้ชื่อ — ใช้ margin-bottom negative (v6: -15mm)
    # ลดจาก v5-final2 (-26mm) เพราะลายเซ็นหลุดลงใต้เส้น → ต้องการแค่ปลายทับเส้น
    sig_img_html = ''
    if sig_uri:
        sig_img_html = (
            f'<img src="{sig_uri}" '
            f'style="width:{sig_w}mm; height:auto; opacity:1.0; '
            f'display:block; margin:0 auto -15mm auto;" '
            f'alt="signature"/>'
        )

    # ─── Assemble HTML ───
    # [v6 Design]
    # ★ NO white background — ตรงกับตัวอย่าง 0303
    # ★ NO z-index, padding, border-radius
    # ★ "ขอแสดงความนับถือ" ชิดขวา (align กับ column ลายเซ็น)
    # ★ 2-column table 50/50
    #   - ซ้าย: ตราประทับ (70mm) — center + vertical-align:middle
    #   - ขวา: ลายเซ็น (55mm, ปลายทับเส้น) + เส้นใต้ + (ชื่อ) + ตำแหน่ง
    # ★ margin-top:10mm → เว้นจากเนื้อหา natural flow
    html = f'''
<div class="sig-closing" style="margin-top:10mm; page-break-inside:avoid;">
  <div style="text-align:right; padding-right:18mm; margin-bottom:4mm;
              font-size:inherit;">
    ขอแสดงความนับถือ
  </div>
  <table style="width:100%; border-collapse:collapse;">
    <tr>
      <td style="width:50%; vertical-align:middle; text-align:center;
                 padding:8mm 0 0 0;">
        {stamp_img_html}
      </td>
      <td style="width:50%; vertical-align:bottom; text-align:center;
                 padding:0;">
        {sig_img_html}
        <div style="border-top:1px solid #000; padding-top:1mm;
                    margin:0 auto; min-width:75mm; display:inline-block;">
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
    print('=== Signature Stamp Helper v6 — Debug ===\n')
    print(f'BASE_DIR: {BASE_DIR}')
    print(f'ASSETS_DIR: {ASSETS_DIR}')
    print(f'ASSETS_DIR exists: {os.path.isdir(ASSETS_DIR)}\n')

    print('Available signatures:')
    for sig in list_available_signatures():
        print(f'  • {sig["key"]}: {sig["name"]} ({sig["title"]})')
    print('\nAvailable stamps:')
    for stamp in list_available_stamps():
        print(f'  • {stamp["key"]}: {stamp["name"]}')

    print('\n=== Test build_sig_closing_with_image (v6) ===')
    html = build_sig_closing_with_image(
        signer='นายปิติชัย พัฒนกิจกุล',
        position='Corporate Lawyers',
        signature_key='pitichai',
        stamp_key='scm_technologies'
    )
    print('HTML length:', len(html))
    print('\n--- HTML Preview (first 500 chars) ---')
    print(html[:500])
