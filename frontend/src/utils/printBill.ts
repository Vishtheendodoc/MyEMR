import { Bill, BillLine } from '../api/client';
import { formatClinicDateTime } from './clinicTime';
import { openPrintHtml } from './openPrintHtml';

function formatInr(n: number) {
  return `₹${n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function esc(value: string | number | null | undefined) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function linesOf(bill: Bill): BillLine[] {
  if (bill.line_items && bill.line_items.length) return bill.line_items;
  const base = bill.base_amount ?? (bill.amount - (bill.gst_amount || 0));
  return [{
    description: bill.description,
    procedure_code: bill.procedure_code,
    quantity: 1,
    rate: base,
    base_amount: base,
    gst_percent: bill.gst_percent || 0,
    gst_amount: bill.gst_amount || 0,
  }];
}

export function printBillInvoice(
  bill: Bill,
  clinicName = 'Endo Clinic',
  doctorName?: string,
  clinic?: { name?: string; address?: string | null; phone?: string | null; gstin?: string | null; signatory?: string | null; signature_data?: string | null },
) {
  const created = formatClinicDateTime(bill.created_at);
  const lines = linesOf(bill);
  const gst = lines.reduce((sum, line) => sum + (line.gst_amount || 0), 0);
  const subtotal = lines.reduce((sum, line) => sum + (line.base_amount || 0), 0);
  const discount = bill.discount_amount || 0;
  const paid = bill.amount_paid || 0;
  const due = Math.max(0, bill.amount - paid);
  const invoiceNo = bill.invoice_number || `INV-${bill.id}`;
  const rows = lines.map(line => `
      <tr>
        <td>${esc(line.description)}${line.note ? `<div style="font-size:11px;color:#555">${esc(line.note)}</div>` : ''}</td>
        <td>${esc(line.procedure_code || '—')}</td>
        <td style="text-align:right">${esc(line.quantity ?? 1)}</td>
        <td style="text-align:right">${esc(formatInr(line.rate || line.base_amount || 0))}</td>
        <td style="text-align:right">${esc(line.gst_percent || 0)}%</td>
        <td style="text-align:right">${esc(formatInr((line.base_amount || 0) + (line.gst_amount || 0)))}</td>
      </tr>`).join('');

  const html = `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Invoice ${esc(invoiceNo)}</title>
  <style>
    body{font-family:Segoe UI,Arial,sans-serif;color:#0f2133;padding:28px;max-width:780px;margin:0 auto}
    .head{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #1a6bb5;padding-bottom:12px;margin-bottom:18px}
    .brand{font-size:22px;font-weight:700;color:#0f4f8a}
    .muted{color:#5a6f84;font-size:13px}
    table{width:100%;border-collapse:collapse;margin-top:12px}
    th,td{border:1px solid #d4e0ec;padding:8px;text-align:left;font-size:13px}
    th{background:#eef5fb}
    .totals{width:300px;margin-left:auto;margin-top:8px}
    .totals td{border:none;padding:5px 10px}
    .totals tr:last-child td{font-weight:700;font-size:16px;border-top:2px solid #1a6bb5;padding-top:10px}
    .actions{margin-bottom:16px}
    .actions button{background:#1a6bb5;color:#fff;border:0;border-radius:8px;padding:8px 14px;font-weight:600;cursor:pointer}
    @media print{.actions{display:none} body{padding:0}}
  </style>
</head>
<body>
  <div class="actions">
    <button type="button" onclick="window.print()">Print invoice</button>
  </div>
  <div class="head">
    <div>
      <div class="brand">${esc(clinic?.name || clinicName)}</div>
      <div class="muted">${esc([clinic?.address, clinic?.phone, clinic?.gstin ? `GSTIN ${clinic.gstin}` : ''].filter(Boolean).join(' · ') || (doctorName ? `Dr. ${doctorName}` : 'Clinic invoice'))}</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:18px;font-weight:700">${due > 0 ? 'INVOICE' : 'RECEIPT'}</div>
      <div class="muted">${esc(invoiceNo)}</div>
      <div class="muted">${esc(created)}</div>
    </div>
  </div>
  <p><strong>${esc(bill.patient_name || '—')}</strong><br/>
  <span class="muted">Age ${esc(bill.patient_age || '—')} · ${esc(bill.patient_sex || '—')} · MRD ${esc(bill.patient_mrd || '—')}</span></p>
  <table>
    <thead><tr><th>Item</th><th>Code</th><th>Qty</th><th>Rate</th><th>GST</th><th>Amount</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>
  <table class="totals">
    <tr><td>Subtotal</td><td style="text-align:right">${esc(formatInr(subtotal))}</td></tr>
    <tr><td>GST</td><td style="text-align:right">${esc(formatInr(gst))}</td></tr>
    <tr><td>Discount</td><td style="text-align:right">${esc(formatInr(discount))}</td></tr>
    <tr><td>Total</td><td style="text-align:right">${esc(formatInr(bill.amount))}</td></tr>
    <tr><td>Paid</td><td style="text-align:right">${esc(formatInr(paid))}</td></tr>
    <tr><td>Balance due</td><td style="text-align:right">${esc(formatInr(due))}</td></tr>
  </table>
  <p style="margin-top:20px"><strong>Payment:</strong> ${esc(bill.payment_status)}${bill.payment_method ? ` · ${esc(bill.payment_method)}` : ''}</p>
  ${clinic?.signature_data ? `<img src="${clinic.signature_data}" alt="Signature" style="max-height:70px" />` : ''}
  <p><strong>${esc(clinic?.signatory || (doctorName ? `Dr. ${doctorName}` : ''))}</strong></p>
  <p class="muted">Thank you for visiting ${esc(clinic?.name || clinicName)}.</p>
  <script>
    window.addEventListener('load', function () {
      setTimeout(function () { window.print(); }, 250);
    });
  </script>
</body>
</html>`;

  openPrintHtml(html, 'Pop-up blocked. Allow pop-ups for this site to print invoices.');
}

export function printCreditNote(
  bill: Bill,
  refundAmount: number,
  reason: string,
  clinicName = 'Endo Clinic',
  clinic?: { name?: string; address?: string | null; phone?: string | null; gstin?: string | null },
) {
  const created = formatClinicDateTime();
  const invoiceNo = bill.invoice_number || `INV-${bill.id}`;
  const html = `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Credit note — ${esc(invoiceNo)}</title>
  <style>
    body{font-family:Segoe UI,Arial,sans-serif;color:#0f2133;padding:28px;max-width:640px;margin:0 auto}
    .head{border-bottom:2px solid #c45a11;padding-bottom:12px;margin-bottom:18px}
    .brand{font-size:20px;font-weight:700;color:#9a3412}
    .muted{color:#5a6f84;font-size:13px}
    .amount{font-size:22px;font-weight:700;margin:16px 0}
    @media print{.actions{display:none}}
  </style>
</head>
<body>
  <div class="actions"><button type="button" onclick="window.print()" style="background:#c45a11;color:#fff;border:0;border-radius:8px;padding:8px 14px;cursor:pointer">Print credit note</button></div>
  <div class="head">
    <div class="brand">CREDIT NOTE</div>
    <div class="muted">${esc(clinic?.name || clinicName)} · ${esc(created)}</div>
  </div>
  <p><strong>${esc(bill.patient_name || '—')}</strong><br/>
  <span class="muted">Age ${esc(bill.patient_age || '—')} · ${esc(bill.patient_sex || '—')} · MRD ${esc(bill.patient_mrd || '—')}</span></p>
  <p><strong>Against invoice:</strong> ${esc(invoiceNo)}</p>
  <p class="amount">Refund: ${esc(formatInr(refundAmount))}</p>
  ${reason ? `<p><strong>Reason:</strong> ${esc(reason)}</p>` : ''}
  <p class="muted">This credit note acknowledges the refund issued against the invoice above.</p>
  <script>window.addEventListener('load',function(){setTimeout(function(){window.print()},250)});</script>
</body>
</html>`;
  openPrintHtml(html, 'Pop-up blocked. Allow pop-ups to print credit notes.');
}
