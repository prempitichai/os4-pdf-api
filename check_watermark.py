#!/usr/bin/env python3
"""ตรวจความเข้มลายน้ำของหัวกระดาษทุกบริษัท + ใบแมสเซนเจอร์ ให้ตรง WATERMARK_OPACITY (template_utils)
รัน: python3 check_watermark.py   — ผ่าน = exit 0"""
import base64, glob, os, sys
from io import BytesIO
from PIL import Image
from pypdf import PdfReader
import template_utils as T

bad = 0
for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bg_template*.pdf'))):
    p = PdfReader(BytesIO(T._letterhead_bytes(f))).pages[0]
    xo, ph = p['/Resources']['/XObject'], float(p.mediabox.height)
    d = T._drawn_images(p)
    wm = max((x for x in d if 0.15 * ph < x[4] + x[2] / 2 < 0.8 * ph), key=lambda x: x[1] * x[2])
    ref = max((T._ink(xo[x[0]].get_object().decode_as_image()) for x in d if x[4] > 0.85 * ph), default=T._LOGO_INK_FALLBACK)
    got = T._ink(xo[wm[0]].get_object().decode_as_image()) / ref
    ok = abs(got - T.WATERMARK_OPACITY) <= 0.01
    bad += not ok
    print(f"{'✓' if ok else '✗'} {os.path.basename(f):28s} {got:.1%}")
from messenger_images import SCM_LOGO_B64
from generate_messenger import _messenger_watermark
got = T._ink(Image.open(BytesIO(_messenger_watermark()))) / T._ink(Image.open(BytesIO(base64.b64decode(SCM_LOGO_B64))))
ok = abs(got - T.WATERMARK_OPACITY) <= 0.01
bad += not ok
print(f"{'✓' if ok else '✗'} {'messenger':28s} {got:.1%}")
sys.exit(1 if bad else 0)
