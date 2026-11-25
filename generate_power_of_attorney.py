#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_power_of_attorney.py — หนังสือมอบอำนาจ (ทั่วไป) [2026-11-24]
══════════════════════════════════════════════════
POST /generate_power_of_attorney — ข้อมูลจาก GAS (_poaPayload_ ใน PoaDoc.js)

การตัดหน้า (ผู้ใช้สั่ง: ข้อน้อย / ข้อมากต้องตัดหน้าแบบมืออาชีพ):
  - ข้ออำนาจแต่ละข้อไม่ถูกตัดกลางข้อ (ข้อยาวเกินหนึ่งหน้าจึงแบ่งตามบรรทัด orphans/widows 3)
  - ข้อสุดท้าย + ข้อความปิดท้าย + ระยะเวลา + อากร + ช่องลงนาม อยู่หน้าเดียวกันเสมอ (ไม่มีหน้าที่มีแต่ลายเซ็น)
  - หัวกระดาษบริษัท / ลายน้ำทุกหน้า (merge_multi_page) · เลขที่ + หน้า x / y ทุกหน้า (build_css)
ช่องลงนาม = class เดียวกับหนังสือฝึกอบรม / ตักเตือน — ตรา+อากร / ผู้มอบ / ผู้รับมอบ / พยาน คนละแถว (_sign_table)
ไม่มีภาพลายเซ็น (ลงนามด้วยมือ) ; stampKey = ตราบริษัทแทนวงกลม "ประทับตรา"
"""

import base64
import logging
from io import BytesIO
from flask import request, jsonify
from pypdf import PdfReader
from template_utils import html_to_pdf
from hr_doc_layout import esc as _esc, document, merge_multi_page, nowrap, SEAL_HTML
from signature_stamp import validate_stamp_key, get_stamp_path, _img_to_base64_uri

logger = logging.getLogger(__name__)

_EXTRA_CSS = """
  .poa-at   { text-align: right; margin: 0 0 4mm; line-height: 1.6; }
  .cl       { page-break-inside: avoid; orphans: 3; widows: 3; }
  .tail     { page-break-inside: avoid; }
  .duty     { display: inline-block; vertical-align: middle; width: 30mm; min-height: 18mm; border: 0.8pt dashed #555; text-align: center;
              font-size: 11pt; line-height: 1.3; padding: 2.5mm 1mm; margin: 0 0 0 4mm; box-sizing: border-box; }
  .poa-seal { display: flex; justify-content: center; align-items: center; gap: 14mm; }
  .poa-seal .seal { margin: 0; }
  tr.poa-seal-row td { padding-top: 3mm; }
  .poa-seal .duty { margin: 0; }
  .clear    { clear: both; }
"""


def _join(names, word):
    names = [n for n in names if n]
    if len(names) < 2:
        return ''.join(names)
    return ' '.join(names[:-1]) + ' ' + word + names[-1]


def _cell(c, colspan=1):
    if not c:
        return '<td%s></td>' % (' colspan="2"' if colspan == 2 else '')
    role, name = c
    nm = '<div class="sg-name">(%s)</div>' % (_esc(name) if str(name or '').strip() else '<span class="bl"></span>')
    return ('<td%s><div class="sg"><div class="sg-row"><span class="sg-pre">ลงชื่อ</span><span class="sg-line"></span></div>%s<div class="sg-role">%s</div></div></td>'
            % (' colspan="2"' if colspan == 2 else '', nm, _esc(role)))


def _sign_table(grantors, grantees, witnesses, seal_html):
    """ช่องลงนาม (ผู้ใช้กำหนด 2026-11-24) — class เดียวกับ hr_doc_layout.signatures
       แถว 1 ตราบริษัท + อากรแสตมป์ · แถว 2 ผู้มอบ (คนเดียว = กลาง, สองคน = คู่) · แถว 3 ผู้รับมอบ (กลาง) · แถว 4 พยานคู่กัน
       คนที่เหลือเศษจากการจับคู่อยู่กลางแถว"""
    def rows_of(cells):
        out = []
        for i in range(0, len(cells), 2):
            pair = cells[i:i + 2]
            out.append(_cell(pair[0]) + _cell(pair[1]) if len(pair) == 2 else _cell(pair[0], 2))
        return out
    rows = ['<td colspan="2"><div class="poa-seal">%s</div></td>' % seal_html]
    rows += rows_of(grantors) + rows_of(grantees) + rows_of(witnesses)
    return '<table class="sign">' + ''.join('<tr%s>%s</tr>' % (' class="poa-seal-row"' if i == 0 else '', r) for i, r in enumerate(rows)) + '</table>'


def _build_poa_html(d):
    g = lambda k: str(d.get(k, '') or '').strip()
    co = g('companyName')
    grantors = [str(x).strip() for x in (d.get('grantors') or []) if str(x).strip()]
    grantees = [x for x in (d.get('grantees') or []) if isinstance(x, dict) and str(x.get('name', '')).strip()]
    clauses = [str(c).strip() for c in (d.get('clauses') or []) if str(c).strip()]
    witnesses = [str(w or '').strip() for w in (d.get('witnesses') or [])] + ['', '']

    def person(x):
        s = _esc(x.get('name', ''))
        if str(x.get('idCard', '')).strip():
            s += ' ผู้ถือบัตรประจำตัวประชาชนเลขที่ ' + _esc(x.get('idCard'))
        if str(x.get('position', '')).strip():
            s += ' ตำแหน่ง ' + _esc(x.get('position'))
        if str(x.get('address', '')).strip():
            s += ' ที่อยู่ ' + _esc(x.get('address'))
        return s

    # เลขบัตรผู้มอบ (ไม่บังคับ — หนังสือมอบอำนาจขอคืน BG ใช้) เรียงตามลำดับผู้มอบ
    gids = [str(v or '').strip() for v in (d.get('grantorIds') or [])]
    gr_txt = [_esc(n) + ((' ผู้ถือบัตรประจำตัวประชาชนเลขที่ ' + _esc(gids[i])) if i < len(gids) and gids[i] else '') for i, n in enumerate(grantors)]

    sep = d.get('granteeMode') == 'separate' and len(grantees) > 1
    to_txt = _join([person(x) for x in grantees], 'หรือ' if sep else 'และ') + (' คนใดคนหนึ่ง' if sep else (' ร่วมกัน' if len(grantees) > 1 else ''))
    addr = g('companyAddress')
    intro = ('โดยหนังสือฉบับนี้ ข้าพเจ้า %s (&ldquo;บริษัท&rdquo;) โดย %s กรรมการผู้มีอำนาจลงนาม%s ขอมอบอำนาจให้ %s มีอำนาจในการกระทำหรือดำเนินการดังต่อไปนี้'
             % (nowrap(_esc(co)), _join(gr_txt, g('grantorJoin') or 'และ'), (' สำนักงานใหญ่ตั้งอยู่' + ('' if addr.startswith('เลขที่') else 'เลขที่') + ' ' + nowrap(_esc(addr))) if addr else '', to_txt))
    if d.get('untilRevoked'):
        period = 'หนังสือมอบอำนาจฉบับนี้ให้มีผลใช้บังคับตั้งแต่วันที่ %s จนกว่าบริษัทจะเพิกถอนเป็นหนังสือ' % _esc(g('periodFrom') or g('docDate'))
    elif g('periodFrom') or g('periodTo'):
        period = 'หนังสือมอบอำนาจฉบับนี้ให้มีผลใช้บังคับตั้งแต่วันที่ %s ถึงวันที่ %s' % (_esc(g('periodFrom') or g('docDate')), _esc(g('periodTo')) or '..................')
    else:
        period = 'หนังสือมอบอำนาจฉบับนี้ให้มีผลใช้บังคับตั้งแต่วันที่ลงนามในหนังสือฉบับนี้'

    cl_html = ['<p class="cl"><b>ข้อ %d.</b> %s</p>' % (i + 1, _esc(c)) for i, c in enumerate(clauses)]
    seal = SEAL_HTML
    sk = g('stampKey') or None
    if sk:
        ok, err = validate_stamp_key(sk)
        uri = _img_to_base64_uri(get_stamp_path(sk) or '') if ok else ''
        if uri:
            seal = '<div class="seal" style="border:none"><img src="%s" style="width:30mm;height:auto" alt="company stamp"/></div>' % uri
        else:
            logger.warning('poa stamp_key: %s', err)
    duty = g('stampDuty')
    duty_html = ('<div class="duty">ปิดอากรแสตมป์<br>%s บาท</div>' % _esc(duty)) if duty else ''
    sig = _sign_table([('กรรมการผู้มีอำนาจ (ผู้มอบอำนาจ)', n) for n in grantors], [('ผู้รับมอบอำนาจ', x.get('name', '')) for x in grantees],
                      [('พยาน', witnesses[0]), ('พยาน', witnesses[1])], seal + duty_html)

    body = ('<div class="poa-at">ทำที่ %s<br>วันที่ %s</div>' % (_esc(g('writtenAt') or co), _esc(g('docDate')) or '..................')
            + '<p>%s</p>' % intro
            + '\n'.join(cl_html)
            + '<div class="tail">'
            + '<p>บรรดาการกระทำใด ๆ ซึ่งผู้รับมอบอำนาจได้กระทำไปภายในขอบเขตแห่งหนังสือมอบอำนาจฉบับนี้ ให้ถือเสมือนว่าข้าพเจ้าเป็นผู้กระทำเองทั้งสิ้น</p>'
            + '<p>%s จึงได้ลงลายมือชื่อและประทับตราสำคัญไว้เป็นหลักฐาน</p>' % period
            + sig + '</div>')
    return document('หนังสือมอบอำนาจ', body, g('docNumber')).replace('</style></head>', _EXTRA_CSS + '</style></head>', 1)


def register_power_of_attorney_routes(app):
    @app.route('/generate_power_of_attorney', methods=['POST'])
    def api_generate_power_of_attorney():
        try:
            from app import _check_key, _safe_error
            err = _check_key()
            if err:
                return err
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'No JSON body'}), 400
            if not (data.get('grantors') and data.get('grantees') and data.get('clauses')):
                return jsonify({'success': False, 'message': 'ข้อมูลผู้มอบ / ผู้รับ / ข้ออำนาจไม่ครบ'}), 400
            pdf_bytes = merge_multi_page(html_to_pdf(_build_poa_html(data)), data.get('entityKey', ''))
            pages = len(PdfReader(BytesIO(pdf_bytes)).pages)
            name = str((data.get('grantees') or [{}])[0].get('name', '') or 'poa')[:30]
            safe = ''.join(ch for ch in name if ch.isalnum() or ch in '_- ' or '฀' <= ch <= '๿').strip() or 'poa'
            return jsonify({'success': True, 'pdfBase64': base64.b64encode(pdf_bytes).decode('utf-8'),
                            'fileName': 'หนังสือมอบอำนาจ_%s.pdf' % safe, 'pages': pages})
        except Exception as e:
            logger.error('generate_power_of_attorney error: %s', e)
            from app import _safe_error
            return jsonify(_safe_error(e, 'generate_power_of_attorney')), 500
