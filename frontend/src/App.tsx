import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './hooks/useAuth';
import Layout from './components/Layout';
import RoleRoute from './components/RoleRoute';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Patients from './pages/Patients';
import PatientDetail from './pages/PatientDetail';
import Patient360 from './pages/Patient360';
import Observations from './pages/Observations';
import Intelligence from './pages/Intelligence';
import MedicationSafety from './pages/MedicationSafety';
import PatientForm from './pages/PatientForm';
import VisitForm from './pages/VisitForm';
import VisitDetail from './pages/VisitDetail';
import PrescriptionPreview from './pages/PrescriptionPreview';
import Prescribe from './pages/Prescribe';
import Medications from './pages/Medications';
import Diagnoses from './pages/Diagnoses';
import Profile from './pages/Profile';
import StaffAccounts from './pages/StaffAccounts';
import ClinicSetup from './pages/ClinicSetup';
import FollowUpQueue from './pages/FollowUpQueue';
import Reminders from './pages/Reminders';
import Messages from './pages/Messages';
import PatientTimeline from './pages/PatientTimeline';
import PatientLabs from './pages/PatientLabs';
import DiabetesDashboard from './pages/DiabetesDashboard';
import GrowthChart from './pages/GrowthChart';
import Calculators from './pages/Calculators';
import Appointments from './pages/Appointments';
import Billing from './pages/Billing';
import Finance from './pages/Finance';
import DayClose from './pages/DayClose';
import PharmacyBilling from './pages/PharmacyBilling';
import StockDesk from './pages/StockDesk';
import Analytics from './pages/Analytics';
import { roleHome } from './utils/roles';

function HomeRedirect() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === 'doctor') return <Dashboard />;
  return <Navigate to={roleHome(user.role)} replace />;
}

function AppRoutes() {
  const { loading } = useAuth();
  if (loading) return <div className="text-center py-5">Loading...</div>;

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/login/:portal" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<Layout />}>
        <Route path="/" element={<RoleRoute><HomeRedirect /></RoleRoute>} />
        <Route path="/patients" element={<RoleRoute><Patients /></RoleRoute>} />
        <Route path="/patients/new" element={<RoleRoute><PatientForm /></RoleRoute>} />
        <Route path="/patients/:id" element={<RoleRoute><PatientDetail /></RoleRoute>} />
        <Route path="/patients/:id/360" element={<RoleRoute><Patient360 /></RoleRoute>} />
        <Route path="/patients/:id/observations" element={<RoleRoute><Observations /></RoleRoute>} />
        <Route path="/patients/:id/intelligence" element={<RoleRoute><Intelligence /></RoleRoute>} />
        <Route path="/patients/:id/medication-safety" element={<RoleRoute><MedicationSafety /></RoleRoute>} />
        <Route path="/patients/:id/edit" element={<RoleRoute><PatientForm /></RoleRoute>} />
        <Route path="/patients/:id/timeline" element={<RoleRoute><PatientTimeline /></RoleRoute>} />
        <Route path="/patients/:id/labs" element={<RoleRoute><PatientLabs /></RoleRoute>} />
        <Route path="/patients/:id/diabetes" element={<RoleRoute><DiabetesDashboard /></RoleRoute>} />
        <Route path="/patients/:id/growth" element={<RoleRoute><GrowthChart /></RoleRoute>} />
        <Route path="/patients/:patientId/visits/new" element={<RoleRoute><VisitForm /></RoleRoute>} />
        <Route path="/visits/:id" element={<RoleRoute><VisitDetail /></RoleRoute>} />
        <Route path="/visits/:id/edit" element={<RoleRoute><VisitForm /></RoleRoute>} />
        <Route path="/visits/:id/prescription-preview" element={<RoleRoute><PrescriptionPreview /></RoleRoute>} />
        <Route path="/visits/:id/prescribe" element={<RoleRoute><Prescribe /></RoleRoute>} />
        <Route path="/follow-ups" element={<RoleRoute><FollowUpQueue /></RoleRoute>} />
        <Route path="/reminders" element={<RoleRoute><Reminders /></RoleRoute>} />
        <Route path="/messages" element={<RoleRoute><Messages /></RoleRoute>} />
        <Route path="/calculators" element={<RoleRoute><Calculators /></RoleRoute>} />
        <Route path="/appointments" element={<RoleRoute><Appointments /></RoleRoute>} />
        <Route path="/billing" element={<RoleRoute><Billing /></RoleRoute>} />
        <Route path="/finance" element={<RoleRoute><Finance /></RoleRoute>} />
        <Route path="/day-close" element={<RoleRoute><DayClose /></RoleRoute>} />
        <Route path="/pharmacy" element={<RoleRoute><PharmacyBilling /></RoleRoute>} />
        <Route path="/stock-desk" element={<RoleRoute><StockDesk /></RoleRoute>} />
        <Route path="/analytics" element={<RoleRoute><Analytics /></RoleRoute>} />
        <Route path="/medications" element={<RoleRoute><Medications /></RoleRoute>} />
        <Route path="/diagnoses" element={<RoleRoute><Diagnoses /></RoleRoute>} />
        <Route path="/profile" element={<RoleRoute><Profile /></RoleRoute>} />
        <Route path="/staff" element={<RoleRoute><StaffAccounts /></RoleRoute>} />
        <Route path="/clinic" element={<RoleRoute><ClinicSetup /></RoleRoute>} />
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
