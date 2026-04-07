// ═══════════════════════════════════════════════════════════
// PATCH: PDFForms.html — เพิ่มฟอร์มที่ 9 (หนังสือทั่วไป)
// ═══════════════════════════════════════════════════════════
//
// จุดที่ 1: เพิ่ม routing ใน _selectPDFForm
// ──────────────────────────────────────────
// หาบรรทัดนี้:
//
//   } else if (formId === 'bg_poa') {
//
// เพิ่มข้างบนมัน (ก่อน bg_poa):
//
// } else if (formId === 'general_letter') {
// _renderGeneralLetterPopup();
//
// ─── ก่อนแก้ ───────────────────────────
// } else if (formId === 'bg_poa') {
// ─── หลังแก้ ───────────────────────────
// } else if (formId === 'general_letter') {
// _renderGeneralLetterPopup();
// } else if (formId === 'bg_poa') {
// ────────────────────────────────────────
//
//
// จุดที่ 2: เพิ่ม function _renderGeneralLetterPopup + _generateGeneralLetter
// ──────────────────────────────────────────────────────────────────────────────
// วาง code ด้านล่างนี้ไว้ที่ **ท้ายไฟล์ PDFForms.html** ก่อน </script>
// ──────────────────────────────────────────────────────────────────────────────

// ============================================================
// ✉️ GENERAL LETTER POPUP — หนังสือทั่วไป (ฟอร์มที่ 9)
// layout อิงจาก BG Withdraw: หัวข้อ, เลขที่, วันที่, เรียน, เรื่อง, เนื้อหา, ลายเซ็น
// ============================================================

function _renderGeneralLetterPopup() {
try {
  var el = document.getElementById('pdfFormPopup');
  if (!el) return;
  var c = currentContract || {};
  var esc = function(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); };

  var iS = 'width:100%;padding:8px 10px;border:1.5px solid var(--border2,#e2e8f0);border-radius:8px;font-size:14px;background:var(--surface,#fff);color:var(--text,#1e293b);box-sizing:border-box;font-family:var(--font)';

  var html = '<div style="background:var(--surface,#fff);border-radius:16px;max-width:620px;width:100%;max-height:90vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,.3)">';

  // ── Header ──
  html += '<div style="position:sticky;top:0;z-index:2;background:var(--surface,#fff);padding:14px 20px;border-bottom:1.5px solid var(--border,#e2e8f0);display:flex;justify-content:space-between;align-items:center">';
  html += '<div style="font-size:16px;font-weight:700;color:var(--text,#1e293b)">✉️ หนังสือทั่วไป (General Letter)</div>';
  html += '<button data-action="closePDFForm" style="width:30px;height:30px;border:none;background:var(--surface2,#f1f5f9);border-radius:8px;cursor:pointer;font-size:16px;color:var(--text2,#64748b)">✕</button>';
  html += '</div>';

  html += '<div style="padding:16px 20px">';

  // ── หัวข้อหนังสือ ──
  html += '<div style="margin-bottom:10px"><label style="font-size:11px;font-weight:700;color:var(--text3,#94a3b8);text-transform:uppercase;display:block;margin-bottom:3px">หัวข้อหนังสือ *</label>';
  html += '<input id="glTitle" style="' + iS + '" value="" placeholder="เช่น หนังสือแจ้งขอส่งมอบงาน"></div>';

  // ── เลขที่หนังสือ + วันที่ ──
  html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">';
  html += '<div><label style="font-size:11px;font-weight:700;color:var(--text3,#94a3b8);text-transform:uppercase;display:block;margin-bottom:3px">เลขที่หนังสือ</label>';
  html += '<input id="glDocNumber" style="' + iS + '" value="" placeholder="SCM 2569/xxx"></div>';
  html += '<div><label style="font-size:11px;font-weight:700;color:var(--text3,#94a3b8);text-transform:uppercase;display:block;margin-bottom:3px">วันที่</label>';
  html += '<input id="glDocDate" style="' + iS + '" value="" placeholder="7 เมษายน พ.ศ.2569"></div>';
  html += '</div>';

  // ── ทำที่ ──
  html += '<div style="margin-bottom:10px"><label style="font-size:11px;font-weight:700;color:var(--text3,#94a3b8);text-transform:uppercase;display:block;margin-bottom:3px">ทำที่ (ชื่อบริษัท)</label>';
  html += '<input id="glWrittenAt" style="' + iS + '" value="" placeholder="auto-fill จากบริษัท"></div>';

  // ── เรื่อง + เรียน ──
  html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">';
  html += '<div><label style="font-size:11px;font-weight:700;color:var(--text3,#94a3b8);text-transform:uppercase;display:block;margin-bottom:3px">เรื่อง</label>';
  html += '<input id="glSubject" style="' + iS + '" value="" placeholder="ระบุเรื่อง"></div>';
  html += '<div><label style="font-size:11px;font-weight:700;color:var(--text3,#94a3b8);text-transform:uppercase;display:block;margin-bottom:3px">เรียน</label>';
  html += '<input id="glRecipient" style="' + iS + '" value="' + esc(c.company || '') + '" placeholder="ชื่อผู้รับ / บริษัท"></div>';
  html += '</div>';

  // ── เนื้อหา (textarea หลายบรรทัด) ──
  html += '<div style="margin-bottom:10px"><label style="font-size:11px;font-weight:700;color:var(--text3,#94a3b8);text-transform:uppercase;display:block;margin-bottom:3px">เนื้อหาหนังสือ * (แต่ละย่อหน้า ขึ้นบรรทัดใหม่)</label>';
  html += '<textarea id="glBody" style="' + iS + ';min-height:120px;resize:vertical;line-height:1.6" placeholder="พิมพ์เนื้อหาที่นี่...\n\nแต่ละย่อหน้า กด Enter ขึ้นบรรทัดใหม่\nลายเซ็นจะเลื่อนลงอัตโนมัติตามเนื้อหา"></textarea></div>';

  // ── ลายเซ็น ──
  html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px">';
  html += '<div><label style="font-size:11px;font-weight:700;color:var(--text3,#94a3b8);text-transform:uppercase;display:block;margin-bottom:3px">ผู้ลงนาม</label>';
  html += '<input id="glSignerName" style="' + iS + '" value="" placeholder="ชื่อ-นามสกุล"></div>';
  html += '<div><label style="font-size:11px;font-weight:700;color:var(--text3,#94a3b8);text-transform:uppercase;display:block;margin-bottom:3px">ตำแหน่ง</label>';
  html += '<input id="glSignerPos" style="' + iS + '" value="Corporate Lawyers" placeholder="ตำแหน่ง"></div>';
  html += '</div>';

  // ── ปุ่ม ──
  html += '<div style="display:flex;gap:8px;justify-content:flex-end;padding-top:4px;border-top:1px solid var(--border,#e2e8f0)">';
  html += '<button data-action="closePDFForm" style="padding:10px 18px;border:1.5px solid var(--border2,#e2e8f0);border-radius:10px;cursor:pointer;font-size:13px;background:var(--surface2,#f8fafc);color:var(--text2,#64748b);font-weight:500">ยกเลิก</button>';
  html += '<button data-action="generateGeneralLetter" style="padding:10px 18px;border:none;border-radius:10px;cursor:pointer;font-size:13px;background:#0369a1;color:#fff;font-weight:600">✉️ สร้าง PDF</button>';
  html += '</div>';

  html += '</div></div>';
  el.innerHTML = html;

  // ── Auto-fill entity name ──
  if (c._sheet) {
    google.script.run
      .withSuccessHandler(function(res) {
        if (!res || !res.name) return;
        var wa = document.getElementById('glWrittenAt');
        if (wa && !wa.value) wa.value = res.name;
      })
      .withFailureHandler(function(){})
      .getLGEntityInfo(c._sheet);
  }
} catch(e) { console.error("[CTRK] _renderGeneralLetterPopup:", e.message||e); }
}

// ── Generate General Letter PDF ──
function _generateGeneralLetter() {
  if (!currentContract) currentContract = {};
  var gv = function(id) { var e = document.getElementById(id); return e ? e.value.trim() : ''; };
  var title = gv('glTitle');
  if (!title) { showToast('กรุณาระบุหัวข้อหนังสือ', 'error'); return; }
  var body = gv('glBody');
  if (!body) { showToast('กรุณาระบุเนื้อหา', 'error'); return; }

  var saveDrive = window._pdfSaveToDrive || false;
  var formData = {
    title:           title,
    docNumber:       gv('glDocNumber'),
    docDate:         gv('glDocDate'),
    writtenAt:       gv('glWrittenAt'),
    subject:         gv('glSubject'),
    recipientName:   gv('glRecipient'),
    bodyParagraphs:  body,
    signerName:      gv('glSignerName'),
    signerPosition:  gv('glSignerPos') || 'Corporate Lawyers'
  };

  showToast('กำลังสร้าง PDF...', 'info');
  google.script.run
    .withSuccessHandler(function(res) {
      if (!res || !res.success) {
        showToast('สร้าง PDF ไม่สำเร็จ: ' + (res ? res.message : ''), 'error');
        return;
      }
      showToast('✅ สร้างหนังสือสำเร็จ', 'success');
      var pf = document.getElementById('pdfFormPopup');
      if (pf) pf.style.display = 'none';
      if (!saveDrive && res.pdfBase64) {
        _downloadBase64PDF(res.pdfBase64, res.filename || res.fileName || 'letter.pdf');
      }
      window._pdfSaveToDrive = false;
    })
    .withFailureHandler(function(err) {
      showToast('Error: ' + (err.message || 'ไม่ทราบสาเหตุ'), 'error');
      window._pdfSaveToDrive = false;
    })
    .generateFormPDF({
      _sheet:      currentContract._sheet || '',
      _row:        currentContract._row || 0,
      formType:    'general_letter',
      formData:    formData,
      saveToDrive: saveDrive,
      folderPath:  currentContract.folderPath || currentContract.folderUrl || ''
    });
}

// ═══════════════════════════════════════════════════════════
// จุดที่ 3: เพิ่ม event delegation สำหรับปุ่ม "สร้าง PDF"
// ═══════════════════════════════════════════════════════════
// หาบรรทัดนี้ใน PDFForms.html (event delegation block):
//
//   if (action === 'generatePettyCashForm') { _generatePettyCashForm(); return; }
//
// เพิ่มข้างล่างมัน:
//
//   if (action === 'generateGeneralLetter') { _generateGeneralLetter(); return; }
