import { useEffect, useState } from 'react';
import { api } from '../api/client';

type Tab = 'catalogue' | 'suppliers' | 'purchases' | 'expiry' | 'returns' | 'alerts';

export default function StockDesk() {
  const [tab, setTab] = useState<Tab>('purchases');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [suppliers, setSuppliers] = useState<Record<string, unknown>[]>([]);
  const [medicines, setMedicines] = useState<Record<string, unknown>[]>([]);
  const [purchases, setPurchases] = useState<Record<string, unknown>[]>([]);
  const [expiry, setExpiry] = useState<Record<string, Array<Record<string, unknown>>> | null>(null);
  const [alerts, setAlerts] = useState<Record<string, unknown[]> | null>(null);
  const [returns, setReturns] = useState<Record<string, unknown>[]>([]);
  const [supplier, setSupplier] = useState({ name: '', gstin: '', phone: '', drug_licence: '' });
  const [medicine, setMedicine] = useState({ brand_name: '', generic_name: '', hsn_code: '300490', gst_percent: '12', pack_size: '1', strip_size: '10', reorder_level: '10', selling_price: '' });
  const [purchase, setPurchase] = useState({ supplier_id: '', supplier_invoice_no: '', invoice_date: '', medicine_name: '', batch_no: '', expiry_date: '', quantity: '1', unit: 'strip', purchase_rate: '', gst_percent: '12' });
  const [saleReturn, setSaleReturn] = useState({ invoice_number: '', description: '', quantity: '1', reason: '', condition: 'saleable', refund: false });
  const [buyReturn, setBuyReturn] = useState({ purchase_line_id: '', quantity: '1', reason: '', supplier_credit_no: '' });

  const load = async () => {
    setError('');
    try {
      const [supplierRows, medicineRows, purchaseRows, expiryRows, alertRows, returnRows] = await Promise.all([
        api.suppliers(),
        api.medicines(''),
        api.purchases(),
        api.expiryReport(),
        api.stockAlerts(),
        api.salesReturns(),
      ]);
      setSuppliers(supplierRows);
      setMedicines(medicineRows);
      setPurchases(purchaseRows);
      setExpiry(expiryRows);
      setAlerts(alertRows);
      setReturns(returnRows);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load the stock desk');
    }
  };

  useEffect(() => { load(); }, []);

  const tabs: [Tab, string][] = [
    ['catalogue', 'Catalogue'],
    ['suppliers', 'Suppliers'],
    ['purchases', 'Purchases'],
    ['expiry', 'Expiry'],
    ['returns', 'Returns'],
    ['alerts', 'Alerts'],
  ];

  return (
    <div>
      <div className="page-header d-flex justify-content-between align-items-start">
        <div>
          <h2>Stock desk</h2>
          <p className="page-subtitle">Purchases, batches, expiry, and returns. Stock moves only through a ledger entry. One strip is stored as its tablets.</p>
        </div>
        <a className="btn btn-outline-secondary" href="#alerts" onClick={e => { e.preventDefault(); api.downloadStockAlerts().catch(err => setError(err.message)); }}>Excel</a>
      </div>
      {error && <div className="alert alert-danger">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}
      <div className="btn-group mb-3 flex-wrap">
        {tabs.map(([id, label]) => (
          <button key={id} type="button" className={`btn btn-sm ${tab === id ? 'btn-primary' : 'btn-outline-primary'}`} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>

      {tab === 'catalogue' && (
        <div className="card p-3">
          <form className="row g-2" onSubmit={async e => {
            e.preventDefault();
            try {
              await api.saveMedicine({ ...medicine, gst_percent: Number(medicine.gst_percent), pack_size: Number(medicine.pack_size), strip_size: Number(medicine.strip_size), reorder_level: Number(medicine.reorder_level), selling_price: medicine.selling_price ? Number(medicine.selling_price) : null });
              setNotice(`Saved ${medicine.brand_name}.`);
              setMedicine({ ...medicine, brand_name: '', generic_name: '' });
              await load();
            } catch (err) { setError(err instanceof Error ? err.message : 'Could not save the medicine'); }
          }}>
            <div className="col-md-4"><input className="form-control" placeholder="Brand name" value={medicine.brand_name} onChange={e => setMedicine({ ...medicine, brand_name: e.target.value })} required /></div>
            <div className="col-md-4"><input className="form-control" placeholder="Generic name" value={medicine.generic_name} onChange={e => setMedicine({ ...medicine, generic_name: e.target.value })} /></div>
            <div className="col-md-2"><input className="form-control" placeholder="HSN" value={medicine.hsn_code} onChange={e => setMedicine({ ...medicine, hsn_code: e.target.value })} /></div>
            <div className="col-md-2"><input className="form-control" placeholder="GST %" value={medicine.gst_percent} onChange={e => setMedicine({ ...medicine, gst_percent: e.target.value })} /></div>
            <div className="col-md-2"><input className="form-control" placeholder="Strips per box" value={medicine.pack_size} onChange={e => setMedicine({ ...medicine, pack_size: e.target.value })} /></div>
            <div className="col-md-2"><input className="form-control" placeholder="Tablets per strip" value={medicine.strip_size} onChange={e => setMedicine({ ...medicine, strip_size: e.target.value })} /></div>
            <div className="col-md-2"><input className="form-control" placeholder="Reorder" value={medicine.reorder_level} onChange={e => setMedicine({ ...medicine, reorder_level: e.target.value })} /></div>
            <div className="col-md-2"><input className="form-control" placeholder="Selling price" value={medicine.selling_price} onChange={e => setMedicine({ ...medicine, selling_price: e.target.value })} /></div>
            <div className="col-md-2"><button className="btn btn-primary w-100" type="submit">Save</button></div>
          </form>
          <ul className="mt-3 mb-0">{medicines.map(row => <li key={String(row.id)}>{String(row.brand_name)} · {String(row.generic_name || '')} · GST {String(row.gst_percent)}% · strip {String(row.strip_size)}</li>)}</ul>
        </div>
      )}

      {tab === 'suppliers' && (
        <div className="card p-3">
          <form className="row g-2" onSubmit={async e => {
            e.preventDefault();
            try {
              await api.saveSupplier(supplier);
              setNotice(`Saved ${supplier.name}.`);
              setSupplier({ name: '', gstin: '', phone: '', drug_licence: '' });
              await load();
            } catch (err) { setError(err instanceof Error ? err.message : 'Could not save the supplier'); }
          }}>
            <div className="col-md-4"><input className="form-control" placeholder="Supplier name" value={supplier.name} onChange={e => setSupplier({ ...supplier, name: e.target.value })} required /></div>
            <div className="col-md-3"><input className="form-control" placeholder="GSTIN" value={supplier.gstin} onChange={e => setSupplier({ ...supplier, gstin: e.target.value })} /></div>
            <div className="col-md-2"><input className="form-control" placeholder="Phone" value={supplier.phone} onChange={e => setSupplier({ ...supplier, phone: e.target.value })} /></div>
            <div className="col-md-2"><input className="form-control" placeholder="Drug licence" value={supplier.drug_licence} onChange={e => setSupplier({ ...supplier, drug_licence: e.target.value })} /></div>
            <div className="col-md-1"><button className="btn btn-primary w-100" type="submit">Add</button></div>
          </form>
          <ul className="mt-3 mb-0">{suppliers.map(row => <li key={String(row.id)}>{String(row.name)} {row.gstin ? `· ${row.gstin}` : ''} {row.phone ? `· ${row.phone}` : ''}</li>)}</ul>
        </div>
      )}

      {tab === 'purchases' && (
        <div className="card p-3">
          <form className="row g-2" onSubmit={async e => {
            e.preventDefault();
            try {
              const saved = await api.savePurchase({
                supplier_id: Number(purchase.supplier_id),
                supplier_invoice_no: purchase.supplier_invoice_no,
                invoice_date: purchase.invoice_date || undefined,
                lines: [{
                  medicine_name: purchase.medicine_name,
                  batch_no: purchase.batch_no,
                  expiry_date: purchase.expiry_date || undefined,
                  quantity: Number(purchase.quantity),
                  unit: purchase.unit,
                  purchase_rate: Number(purchase.purchase_rate),
                  gst_percent: Number(purchase.gst_percent),
                  pack_size: 1,
                  strip_size: purchase.unit === 'strip' ? 10 : 1,
                }],
              });
              setNotice(`Purchase ${String(saved.document_no)} posted to stock.`);
              await load();
            } catch (err) { setError(err instanceof Error ? err.message : 'Could not post the purchase'); }
          }}>
            <div className="col-md-4">
              <select className="form-select" value={purchase.supplier_id} onChange={e => setPurchase({ ...purchase, supplier_id: e.target.value })} required>
                <option value="">Supplier</option>
                {suppliers.map(row => <option key={String(row.id)} value={String(row.id)}>{String(row.name)}</option>)}
              </select>
            </div>
            <div className="col-md-3"><input className="form-control" placeholder="Supplier invoice no." value={purchase.supplier_invoice_no} onChange={e => setPurchase({ ...purchase, supplier_invoice_no: e.target.value })} required /></div>
            <div className="col-md-2"><input className="form-control" type="date" value={purchase.invoice_date} onChange={e => setPurchase({ ...purchase, invoice_date: e.target.value })} /></div>
            <div className="col-md-3"><input className="form-control" placeholder="Medicine" value={purchase.medicine_name} onChange={e => setPurchase({ ...purchase, medicine_name: e.target.value })} required /></div>
            <div className="col-md-2"><input className="form-control" placeholder="Batch" value={purchase.batch_no} onChange={e => setPurchase({ ...purchase, batch_no: e.target.value })} /></div>
            <div className="col-md-2"><input className="form-control" type="date" value={purchase.expiry_date} onChange={e => setPurchase({ ...purchase, expiry_date: e.target.value })} /></div>
            <div className="col-md-1"><input className="form-control" placeholder="Qty" value={purchase.quantity} onChange={e => setPurchase({ ...purchase, quantity: e.target.value })} /></div>
            <div className="col-md-2">
              <select className="form-select" value={purchase.unit} onChange={e => setPurchase({ ...purchase, unit: e.target.value })}>
                <option value="strip">Strip</option>
                <option value="tablet">Tablet</option>
                <option value="box">Box</option>
                <option value="bottle">Bottle</option>
              </select>
            </div>
            <div className="col-md-2"><input className="form-control" placeholder="Rate" value={purchase.purchase_rate} onChange={e => setPurchase({ ...purchase, purchase_rate: e.target.value })} required /></div>
            <div className="col-md-1"><input className="form-control" placeholder="GST" value={purchase.gst_percent} onChange={e => setPurchase({ ...purchase, gst_percent: e.target.value })} /></div>
            <div className="col-md-2"><button className="btn btn-primary w-100" type="submit">Receive</button></div>
          </form>
          <p className="small text-muted mt-2">A strip is received as 10 tablets. Enter the same supplier invoice twice and it will be refused.</p>
          <ul className="mb-0">{purchases.map(row => <li key={String(row.id)}>{String(row.document_no)} · {String(row.supplier_name)} · {String(row.supplier_invoice_no)} · ₹{String(row.amount)} · due ₹{String(row.outstanding)}</li>)}</ul>
        </div>
      )}

      {tab === 'expiry' && expiry && (
        <div className="row g-3">
          {(['expired', 'within_30', 'within_60', 'within_90'] as const).map(key => (
            <div className="col-md-6" key={key}>
              <div className="card p-3">
                <h5>{key === 'expired' ? 'Expired' : key === 'within_30' ? 'Within 30 days' : key === 'within_60' ? 'Within 60 days' : 'Within 90 days'}</h5>
                <ul className="mb-0">{(expiry[key] || []).map(row => <li key={String(row.id)}>{String(row.medicine_name)} · {String(row.batch_no || 'no batch')} · exp {String(row.expiry_date)} · qty {String(row.quantity)} · {String(row.stock_status)}</li>)}</ul>
                {(expiry[key] || []).length === 0 && <p className="text-muted mb-0">None</p>}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'returns' && (
        <div className="row g-3">
          <div className="col-md-6">
            <div className="card p-3">
              <h5>Sales return</h5>
              <form className="row g-2" onSubmit={async e => {
                e.preventDefault();
                try {
                  const saved = await api.salesReturn({ ...saleReturn, quantity: Number(saleReturn.quantity), refund: saleReturn.refund });
                  setNotice(`Credit note ${String(saved.document_no)} for ₹${String(saved.amount)}.`);
                  await load();
                } catch (err) { setError(err instanceof Error ? err.message : 'Could not save the return'); }
              }}>
                <div className="col-md-6"><input className="form-control" placeholder="Invoice number" value={saleReturn.invoice_number} onChange={e => setSaleReturn({ ...saleReturn, invoice_number: e.target.value })} required /></div>
                <div className="col-md-6"><input className="form-control" placeholder="Medicine on the invoice" value={saleReturn.description} onChange={e => setSaleReturn({ ...saleReturn, description: e.target.value })} required /></div>
                <div className="col-md-3"><input className="form-control" placeholder="Qty" value={saleReturn.quantity} onChange={e => setSaleReturn({ ...saleReturn, quantity: e.target.value })} /></div>
                <div className="col-md-4">
                  <select className="form-select" value={saleReturn.condition} onChange={e => setSaleReturn({ ...saleReturn, condition: e.target.value })}>
                    <option value="saleable">Saleable — back to stock</option>
                    <option value="damaged">Damaged — quarantine</option>
                  </select>
                </div>
                <div className="col-md-5 form-check ms-2"><label className="form-check-label"><input className="form-check-input" type="checkbox" checked={saleReturn.refund} onChange={e => setSaleReturn({ ...saleReturn, refund: e.target.checked })} /> Refund the patient</label></div>
                <div className="col-12"><input className="form-control" placeholder="Reason" value={saleReturn.reason} onChange={e => setSaleReturn({ ...saleReturn, reason: e.target.value })} required /></div>
                <div className="col-12"><button className="btn btn-primary" type="submit">Save credit note</button></div>
              </form>
              <ul className="mt-3 mb-0">{returns.map(row => <li key={String(row.id)}>{String(row.document_no)} · {String(row.condition)} · ₹{String(row.amount)} · {String(row.reason)}</li>)}</ul>
            </div>
          </div>
          <div className="col-md-6">
            <div className="card p-3">
              <h5>Purchase return</h5>
              <form className="row g-2" onSubmit={async e => {
                e.preventDefault();
                try {
                  const saved = await api.purchaseReturn({ purchase_line_id: Number(buyReturn.purchase_line_id), quantity: Number(buyReturn.quantity), reason: buyReturn.reason, supplier_credit_no: buyReturn.supplier_credit_no });
                  setNotice(`Purchase return ${String(saved.document_no)}.`);
                  await load();
                } catch (err) { setError(err instanceof Error ? err.message : 'Could not save the purchase return'); }
              }}>
                <div className="col-md-4"><input className="form-control" placeholder="Purchase line id" value={buyReturn.purchase_line_id} onChange={e => setBuyReturn({ ...buyReturn, purchase_line_id: e.target.value })} required /></div>
                <div className="col-md-3"><input className="form-control" placeholder="Qty" value={buyReturn.quantity} onChange={e => setBuyReturn({ ...buyReturn, quantity: e.target.value })} /></div>
                <div className="col-md-5"><input className="form-control" placeholder="Supplier credit note" value={buyReturn.supplier_credit_no} onChange={e => setBuyReturn({ ...buyReturn, supplier_credit_no: e.target.value })} /></div>
                <div className="col-12"><input className="form-control" placeholder="Reason" value={buyReturn.reason} onChange={e => setBuyReturn({ ...buyReturn, reason: e.target.value })} required /></div>
                <div className="col-12"><button className="btn btn-outline-danger" type="submit">Return to supplier</button></div>
              </form>
              <ul className="small mt-3">{purchases.flatMap(row => ((row.lines as Record<string, unknown>[]) || []).map(line => <li key={String(line.id)}>Line {String(line.id)} · {String(line.medicine_name)} · base {String(line.base_quantity)} · returned {String(line.returned_base || 0)}</li>))}</ul>
            </div>
          </div>
        </div>
      )}

      {tab === 'alerts' && alerts && (
        <div className="row g-3">
          {(['out_of_stock', 'low_stock', 'reorder', 'fast_moving', 'slow_moving'] as const).map(key => (
            <div className="col-md-6" key={key}>
              <div className="card p-3">
                <h5 className="text-capitalize">{key.replace(/_/g, ' ')}</h5>
                <ul className="mb-0">
                  {(alerts[key] || []).map((row, index) => (
                    <li key={index}>{String((row as Record<string, unknown>).brand_name || (row as Record<string, unknown>).medicine_name || row)}{(row as Record<string, unknown>).quantity != null ? ` · ${String((row as Record<string, unknown>).quantity)}` : ''}</li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
