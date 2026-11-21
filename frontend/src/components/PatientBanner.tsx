import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { api, Patient } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { chartTarget } from '../utils/chartContext';
import { canAccessPath } from '../utils/roles';

export default function PatientBanner() {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const target = chartTarget(pathname);
  const [patient, setPatient] = useState<Patient | null>(null);

  useEffect(() => {
    let cancel = false;
    setPatient(null);
    const load = async () => {
      try {
        let patientId = target.patientId;
        if (!patientId && target.visitId) {
          const visit = await api.visit(target.visitId);
          patientId = visit.patient_id;
        }
        if (!patientId) return;
        const row = await api.patient(patientId);
        if (!cancel) setPatient(row);
      } catch {
        if (!cancel) setPatient(null);
      }
    };
    if (target.patientId || target.visitId) load();
    return () => { cancel = true; };
  }, [target.patientId, target.visitId]);

  if (!patient) return null;

  const allergy = (patient.allergies || '').trim();
  const mrd = patient.mrd_number
    ? ((patient.mrd_number.startsWith('TMP-') || patient.registration_status === 'temporary') ? `Temp ${patient.mrd_number}` : patient.mrd_number)
    : 'No MRD';

  const tabs = [
    ['Chart', `/patients/${patient.id}`],
    ['360', `/patients/${patient.id}/360`],
    ['Visits', `/patients/${patient.id}/visits/new`],
    ['Labs', `/patients/${patient.id}/labs`],
    ['Diabetes', `/patients/${patient.id}/diabetes`],
    ['Growth', `/patients/${patient.id}/growth`],
    ['Timeline', `/patients/${patient.id}/timeline`],
  ].filter(([, path]) => !user || canAccessPath(user.role, path));

  return (
    <div className="chart-banner no-print" role="region" aria-label="Patient">
      <div className="chart-banner-id">
        <Link to={`/patients/${patient.id}`}>{patient.name}</Link>
        <span>{[patient.age, patient.sex, mrd].filter(Boolean).join(' · ')}</span>
      </div>
      <div className={allergy ? 'chart-banner-allergy' : 'chart-banner-allergy is-clear'}>
        <strong>{allergy ? 'Allergies' : 'Allergies not recorded'}</strong>
        {allergy && <span>{allergy}</span>}
      </div>
      <div className="chart-tabs">
        {tabs.map(([label, path]) => (
          <Link key={path} to={path} className={pathname === path ? 'active' : ''}>{label}</Link>
        ))}
      </div>
    </div>
  );
}
