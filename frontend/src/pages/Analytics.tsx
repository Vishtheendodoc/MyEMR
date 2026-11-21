import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { api, AnalyticsData } from '../api/client';

const COLORS = ['#0d6efd', '#198754', '#ffc107', '#dc3545', '#6f42c1', '#20c997', '#fd7e14', '#0dcaf0'];

export default function Analytics() {
  const [data, setData] = useState<AnalyticsData | null>(null);

  useEffect(() => {
    api.analytics().then(setData).catch(() => {});
  }, []);

  if (!data) return <div>Loading...</div>;

  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const visitChart = data.visit_volume_by_month.map(v => ({ name: monthNames[v.month - 1] || `M${v.month}`, count: v.count }));

  return (
    <div>
      <h2 className="mb-4"><i className="fas fa-chart-bar me-2"></i>Analytics & Reports</h2>

      {data.practice && (
        <div className="row mb-4">
          <div className="col-md-4"><div className="card p-3 text-center"><h4>₹{data.practice.business.consultation_revenue.toFixed(0)}</h4><small>Consultation</small></div></div>
          <div className="col-md-4"><div className="card p-3 text-center"><h4>₹{data.practice.business.pharmacy_turnover.toFixed(0)}</h4><small>Pharmacy</small></div></div>
          <div className="col-md-4"><div className="card p-3 text-center"><h4>₹{data.practice.business.laboratory_revenue.toFixed(0)}</h4><small>Laboratory</small></div></div>
          <div className="col-12 mt-2"><p className="text-muted small mb-0">{data.practice.business.revenue_note} {data.practice.business.pharmacy_margin_note}</p></div>
          <div className="col-md-6 mt-3"><div className="card p-3">Average HbA1c {String(data.practice.clinical.average_hba1c ?? '—')}. {String(data.practice.clinical.target_note || '')}</div></div>
          <div className="col-md-6 mt-3"><div className="card p-3">Today {data.practice.business.consultations_today} consultations. New this month {data.practice.business.new_patients_this_month}, returning {data.practice.business.returning_patients_this_month}.</div></div>
        </div>
      )}

      <div className="row mb-4">
        <div className="col-md-4"><div className="card p-3 text-center"><h4>₹{data.revenue_summary.total_billed.toFixed(0)}</h4><small className="text-muted">Total Revenue</small></div></div>
        <div className="col-md-4"><div className="card p-3 text-center"><h4 className="text-success">₹{data.revenue_summary.total_paid.toFixed(0)}</h4><small className="text-muted">Collected</small></div></div>
        <div className="col-md-4"><div className="card p-3 text-center"><h4>{data.diagnosis_distribution.reduce((s, d) => s + d.count, 0)}</h4><small className="text-muted">Diagnoses Tracked</small></div></div>
      </div>

      <div className="row">
        <div className="col-md-6 mb-4">
          <div className="card p-3">
            <h5>Diagnosis Distribution</h5>
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={data.diagnosis_distribution} dataKey="count" nameKey="diagnosis" cx="50%" cy="50%" outerRadius={90} label>
                  {data.diagnosis_distribution.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="col-md-6 mb-4">
          <div className="card p-3">
            <h5>Visit Volume by Month</h5>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={visitChart}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#0d6efd" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="col-12">
          <div className="card p-3">
            <h5>Top Prescribed Medications</h5>
            <table className="table mb-0">
              <thead><tr><th>Drug</th><th>Prescription Count</th></tr></thead>
              <tbody>
                {data.top_medications.map((m, i) => (
                  <tr key={i}><td>{m.drug}</td><td>{m.count}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
