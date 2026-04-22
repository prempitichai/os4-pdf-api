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
    fmt, fmt_date_th, sig_closing, sig_poa_line
)

# ★ v4 — import signature/stamp helper
from signature_stamp import (
    build_sig_closing_with_image,
    validate_signature_key,
    validate_stamp_key,
)

logger = logging.getLogger(__name__)


def generate_bg_withdraw():
    try:
        data       = request.get_json(force=True) or {}
        cid        = str(data.get('contractId', '') or '')
        cname      = str(data.get('contractName', '') or '')
        cdate      = str(data.get('signedDate', '') or '')
        co         = str(data.get('company', '') or '')
        bgn        = str(data.get('guaranteeNumber', '') or '')
        bgd        = fmt_date_th(str(data.get('guaranteeIssueDate', '') or ''))
        bgv        = fmt(data.get('guaranteeValue', ''))
        signer     = str(data.get('signerName', '') or '')
        spos       = str(data.get('signerPosition', 'Corporate Lawyers') or 'Corporate Lawyers')
        docnum     = str(data.get('docNumber', '') or cid)
        doc_date   = str(data.get('docDate', '') or '')
        entity     = data.get('entity') or {}
        ename      = entity.get('name', 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด')
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
        p1 = (f'ตามที่{eshort} ได้ทำสัญญา{cname} '
              f'ฉบับเลขที่ {cid} ลงวันที่ {cdate} กับ {co} นั้น')
        p2 = (f'บัดนี้{eshort} ได้ทำงานสำเร็จเสร็จสิ้นเป็นที่เรียบร้อยแล้วตาม'
              f'สัญญาดังกล่าว บริษัทฯ จึงใคร่ขอคืนหนังสือค้ำประกันเลขที่ {bgn} '
              f'ลงวันที่ {bgd} มูลค่าค้ำประกัน {bgv} บาท')
        p3 = ('ทางบริษัทฯ หวังเป็นอย่างยิ่งว่าจะได้รับความกรุณาจากท่าน '
              'และขอบคุณล่วงหน้ามา ณ ที่นี้')

        custom_body = str(data.get('withdrawBody', '') or '').strip()
        if custom_body:
            paras = [p.strip() for p in custom_body.split('\n') if p.strip()]
        else:
            paras = [p1, p2, p3]

        body_html = '\n'.join(f'  <p class="para">{p}</p>' for p in paras)

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

        css = build_css()
        page = f"""<div class="page">
  <div class="doc-number">เลขที่ {docnum}</div>
  <div class="title">หนังสือแจ้งขอถอนหลักประกันสัญญา</div>
  <div class="written-at">เขียนที่ {ename}<br>วันที่ {doc_date}</div>
  <div class="subject-line"><span class="subject-label">เรื่อง</span><span class="subject-value">ขอถอนหลักประกันสัญญา</span></div>
  <div class="subject-line"><span class="subject-label">เรียน</span><span class="subject-value">{co}</span></div>
{body_html}
  {sig_block}
  <div class="clearfix"></div>
</div>"""

        final = merge_on_template(html_to_pdf(build_html(css, page)), entity_key)
        return jsonify({
            'success': True,
            'pdfBase64': base64.b64encode(final).decode(),
            'fileName': f'หนังสือขอถอนหลักประกัน_{cid.replace("/","-")}.pdf'
        })
    except Exception as e:
        logger.error(f'bg_withdraw error: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500


def generate_bg_poa():
    """หนังสือมอบอำนาจ

    ★ v4 Note: POA มี 4 ลายเซ็น (ผู้มอบ/ผู้รับ/พยาน 2 คน)
              ยังไม่ implement signature image สำหรับ POA ในเวอร์ชันนี้
              (ซับซ้อน — ต้อง handle multiple signers)
              สำหรับ POC ขอทำแค่ BG Withdraw ก่อน
    """
    try:
        data       = request.get_json(force=True) or {}
        cid        = str(data.get('contractId', '') or '')
        docnum     = str(data.get('docNumber', '') or cid)
        bgn        = str(data.get('guaranteeNumber', '') or '')
        bgv        = fmt(data.get('guaranteeValue', ''))
        co         = str(data.get('company', '') or '')
        doc_date   = str(data.get('docDate', '') or '')
        entity     = data.get('entity') or {}
        grantor    = data.get('grantor') or {}
        grantee    = data.get('grantee') or {}
        witnesses  = data.get('witnesses') or [{}, {}]
        entity_key = str(data.get('entityKey', '') or '')
        while len(witnesses) < 2:
            witnesses.append({})

        ename   = entity.get('name', 'บริษัท เอส ซี เอ็ม เทคโนโลจีส์ จำกัด')
        eshort  = ename
        eaddr   = entity.get('address',
            'ตั้งอยู่เลขที่ 92/54-55 อาคารสาธรธานี 2 ชั้น 19 ถนนสาทรเหนือ '
            'แขวงสีลม เขตบางรัก กรุงเทพมหานคร')
        gr_name = str(grantor.get('name', 'นายบัณฑิต หมั้นทรัพย์') or '')
        gr_id   = str(grantor.get('idCard', '3101201187013') or '')
        ge_name = str(grantee.get('name', '') or '')
        ge_id   = str(grantee.get('idCard', '') or '')
        ge_addr = str(grantee.get('address', '') or '')
        w1      = str(witnesses[0].get('name', 'นายปิติชัย พัฒนกิจกุล') or '')
        w2      = str(witnesses[1].get('name', 'นางสาวสิริกาญจนา จันทร์อ่อน') or '')

        addr_part = f'ที่อยู่ {ge_addr} ' if ge_addr else ''
        body_default = (
            f'โดยหนังสือฉบับนี้ ข้าพเจ้า {eshort} {eaddr} '
            f'โดย {gr_name} บัตรประชาชนเลขที่ {gr_id} '
            f'ผู้มีอำนาจกระทำนิติกรรมตามหนังสือรับรองของสำนักงานทะเบียน'
            f'หุ้นส่วนบริษัทกลางกรมพัฒนาธุรกิจการค้า กระทรวงพาณิชย์ '
            f'ขอมอบอำนาจให้ {ge_name} ผู้ถือบัตรประชาชนเลขที่ {ge_id} '
            f'{addr_part}'
            f'เป็นผู้มีอำนาจดำเนินการรับคืนหนังสือค้ำประกันเลขที่ {bgn} '
            f'มูลค่า {bgv} บาท กับ {co}')
        p2_default = (
            'การกระทำใดๆ ที่ผู้รับมอบอำนาจได้กระทำไป เปรียบเสมือนข้าพเจ้าได้กระทำทุกประการ '
            'จึงลงลายมือชื่อไว้ต่อหน้าพยานทั้ง 2 คน และให้พยานลงลายมือชื่อไว้เป็นหลักฐาน '
            'พร้อมทั้งแนบสำเนาบัตรประจำตัวประชาชนของข้าพเจ้าและผู้รับมอบอำนาจมานี้ด้วย')

        custom_poa = str(data.get('poaBody', '') or '').strip()
        if custom_poa:
            poa_paras = [p.strip() for p in custom_poa.split('\n') if p.strip()]
        else:
            poa_paras = [body_default, p2_default]

        poa_body = '\n'.join(f'  <p class="para">{p}</p>' for p in poa_paras)
        sigs = '\n'.join([
            sig_poa_line('ผู้มอบอำนาจ', gr_name),
            sig_poa_line('ผู้รับมอบอำนาจ', ge_name),
            sig_poa_line('พยาน', w1),
            sig_poa_line('พยาน', w2),
        ])

        css = build_css()
        page = f"""<div class="page">
  {'<div class="doc-number">เลขที่ ' + docnum + '</div>' if docnum else ''}
  <div class="title">หนังสือมอบอำนาจ</div>
  <div class="written-at">ทำที่ {ename}<br>วันที่ {doc_date}</div>
{poa_body}
  <div class="sig-col">{sigs}</div>
  <div class="stamp">ติดอากรแสตมป์ 10 บาท</div>
</div>"""

        final = merge_on_template(html_to_pdf(build_html(css, page)), entity_key)
        return jsonify({
            'success': True,
            'pdfBase64': base64.b64encode(final).decode(),
            'fileName': f'หนังสือมอบอำนาจ_{cid.replace("/","-")}.pdf'
        })
    except Exception as e:
        logger.error(f'bg_poa error: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500


def register_bg_withdraw_routes(app):
    app.add_url_rule('/generate_bg_withdraw', 'generate_bg_withdraw',
                     generate_bg_withdraw, methods=['POST'])
    app.add_url_rule('/generate_bg_poa', 'generate_bg_poa',
                     generate_bg_poa, methods=['POST'])
