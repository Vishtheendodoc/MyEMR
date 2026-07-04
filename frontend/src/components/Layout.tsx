import { NavLink, Outlet, Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function Layout() {
  const { user, logout } = useAuth();

  if (!user) return <Navigate to="/login" replace />;

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `nav-link ${isActive ? 'active' : ''}`;

  return (
    <div className="container-fluid">
      <div className="row">
        <nav className="col-md-2 d-md-block sidebar py-3">
          <div className="position-sticky">
            <div className="text-center mb-4">
              <h5 className="text-white"><i className="fas fa-heartbeat"></i> Endo EMR</h5>
              <small className="text-white-50">Dr. {user.doctor_name}</small>
            </div>
            <ul className="nav flex-column px-3">
              <li className="nav-item"><NavLink to="/" end className={linkClass}><i className="fas fa-home me-2"></i>Dashboard</NavLink></li>
              <li className="nav-item"><NavLink to="/patients" className={linkClass}><i className="fas fa-users me-2"></i>Patients</NavLink></li>
              <li className="nav-item"><NavLink to="/follow-ups" className={linkClass}><i className="fas fa-calendar-check me-2"></i>Follow-ups</NavLink></li>
              <li className="nav-item"><NavLink to="/appointments" className={linkClass}><i className="fas fa-calendar-alt me-2"></i>Appointments</NavLink></li>
              <li className="nav-item"><NavLink to="/calculators" className={linkClass}><i className="fas fa-calculator me-2"></i>Calculators</NavLink></li>
              <li className="nav-item"><NavLink to="/billing" className={linkClass}><i className="fas fa-file-invoice-dollar me-2"></i>Billing</NavLink></li>
              <li className="nav-item"><NavLink to="/analytics" className={linkClass}><i className="fas fa-chart-bar me-2"></i>Analytics</NavLink></li>
              <li className="nav-item"><NavLink to="/medications" className={linkClass}><i className="fas fa-pills me-2"></i>Medications</NavLink></li>
              <li className="nav-item"><NavLink to="/diagnoses" className={linkClass}><i className="fas fa-stethoscope me-2"></i>Diagnoses</NavLink></li>
              <li className="nav-item"><NavLink to="/profile" className={linkClass}><i className="fas fa-user-md me-2"></i>Profile</NavLink></li>
              <li className="nav-item mt-3">
                <button className="nav-link btn btn-link text-start w-100" onClick={logout}>
                  <i className="fas fa-sign-out-alt me-2"></i>Logout
                </button>
              </li>
            </ul>
          </div>
        </nav>
        <main className="col-md-10 ms-sm-auto px-md-4 py-4">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
