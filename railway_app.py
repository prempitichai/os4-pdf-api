#!/usr/bin/env python3
"""
OS4 PDF API Server — deploy บน Railway
POST /generate → รับ JSON → return { success, pdfBase64, fileName }
GET  /health   → health check
"""
import os, json, base64, math
from io import BytesIO
from flask import Flask, request, jsonify
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter

app = Flask(__name__)

# Font
THAI_FONT = 'FreeSerif'
for fp in ['/usr/share/fonts/truetype/freefont/FreeSerif.ttf', './fonts/FreeSerif.ttf', '/app/fonts/FreeSerif.ttf']:
    if os.path.exists(fp):
        pdfmetrics.registerFont(TTFont(THAI_FONT, fp)); break

# Template
TEMPLATE_PATH = os.environ.get('OS4_TEMPLATE', './os4_blank.pdf')
API_KEY = os.environ.get('OS4_API_KEY', '')

# Exact positions (pixel-scanned)
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
        if API_KEY and request.headers.get('X-API-Key','') != API_KEY:
            return jsonify({'success':False,'message':'Invalid API key'}), 401
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',8080)))
