#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VERSION: v4-signature-stamp
"""
generate_bg_withdraw.py — ใช้ template_utils shared module
═══════════════════════════════════════════════════════════
  1. POST /generate_bg_withdraw — หนังสือแจ้งขอถอนหลักประกันสัญญา
  2. POST /generate_bg_poa      — หนังสือมอบอำนาจขอคืนหนังสือค้ำประกัน

★ v4 — Digital Signature + Stamp (22/04/69):
  - เพิ่ม params: signatureKey, stampKey
  - ใช้ build_sig_closing_with_image() แทน sig_closing() เมื่อมี signature/stamp
  - Backward compatible 100% — ถ้าไม่ส่ง keys → ทำงานเหมือนเดิม
  - POA ยังใช้ sig_poa_line เดิม (4 ลายเซ็น: ผู้มอบ/ผู้รับ/พยาน 2 คน — ซับซ้อน, ทำภายหลัง)
"""

import base64, logging
from flask import request, jsonify
from template_utils import (
    merge_on_template, html_to_pdf, build_css, build_html,
    fmt, fmt_date_th, sig_closing, sig_poa_line, justify_html, nowrap_tokens
)

# ★ v4 — import signature/stamp helper
from signature_stamp import (
    build_sig_closing_with_image,
    validate_signature_key,
    validate_stamp_key,
    get_stamp_path,
    _img_to_base64_uri,
    STAMPS,
)

logger = logging.getLogger(__name__)


def _name(s):
    """ชื่อบริษัท / ชื่อบุคคล / ที่อยู่ ที่แทรกในย่อหน้า — escape แล้ว และไม่ถูกตัดกลางชื่อเมื่อขึ้นบรรทัดใหม่"""
    return nowrap_tokens(s)


def _esc(s):
    """HTML-escape — ชื่อบริษัท/ชื่อสัญญาที่มี & < > เดิมถูกใส่ลง HTML ตรง ๆ (ข้อความหายหรือผิดรูป)"""
    return (str('' if s is None else s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def _guard():
    """ตรวจ API key แบบเดียวกับ route อื่น (เดิมสอง route นี้ไม่ตรวจ ทั้งที่ใส่ลายเซ็น/ตราประทับได้)"""
    from app import _check_key
    return _check_key()


def _fail(e, context):
    from app import _safe_error
    return jsonify(_safe_error(e, context)), 500


def generate_bg_withdraw():
    try:
        err = _guard()
        if err:
            return err
        data       = request.get_json(force=True) or {}
        cid        = str(data.get('contractId', '') or '')
        cname      = _esc(data.get('contractName', '') or '')
        cdate      = _esc(data.get('signedDate', '') or '')
        co         = _esc(data.get('company', '') or '')
        bgn        = _esc(data.get('guaranteeNumber', '') or '')
        bgd        = _esc(fmt_date_th(str(data.get('guaranteeIssueDate', '') or '')))
        bgv        = _esc(fmt(data.get('guaranteeValue', '')))
        signer     = _esc(data.get('signerName', '') or '')
        spos       = _esc(data.get('signerPosition', 'Corporate Lawyers') or 'Corporate Lawyers')
        docnum_raw = str(data.get('docNumber', '') or cid)
        docnum     = _esc(docnum_raw)
        doc_date   = _esc(data.get('docDate', '') or '')
        entity     = data.get('entity') or {}
        ename      = _esc(entity.get('name', 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด'))
        eshort     = ename
        entity_key = str(data.get('entityKey', '') or '')

        # ★ v4 — รับ signature + stamp keys (optional)
        # ── signatureKey: เช่น 'pitichai' | None = ไม่ใส่
        # ── stampKey: เช่น 'scm_technologies' | None = ไม่ใส่
        sig_key   = str(data.get('signatureKey', '') or '').strip() or None
        stamp_key = str(data.get('stampKey', '') or '').strip() or None

        # Validate — ถ้า key ผิด → log warning แต่ไม่ fail (fallback = ไม่ใส่)
        sig_ok, sig_err = validate_signature_key(sig_key)
        if not sig_ok:
            logger.warning(f'bg_withdraw signature_key error: {sig_err}')
            sig_key = None
        stamp_ok, stamp_err = validate_stamp_key(stamp_key)
        if not stamp_ok:
            logger.warning(f'bg_withdraw stamp_key error: {stamp_err}')
            stamp_key = None

        # ── สร้าง body paragraphs ──
        ent_p = _name(entity.get('name', 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด'))
        co_p  = _name(data.get('company', '') or '')
        # ชื่อสัญญาที่ขึ้นต้นด้วย "สัญญา" อยู่แล้ว ไม่พิมพ์คำซ้ำ (เดิมได้ "ได้ทำสัญญาสัญญาจ้าง…")
        cname_p = cname[len('สัญญา'):] if cname.startswith('สัญญา') and len(cname) > len('สัญญา') else cname
        p1 = (f'ตามที่{ent_p} ได้ทำสัญญา{cname_p} '
              f'ฉบับเลขที่ {_esc(cid)} ลงวันที่ {cdate} กับ {co_p} นั้น')
        p2 = (f'บัดนี้{ent_p} ได้ทำงานสำเร็จเสร็จสิ้นเป็นที่เรียบร้อยแล้วตาม'
              f'สัญญาดังกล่าว บริษัทฯ จึงใคร่ขอคืนหนังสือค้ำประกันเลขที่ {bgn} '
              f'ลงวันที่ {bgd} มูลค่าค้ำประกัน {bgv} บาท')
        p3 = ('ทางบริษัทฯ หวังเป็นอย่างยิ่งว่าจะได้รับความกรุณาจากท่าน '
              'และขอบคุณล่วงหน้ามา ณ ที่นี้')

        custom_body = str(data.get('withdrawBody', '') or '').strip()
        if custom_body:
            paras = [_esc(p.strip()) for p in custom_body.split('\n') if p.strip()]
        else:
            paras = [p1, p2, p3]

        para_html = [f'  <p class="para">{justify_html(p)}</p>' for p in paras]

        # ★ v4 — เลือก sig closing: มี image หรือไม่?
        # ── ถ้ามี sig_key หรือ stamp_key → ใช้ build_sig_closing_with_image
        # ── ถ้าไม่ → ใช้ sig_closing เดิม (backward compat)
        if sig_key or stamp_key:
            sig_block = build_sig_closing_with_image(
                signer=signer,
                position=spos,
                signature_key=sig_key,
                stamp_key=stamp_key,
            )
        else:
            sig_block = sig_closing(signer, spos)

        # ย่อหน้าสุดท้าย + คำลงท้าย/ลายเซ็น อยู่หน้าเดียวกัน (ไม่มีหน้าลายเซ็นลำพัง)
        body_html = '\n'.join(para_html[:-1])
        tail_html = '<div class="keep-tail">\n' + para_html[-1] + '\n' + sig_block + '\n</div>'

        css = build_css(doc_number=docnum_raw)
        page = f"""<div class="page">
  <div class="doc-number">เลขที่ {docnum}</div>
  <div class="title">หนังสือแจ้งขอถอนหลักประกันสัญญา</div>
  <div class="written-at">เขียนที่ {ename}<br>วันที่ {doc_date}</div>
  <div class="subject-line"><span class="subject-label">เรื่อง</span><span class="subject-value">ขอถอนหลักประกันสัญญา</span></div>
  <div class="subject-line"><span class="subject-label">เรียน</span><span class="subject-value">{co}</span></div>
{body_html}
  {tail_html}
  <div class="clearfix"></div>
</div>"""

        final = merge_on_template(html_to_pdf(build_html(css, page)), entity_key)
        return jsonify({
            'success': True,
            'pdfBase64': base64.b64encode(final).decode(),
            'fileName': f'หนังสือขอถอนหลักประกัน_{cid.replace("/","-")}.pdf'
        })
    except Exception as e:
        return _fail(e, 'generate_bg_withdraw')


def generate_bg_poa():
    """หนังสือมอบอำนาจ

    ลงนามด้วยมือทั้ง 4 คน (ผู้มอบ/ผู้รับ/พยาน 2 คน) — ไม่มีภาพลายเซ็น
    stampKey (ถ้าส่งมา) = ตราประทับบริษัท วางข้างช่องลงนามผู้มอบอำนาจ
    ชื่อบุคคล/เลขบัตรฯ ไม่มีค่าเริ่มต้นในโค้ด — ไม่ส่งมา = เว้นว่างให้กรอก (หนังสือมอบอำนาจต้องไม่เติมตัวตนของใครเอง)
    """
    try:
        err = _guard()
        if err:
            return err
        data       = request.get_json(force=True) or {}
        cid        = str(data.get('contractId', '') or '')
        docnum_raw = str(data.get('docNumber', '') or cid)
        docnum     = _esc(docnum_raw)
        bgn        = _esc(data.get('guaranteeNumber', '') or '')
        bgv        = _esc(fmt(data.get('guaranteeValue', '')))
        co         = _esc(data.get('company', '') or '')
        doc_date   = _esc(data.get('docDate', '') or '')
        entity     = data.get('entity') or {}
        grantor    = data.get('grantor') or {}
        grantee    = data.get('grantee') or {}
        witnesses  = [w if isinstance(w, dict) else {} for w in (data.get('witnesses') or [])]
        entity_key = str(data.get('entityKey', '') or '')
        while len(witnesses) < 2:
            witnesses.append({})

        ename   = _esc(entity.get('name', 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด'))
        eshort  = ename
        eaddr   = _esc(entity.get('address',
            'ตั้งอยู่เลขที่ 92/54-55 อาคารสาธรธานี 2 ชั้น 19 ถนนสาทรเหนือ '
            'แขวงสีลม เขตบางรัก กรุงเทพมหานคร'))
        gr_name = _esc(grantor.get('name', '') or '')
        gr_id   = _esc(grantor.get('idCard', '') or '')
        ge_name = _esc(grantee.get('name', '') or '')
        ge_id   = _esc(grantee.get('idCard', '') or '')
        ge_addr = _esc(grantee.get('address', '') or '')
        w1      = _esc(witnesses[0].get('name', '') or '')
        w2      = _esc(witnesses[1].get('name', '') or '')

        # ตราประทับ (ไม่บังคับ) — เดิม GAS ส่ง stampKey มาแต่ route นี้ไม่ได้อ่าน ตัวเลือก "ใส่ตราประทับ" จึงไม่มีผล
        stamp_key = str(data.get('stampKey', '') or '').strip() or None
        stamp_ok, stamp_err = validate_stamp_key(stamp_key)
        if not stamp_ok:
            logger.warning(f'bg_poa stamp_key error: {stamp_err}')
            stamp_key = None
        stamp_html = ''
        if stamp_key:
            uri = _img_to_base64_uri(get_stamp_path(stamp_key) or '')
            if uri:
                w_mm = min(int(STAMPS.get(stamp_key, {}).get('width_mm', 60)), 55)
                stamp_html = f'<img src="{uri}" style="width:{w_mm}mm; height:auto" alt="company stamp"/>'

        addr_part = f'ที่อยู่ {_name(grantee.get("address", "") or "")} ' if ge_addr else ''
        ent_p   = _name(entity.get('name', 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด'))
        eaddr_p = _name(entity.get('address',
            'ตั้งอยู่เลขที่ 92/54-55 อาคารสาธรธานี 2 ชั้น 19 ถนนสาทรเหนือ '
            'แขวงสีลม เขตบางรัก กรุงเทพมหานคร'))
        body_default = (
            f'โดยหนังสือฉบับนี้ ข้าพเจ้า {ent_p} {eaddr_p} '
            f'โดย {_name(grantor.get("name", "") or "")} บัตรประชาชนเลขที่ {gr_id} '
            f'ผู้มีอำนาจกระทำนิติกรรมตามหนังสือรับรองของสำนักงานทะเบียน'
            f'หุ้นส่วนบริษัทกลางกรมพัฒนาธุรกิจการค้า กระทรวงพาณิชย์ '
            f'ขอมอบอำนาจให้ {_name(grantee.get("name", "") or "")} ผู้ถือบัตรประชาชนเลขที่ {ge_id} '
            f'{addr_part}'
            f'เป็นผู้มีอำนาจดำเนินการรับคืนหนังสือค้ำประกันเลขที่ {bgn} '
            f'มูลค่า {bgv} บาท กับ {_name(data.get("company", "") or "")}')
        p2_default = (
            'การกระทำใดๆ ที่ผู้รับมอบอำนาจได้กระทำไป เปรียบเสมือนข้าพเจ้าได้กระทำทุกประการ '
            'จึงลงลายมือชื่อไว้ต่อหน้าพยานทั้ง 2 คน และให้พยานลงลายมือชื่อไว้เป็นหลักฐาน '
            'พร้อมทั้งแนบสำเนาบัตรประจำตัวประชาชนของข้าพเจ้าและผู้รับมอบอำนาจมานี้ด้วย')

        custom_poa = str(data.get('poaBody', '') or '').strip()
        if custom_poa:
            poa_paras = [_esc(p.strip()) for p in custom_poa.split('\n') if p.strip()]
        else:
            poa_paras = [body_default, p2_default]

        poa_html = [f'  <p class="para">{justify_html(p)}</p>' for p in poa_paras]
        poa_body = '\n'.join(poa_html[:-1])
        sigs = '\n'.join([
            sig_poa_line('ผู้มอบอำนาจ', gr_name),
            sig_poa_line('ผู้รับมอบอำนาจ', ge_name),
            sig_poa_line('พยาน', w1),
            sig_poa_line('พยาน', w2),
        ])

        # ช่องลงนามอยู่ต่อจากข้อความตามปกติ ไม่ถูกตัดข้ามหน้า และอยู่หน้าเดียวกับย่อหน้าสุดท้ายเสมอ
        # (เดิมตรึงไว้ท้ายหน้าด้วย position:absolute + ซ่อนส่วนที่ล้น — ข้อความยาวจะถูกลายเซ็นทับ/หายไป)
        css = build_css(doc_number=docnum_raw)
        page = f"""<div class="page">
  {'<div class="doc-number">เลขที่ ' + docnum + '</div>' if docnum else ''}
  <div class="title">หนังสือมอบอำนาจ</div>
  <div class="written-at">ทำที่ {ename}<br>วันที่ {doc_date}</div>
{poa_body}
  <div class="keep-tail">
{poa_html[-1]}
  <table class="poa-sign"><tr>
    <td style="width:45%; vertical-align:top; text-align:center; padding-top:4mm">{stamp_html}</td>
    <td style="width:55%" rowspan="2"><div class="sig-col">{sigs}</div></td>
  </tr><tr>
    <td style="width:45%"><div class="stamp">ติดอากรแสตมป์ 10 บาท</div></td>
  </tr></table>
  </div>
</div>"""

        final = merge_on_template(html_to_pdf(build_html(css, page)), entity_key)
        return jsonify({
            'success': True,
            'pdfBase64': base64.b64encode(final).decode(),
            'fileName': f'หนังสือมอบอำนาจ_{cid.replace("/","-")}.pdf'
        })
    except Exception as e:
        return _fail(e, 'generate_bg_poa')


def register_bg_withdraw_routes(app):
    app.add_url_rule('/generate_bg_withdraw', 'generate_bg_withdraw',
                     generate_bg_withdraw, methods=['POST'])
    app.add_url_rule('/generate_bg_poa', 'generate_bg_poa',
                     generate_bg_poa, methods=['POST'])
