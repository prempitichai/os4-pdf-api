#!/usr/bin/env python3
"""
OS4 PDF API Server — deploy บน Render
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Endpoints:
  POST /generate            → อ.ส.4 stamp duty
  POST /generate_bg_delivery → BG Delivery Form
  POST /generate_lg          → Request Approve LG      ★ NEW
  POST /generate_pettycash   → Petty Cash               ★ NEW
  GET  /health              → health check
"""
import os, json, base64, math
from io import BytesIO
from flask import Flask, request, jsonify
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter
from generate_lg_pettycash import generate_lg_pdf, generate_pettycash_pdf

app = Flask(__name__)

# ============================================================
# FONT
# ============================================================
THAI_FONT = 'FreeSerif'
for fp in ['/usr/share/fonts/truetype/freefont/FreeSerif.ttf', './fonts/FreeSerif.ttf', '/app/fonts/FreeSerif.ttf']:
    if os.path.exists(fp):
        pdfmetrics.registerFont(TTFont(THAI_FONT, fp)); break

# ============================================================
# CONFIG
# ============================================================
TEMPLATE_PATH = os.environ.get('OS4_TEMPLATE', './os4_blank.pdf')
API_KEY = os.environ.get('OS4_API_KEY', '')

def _check_key():
    """ตรวจ API Key — return error response ถ้าไม่ผ่าน, None ถ้า OK"""
    if API_KEY and request.headers.get('X-API-Key', '') != API_KEY:
        return jsonify({'success': False, 'message': 'Invalid API key'}), 401
    return None


# ════════════════════════════════════════════════════════════
# 1. อ.ส.4 STAMP DUTY
# ════════════════════════════════════════════════════════════

TIN_C = [145.9,162.6,173.7,184.7,195.8,212.3,223.4,234.5,245.6,256.7,273.5,284.7,301.2]
BR_C = [352.3,364.3,376.3,388.2,400.3]
ZIP_C = [364.9,376.9,389.0,401.0,413.1]

def build_fields(d):
    fields = []
    def add(x, yt, text, fs=9, cen=False):
        if text and str(text).strip(): fields.append({'x':x,'y_top':yt,'text':str(text),'fs':fs,'centered':cen})
    def digits(s, centers, yt, fs=9):
        s = str(s or '').replace(' ','').replace('-','')
        for i, c in enumerate(s[:len(centers)]): add(centers[i], yt, c, fs, True)

    add(175,87,d.get('branchOffice','')); add(410,87,d.get('day','')); add(470,87,d.get('month','')); add(548,87,d.get('year',''))
    add(96,104,d.get('taxpayerName',''))
    digits(d.get('taxpayerTIN',''), TIN_C, 119); digits(d.get('taxpayerBranch','00000'), BR_C, 119)
    ta = d.get('tAddr', d.get('taxpayerAddr', {}))
    add(85,138,ta.get('building','-'),8); add(239,138,ta.get('room','-'),8); add(314,138,ta.get('floor','-'),8)
    add(363,138,ta.get('village','-'),8); add(482,138,ta.get('number','-'),8); add(543,138,ta.get('moo','-'),8)
    add(80,157,ta.get('soi','-'),8); add(210,157,ta.get('yaek','-'),8); add(310,157,ta.get('road','-'),8); add(465,157,ta.get('subDistrict','-'),8)
    add(90,172,ta.get('district','-'),8); add(240,172,ta.get('province','-'),8); digits(ta.get('zip',''), ZIP_C, 170, 8)

    add(96,190,d.get('counterpartyName',''))
    digits(d.get('counterpartyTIN',''), TIN_C, 213); digits(d.get('counterpartyBranch','00000'), BR_C, 213)
    ca = d.get('cpAddr', d.get('counterpartyAddr', {}))
    add(85,232,ca.get('building','-'),8); add(239,232,ca.get('room','-'),8); add(314,232,ca.get('floor','-'),8)
    add(363,232,ca.get('village','-'),8); add(482,232,ca.get('number','-'),8); add(543,232,ca.get('moo','-'),8)
    add(80,249,ca.get('soi','-'),8); add(210,249,ca.get('yaek','-'),8); add(310,249,ca.get('road','-'),8); add(465,249,ca.get('subDistrict','-'),8)
    add(90,266,ca.get('district','-'),8); add(240,266,ca.get('province','-'),8); digits(ca.get('zip',''), ZIP_C, 264, 8)

    ct = d.get('contractType','hire')
    if ct=='hire': add(152,282,'X',9,True)
    if ct=='lease': add(215,282,'X',9,True)
    if ct=='other': add(279,282,'X',9,True); add(340,282,d.get('contractTypeOther',''),8)
    add(92,298,d.get('contractNo','')); add(445,298,d.get('contractDate',''))
    add(140,315,d.get('startDate','')); add(150,330,d.get('endDate',''))

    desc = 'จ้างทำของ' if ct=='hire' else 'เช่าทรัพย์สิน' if ct=='lease' else d.get('contractTypeOther','')
    clause = d.get('stampClause','4' if ct=='hire' else '1')
    val = d.get('instrumentValue','')
    dutyAmt = d.get('stampDutyAmount','')
    if not dutyAmt and val:
        try: dutyAmt = f'{math.ceil(float(str(val).replace(",",""))/1000):,}'
        except: pass
    rate = d.get('stampRate',''); sur = d.get('surcharge','-'); tot = d.get('totalDuty',dutyAmt)

    add(43,540,'1',8,True); add(65,540,clause,8,True); add(85,540,desc,8); add(192,540,'1',8,True)
    add(220,540,val,8); add(280,540,'00',8,True)
    add(314,540,rate,7,True); add(368,540,dutyAmt,7); add(407,540,'00',7,True)
    add(446,540,sur,7); add(485,540,'00',7,True); add(524,540,tot,7); add(564,540,'00',7,True)
    add(220,608,val,8); add(280,608,'00',8,True)
    add(368,608,dutyAmt,7); add(407,608,'00',7,True); add(446,608,sur,7); add(485,608,'00',7,True)
    add(524,608,tot,7); add(564,608,'00',7,True)

    sub = d.get('submittedInstrument',True)
    if sub: add(44,628,'X',9,True)
    else: add(44,644,'X',9,True); add(230,646,d.get('notSubmittedReason',''),8)
    add(325,683,d.get('signerName','')); add(320,703,d.get('signerName',''),8); add(330,719,d.get('signerPosition',''))
    return fields


def create_pdf(data):
    fields = build_fields(data)
    reader = PdfReader(TEMPLATE_PATH)
    page = reader.pages[0]
    pw, ph = float(page.mediabox.width), float(page.mediabox.height)
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(pw, ph))
    for f in fields:
        fs = f['fs']; c.setFont(THAI_FONT, fs)
        y = ph - f['y_top'] - fs + (3 if f.get('centered') else 6)
        if f.get('centered'): c.drawCentredString(f['x'], y, f['text'])
        else: c.drawString(f['x']+2, y, f['text'])
    c.save(); packet.seek(0)
    overlay = PdfReader(packet).pages[0]
    writer = PdfWriter()
    page.merge_page(overlay); writer.add_page(page)
    out = BytesIO(); writer.write(out)
    return out.getvalue()


@app.route('/health')
def health():
    return jsonify({'status':'ok','template_exists':os.path.exists(TEMPLATE_PATH)})


@app.route('/generate', methods=['POST'])
def generate():
    try:
        err = _check_key()
        if err: return err
        data = request.get_json()
        if not data: return jsonify({'success':False,'message':'No JSON body'}), 400
        pdf_bytes = create_pdf(data)
        return jsonify({
            'success': True,
            'pdfBase64': base64.b64encode(pdf_bytes).decode(),
            'fileName': f"OS4_{data.get('contractNo','draft').replace('/','_')}.pdf"
        })
    except Exception as e:
        return jsonify({'success':False,'message':str(e)}), 500


# ════════════════════════════════════════════════════════════
# 2. BG DELIVERY FORM
# ════════════════════════════════════════════════════════════
from reportlab.lib.pagesizes import landscape as _landscape
from reportlab.lib.colors import HexColor as _HC, white, black

_BLUE=_HC('#1a3a7a');_TEAL=_HC('#0a7a6e');_PURPLE=_HC('#6a3a9a')
_GRAY=_HC('#555555');_LGRAY=_HC('#999999');_BORDER=_HC('#bbbbbb')
_FIELD_BG=_HC('#f7f9fc');_FIELD_BD=_HC('#d0d5dd')
_W=white;_B=black;_TF=THAI_FONT

def _bg_chk(c,x,y,on,sz=9):
    c.setLineWidth(1)
    if on:
        c.setStrokeColor(_BLUE);c.setFillColor(_HC('#e0e8f8'))
        c.rect(x,y,sz,sz,fill=1,stroke=1);c.setFillColor(_BLUE);c.setFont(_TF,7)
        c.drawCentredString(x+sz/2,y+1.5,'✓')
    else:
        c.setStrokeColor(_BORDER);c.setFillColor(_W);c.rect(x,y,sz,sz,fill=1,stroke=1)
    c.setFillColor(_B)

def _bg_field(c,x,y,w,h,text='',fs=8):
    c.setStrokeColor(_FIELD_BD);c.setFillColor(_FIELD_BG);c.setLineWidth(0.5)
    c.roundRect(x,y,w,h,2,fill=1,stroke=1)
    if text:
        c.setFillColor(_B);c.setFont(_TF,fs)
        t=str(text)
        while c.stringWidth(t,_TF,fs)>w-6 and len(t)>1: t=t[:-1]
        c.drawString(x+3,y+(h-fs)/2,t)
    c.setFillColor(_B)

def _bg_label(c,x,y,text,fs=7.5):
    c.setFont(_TF,fs);c.setFillColor(_GRAY);c.drawString(x,y,text);c.setFillColor(_B)

def _bg_section(c,x,y,w,text,fs=10):
    c.setStrokeColor(_BLUE);c.setLineWidth(2);c.line(x,y+2,x,y-12)
    c.setFont(_TF,fs);c.setFillColor(_BLUE);c.drawString(x+8,y-9,text)
    c.setStrokeColor(_HC('#dde2ea'));c.setLineWidth(0.5);c.line(x,y-14,x+w,y-14)
    c.setFillColor(_B);return y-22

def _bg_sign(c,x,y,title,w=155,h=55):
    c.setStrokeColor(_HC('#c0c8d8'));c.setLineWidth(0.8);c.setDash(4,3)
    c.roundRect(x,y,w,h,4);c.setDash()
    c.setFont(_TF,7.5);c.setFillColor(_GRAY);c.drawCentredString(x+w/2,y+h-12,title)
    c.setStrokeColor(_HC('#b0b8c8'));c.setLineWidth(0.5)
    c.line(x+15,y+h/2-2,x+w-15,y+h/2-2)
    c.setFont(_TF,6.5);c.setFillColor(_LGRAY)
    c.drawCentredString(x+w/2,y+h/2-14,'(                                               )')
    c.drawCentredString(x+w/2,y+h/2-24,'วันที่ ........./................/...........')
    c.setFillColor(_B)

def _create_bg_delivery_pdf(d):
    from reportlab.lib.pagesizes import A4
    A4W,A4H=A4;LW,LH=_landscape(A4)
    buf=BytesIO();c=canvas.Canvas(buf)
    sn=d.get('senderName','');sc=d.get('senderCompany','');sp=d.get('senderPhone','')
    rn=d.get('receiverName','');rc=d.get('receiverCompany','');rp=d.get('receiverPhone','')
    cno=d.get('contractNo','');cnm=d.get('contractName','')
    dt=d.get('docTypeText','หนังสือค้ำประกันสัญญา')
    bgn=d.get('bgNumber','');isd=d.get('issueDate','');bgv=d.get('bgValue','')
    bge=d.get('bgExpiry','');cpy=d.get('counterparty','');po=d.get('poNumber','')
    own=d.get('projectOwner','');bnk=d.get('bankName','ธนาคารกสิกรไทย')
    bbr=d.get('bankBranch','สาขานราธิวาสราชนครินทร์')
    chd=d.get('companyForHeader','บจก. เอส ซีเอ็ม เทคโนโลจีส์')
    gcat=d.get('guaranteeCategory','contract');ptype=d.get('paymentType','bank_lg')
    td=d.get('thaiDay','');tm=d.get('thaiMonth','');tyr=d.get('thaiYear','')
    ib=gcat=='bid';ic=gcat=='contract';ii=gcat=='insurance'

    # ═══ หน้า 1 LANDSCAPE ═══
    c.setPageSize(_landscape(A4));pw,ph=LW,LH;mx=35;mr=pw-35
    c.setFont(_TF,16);c.setFillColor(_BLUE)
    c.drawCentredString(pw/2,ph-38,'แบบฟอร์มนำส่งหนังสือค้ำประกัน')
    c.setFont(_TF,9);c.setFillColor(_LGRAY)
    c.drawCentredString(pw/2,ph-52,'กรมธรรม์ประกันภัย / Bank Guarantee Delivery Form')
    c.setStrokeColor(_BLUE);c.setLineWidth(1.5);c.line(pw/2-140,ph-58,pw/2+140,ph-58)

    y=_bg_section(c,mx,ph-72,mr-mx,'ส่วนที่ 1 — ผู้นำส่งเอกสาร / ผู้รับเอกสาร')
    half=(mr-mx)/2-10;lx=mx;rx=mx+half+20;rh=15;g=5;lw=32
    c.setFont(_TF,8);c.setFillColor(_TEAL);c.drawString(lx+5,y,'▸  ผู้นำส่งเอกสาร')
    c.setFillColor(_BLUE);c.drawString(rx+5,y,'▸  ผู้รับเอกสาร')
    for i,(lb,vl,vr) in enumerate([('ชื่อ',sn,rn),('บริษัท',sc,rc),('โทร',sp,rp)]):
        fy=y-16-i*(rh+g)
        _bg_label(c,lx+5,fy+3,lb);_bg_field(c,lx+lw+10,fy,half-lw-15,rh,vl,7.5)
        _bg_label(c,rx+5,fy+3,lb);_bg_field(c,rx+lw+10,fy,half-lw-15,rh,vr,7.5)

    ty=y-16-3*(rh+g)-6;ty=_bg_section(c,mx,ty,mr-mx,'ส่วนที่ 2 — ข้อมูลจัดเก็บเอกสาร')
    hds=['#','เลขที่สัญญา','ชื่อสัญญา','ประเภทเอกสาร','เลขที่เอกสาร','ลงวันที่','จำนวนเงิน (บาท)','วันครบกำหนด','คู่สัญญา','เลขที่ PO','Project Owner']
    cw=[22,68,148,58,62,52,68,56,125,58,56];tw=sum(cw);tx=mx;thh=16;tdh=40
    c.setFillColor(_BLUE);c.rect(tx,ty-thh,tw,thh,fill=1)
    c.setFillColor(_W);c.setFont(_TF,6);cx_=tx
    for i,ht in enumerate(hds): c.drawCentredString(cx_+cw[i]/2,ty-thh+4,ht);cx_+=cw[i]
    c.setStrokeColor(_BORDER);c.setLineWidth(0.4);c.setFillColor(_W)
    c.rect(tx,ty-thh-tdh,tw,tdh,fill=1,stroke=1)
    cx_=tx
    for w in cw[:-1]: cx_+=w;c.line(cx_,ty-thh,cx_,ty-thh-tdh)
    vs=['1',cno,cnm,dt,bgn,isd,bgv,bge,cpy,po,own]
    c.setFont(_TF,7);c.setFillColor(_B);cx_=tx
    for i,v in enumerate(vs):
        t=str(v or '');cwd=cw[i]-4;ls=[]
        while t:
            f=t
            while c.stringWidth(f,_TF,7)>cwd and len(f)>1:f=f[:-1]
            ls.append(f);t=t[len(f):]
            if len(ls)>=4:break
        for li,ln in enumerate(ls):c.drawString(cx_+2,ty-thh-10-li*8,ln)
        cx_+=cw[i]

    sy=ty-thh-tdh-6;sy=_bg_section(c,mx,sy,mr-mx,'ส่วนที่ 3 — สำหรับเจ้าหน้าที่รับเอกสาร')
    _bg_label(c,mx+10,sy,'ข้าพเจ้าตรวจสอบรายละเอียดแล้ว ถูกต้องครบถ้วน',8)
    sx=pw/2-175;_bg_sign(c,sx,sy-68,'ลงนามผู้นำส่ง');_bg_sign(c,sx+190,sy-68,'ลงนามผู้รับเอกสาร')
    c.showPage()

    # ═══ หน้า 2 PORTRAIT ═══
    c.setPageSize(A4);pw2,ph2=A4W,A4H;m2=35;fw=pw2-70;bw=155
    sh=280;st=ph2-25;sb=st-sh;rg=15;rh2=255;rt=sb-rg;rb=rt-rh2

    c.setStrokeColor(_TEAL);c.setLineWidth(2);c.rect(m2,sb,fw,sh)
    c.setFillColor(_TEAL);c.rect(pw2/2-bw/2,st-8,bw,16,fill=1)
    c.setFillColor(_W);c.setFont(_TF,10);c.drawCentredString(pw2/2,st-5,'แบบส่งหลักประกัน');c.setFillColor(_B)
    cy=st-28
    _bg_label(c,m2+10,cy,'วันที่');_bg_field(c,m2+42,cy-3,30,14,td,9)
    _bg_label(c,m2+80,cy,'เดือน');_bg_field(c,m2+110,cy-3,65,14,tm,9)
    _bg_label(c,m2+183,cy,'พ.ศ.');_bg_field(c,m2+205,cy-3,42,14,tyr,9)
    cy-=20;st_=sc or cpy;c.setFont(_TF,9);c.setFillColor(_B);c.drawString(m2+10,cy,st_)
    c.setFillColor(_TEAL);c.drawString(m2+10+c.stringWidth(st_,_TF,9)+5,cy,'ได้ส่ง')
    cy-=18;_bg_chk(c,m2+10,cy,ib);c.setFont(_TF,8);c.setFillColor(_B)
    c.drawString(m2+22,cy+1,'หลักประกันซอง');_bg_chk(c,m2+110,cy,ic);c.drawString(m2+122,cy+1,'หลักประกันสัญญา')
    _bg_chk(c,m2+230,cy,ii);c.drawString(m2+242,cy+1,'เอกสารประกันภัย');c.setFont(_TF,7.5);c.drawString(m2+325,cy+1,'ของ '+chd)
    cy-=20;_bg_label(c,m2+10,cy+3,'สำหรับโครงการ');_bg_field(c,m2+85,cy-1,225,15,cnm,7)
    _bg_label(c,m2+318,cy+3,'เลขที่สัญญา');_bg_field(c,m2+385,cy-1,fw-395,15,cno,7)
    cy-=18;_bg_chk(c,m2+10,cy,ptype=='cash');c.setFont(_TF,8);c.setFillColor(_B)
    c.drawString(m2+22,cy+1,'เงินสด');_bg_chk(c,m2+80,cy,ptype=='bond');c.drawString(m2+92,cy+1,'พันธบัตรรัฐบาลไทย')
    _bg_chk(c,m2+210,cy,ptype=='cheque');c.drawString(m2+222,cy+1,'แคชเชียร์เช็ค')
    cy-=15;_bg_chk(c,m2+10,cy,ptype=='bank_lg');c.setFillColor(_B)
    c.drawString(m2+22,cy+1,'หนังสือค้ำประกันของธนาคารภายในประเทศ')
    _bg_chk(c,m2+270,cy,ptype=='car_insurance');c.drawString(m2+282,cy+1,'กรมธรรม์ประกันภัย CAR & PL')
    cy-=18;_bg_label(c,m2+10,cy+3,'ชื่อธนาคาร/บริษัท');_bg_field(c,m2+98,cy-1,185,15,bnk,8)
    _bg_label(c,m2+292,cy+3,'สาขา');_bg_field(c,m2+318,cy-1,fw-328,15,bbr,7)
    cy-=18;_bg_label(c,m2+10,cy+3,'เลขที่');_bg_field(c,m2+42,cy-1,135,15,bgn,8)
    _bg_label(c,m2+186,cy+3,'จำนวน');_bg_field(c,m2+218,cy-1,110,15,bgv,8)
    c.setFont(_TF,6);c.setFillColor(_LGRAY);c.drawString(m2+338,cy+3,'ครบถ้วนถูกต้องเรียบร้อย')
    _bg_sign(c,pw2/2-78,cy-62,'ลงชื่อผู้ส่งหลักประกัน',155,50)

    c.setStrokeColor(_PURPLE);c.setLineWidth(2);c.rect(m2,rb,fw,rh2)
    c.setFillColor(_PURPLE);c.rect(pw2/2-bw/2,rt-8,bw,16,fill=1)
    c.setFillColor(_W);c.setFont(_TF,10);c.drawCentredString(pw2/2,rt-5,'แบบคืนหลักประกัน');c.setFillColor(_B)
    cy2=rt-28;c.setFont(_TF,9);c.drawString(m2+10,cy2,chd)
    c.setFillColor(_PURPLE);c.drawString(m2+10+c.stringWidth(chd,_TF,9)+5,cy2,'ได้คืน')
    cy2-=18
    for lb,cv in [('หลักประกันซอง',ib),('หลักประกันสัญญา',ic),('เอกสารประกันภัย',ii)]:
        _bg_chk(c,m2+10,cy2,cv);c.setFont(_TF,8);c.setFillColor(_B);c.drawString(m2+22,cy2+1,lb+'  ของ  '+cpy);cy2-=15
    cy2-=4;_bg_chk(c,m2+10,cy2,ptype=='cash');c.setFont(_TF,8);c.setFillColor(_B)
    c.drawString(m2+22,cy2+1,'เงินสด');_bg_chk(c,m2+80,cy2,ptype=='bond');c.drawString(m2+92,cy2+1,'พันธบัตรรัฐบาลไทย')
    _bg_chk(c,m2+210,cy2,ptype=='cheque');c.drawString(m2+222,cy2+1,'แคชเชียร์เช็ค')
    cy2-=15;_bg_chk(c,m2+10,cy2,ptype=='bank_lg');c.setFillColor(_B)
    c.drawString(m2+22,cy2+1,'หนังสือค้ำประกันของธนาคารภายในประเทศ')
    _bg_chk(c,m2+270,cy2,ptype=='car_insurance');c.drawString(m2+282,cy2+1,'กรมธรรม์ประกันภัย CAR & PL')
    cy2-=18;_bg_label(c,m2+10,cy2+3,'ชื่อธนาคาร/บริษัท');_bg_field(c,m2+98,cy2-1,fw-108,15,bnk,8)
    cy2-=17;_bg_label(c,m2+10,cy2+3,'สาขา');_bg_field(c,m2+42,cy2-1,fw-52,15,bbr,8)
    cy2-=17;_bg_label(c,m2+10,cy2+3,'เลขที่');_bg_field(c,m2+42,cy2-1,135,15,bgn,8)
    _bg_label(c,m2+186,cy2+3,'จำนวน');_bg_field(c,m2+218,cy2-1,110,15,bgv,8)
    c.setFont(_TF,6);c.setFillColor(_LGRAY);c.drawString(m2+338,cy2+3,'ครบถ้วน')
    _bg_sign(c,pw2/2-78,cy2-55,'ลงชื่อผู้คืนหลักประกัน',155,45)

    c.save();return buf.getvalue()


@app.route('/generate_bg_delivery', methods=['POST'])
def generate_bg_delivery():
    try:
        err = _check_key()
        if err: return err
        data = request.get_json()
        if not data: return jsonify({'success':False,'message':'No JSON body'}), 400
        pdf_bytes = _create_bg_delivery_pdf(data)
        fn = data.get('contractNo','BG').replace('/','_').replace(' ','_')
        return jsonify({
            'success': True,
            'pdfBase64': base64.b64encode(pdf_bytes).decode(),
            'fileName': f"BG_Delivery_{fn}.pdf"
        })
    except Exception as e:
        return jsonify({'success':False,'message':str(e)}), 500


# ════════════════════════════════════════════════════════════
# 3. REQUEST APPROVE LG  ★ NEW
# ════════════════════════════════════════════════════════════

@app.route('/generate_lg', methods=['POST'])
def api_generate_lg():
    try:
        err = _check_key()
        if err: return err
        data = request.get_json()
        if not data: return jsonify({'success':False,'message':'No JSON body'}), 400

        pdf_bytes = generate_lg_pdf(data)
        pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

        items = data.get('items', [{}])
        proj = (items[0].get('project', '') if items else '').strip()
        safe = ''.join(ch for ch in proj[:40] if ch.isalnum() or ch in '_- ' or ('\u0e00' <= ch <= '\u0e7f'))
        filename = 'Request_Approve_LG_' + (safe.strip() or 'form') + '.pdf'

        return jsonify({'success': True, 'pdfBase64': pdf_b64, 'fileName': filename})
    except Exception as e:
        return jsonify({'success':False,'message':str(e)}), 500


# ════════════════════════════════════════════════════════════
# 4. PETTY CASH  ★ NEW
# ════════════════════════════════════════════════════════════

@app.route('/generate_pettycash', methods=['POST'])
def api_generate_pettycash():
    try:
        err = _check_key()
        if err: return err
        data = request.get_json()
        if not data: return jsonify({'success':False,'message':'No JSON body'}), 400

        pdf_bytes = generate_pettycash_pdf(data)
        pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

        items = data.get('items', [{}])
        desc = (items[0].get('description', '') if items else '').strip()
        safe = ''.join(ch for ch in desc[:40] if ch.isalnum() or ch in '_- ' or ('\u0e00' <= ch <= '\u0e7f'))
        filename = 'PettyCash_' + (safe.strip() or 'form') + '.pdf'

        return jsonify({'success': True, 'pdfBase64': pdf_b64, 'fileName': filename})
    except Exception as e:
        return jsonify({'success':False,'message':str(e)}), 500


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
