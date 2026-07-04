import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './hooks/useAuth';
import Layout from './components/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Patients from './pages/Patients';
import PatientDetail from './pages/PatientDetail';
import PatientForm from './pages/PatientForm';
import VisitForm from './pages/VisitForm';
import VisitDetail from './pages/VisitDetail';
import PrescriptionPreview from './pages/PrescriptionPreview';
import Prescribe from './pages/Prescribe';
import Medications from './pages/Medications';
import Diagnoses from './pages/Diagnoses';
import Profile from './pages/Profile';
import FollowUpQueue from './pages/FollowUpQueue';
import PatientTimeline from './pages/PatientTimeline';
import PatientLabs from './pages/PatientLabs';
import DiabetesDashboard from './pages/DiabetesDashboard';
import GrowthChart from './pages/GrowthChart';
import Calculators from './pages/Calculators';
import Appointments from './pages/Appointments';
import Billing from './pages/Billing';
import Analytics from './pages/Analytics';

function AppRoutes() {
  const { loading } = useAuth();
  if (loading) return <div className="text-center py-5">Loading...</div>;

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/patients" element={<Patients />} />
        <Route path="/patients/new" element={<PatientForm />} />
        <Route path="/patients/:id" element={<PatientDetail />} />
        <Route path="/patients/:id/edit" element={<PatientForm />} />
        <Route path="/patients/:id/timeline" element={<PatientTimeline />} />
        <Route path="/patients/:id/labs" element={<PatientLabs />} />
        <Route path="/patients/:id/diabetes" element={<DiabetesDashboard />} />
        <Route path="/patients/:id/growth" element={<GrowthChart />} />
        <Route path="/patients/:patientId/visits/new" element={<VisitForm />} />
        <Route path="/visits/:id" element={<VisitDetail />} />
        <Route path="/visits/:id/edit" element={<VisitForm />} />
        <Route path="/visits/:id/prescription-preview" element={<PrescriptionPreview />} />
        <Route path="/visits/:id/prescribe" element={<Prescribe />} />
        <Route path="/follow-ups" element={<FollowUpQueue />} />
        <Route path="/calculators" element={<Calculators />} />
        <Route path="/appointments" element={<Appointments />} />
        <Route path="/billing" element={<Billing />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/medications" element={<Medications />} />
        <Route path="/diagnoses" element={<Diagnoses />} />
        <Route path="/profile" element={<Profile />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
