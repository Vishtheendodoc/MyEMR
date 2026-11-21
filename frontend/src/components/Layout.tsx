import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, Outlet, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { api, Patient, User } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { navVisible, ROLE_LABELS } from '../utils/roles';
import { openAppWindow } from '../utils/openWindow';
import ToolOverlay from './ToolOverlay';
import Calculators from '../pages/Calculators';
import PatientBanner from './PatientBanner';
import { mergePatients } from '../utils/chartContext';

export default function Layout() {
  const { user, logout, refreshUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const isPopup = new URLSearchParams(location.search).get('popup') === '1';
  const [navOpen, setNavOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [q, setQ] = useState('');
  const [results, setResults] = useState<Patient[]>([]);
  const [searchError, setSearchError] = useState('');
  const [searching, setSearching] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [calcOpen, setCalcOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const [doctors, setDoctors] = useState<User[]>([]);
  const [switching, setSwitching] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem('endo-theme') || 'light');

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `nav-link ${isActive ? 'active' : ''}`;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('endo-theme', theme);
  }, [theme]);

  useEffect(() => {
    if (!user) return;
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (e.target as HTMLElement)?.isContentEditable;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen(true);
        return;
      }
      if (e.key === '/' && !typing && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (e.key === '?' && !typing) {
        e.preventDefault();
        setHelpOpen(v => !v);
      }
      if ((e.key === 'c' || e.key === 'C') && !typing && (e.altKey || e.metaKey)) {
        e.preventDefault();
        if (navVisible(user.role, '/calculators')) setCalcOpen(true);
      }
      if (e.key === 'Escape') {
        setSearchOpen(false);
        setHelpOpen(false);
        setNavOpen(false);
        setCalcOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [user]);

  useEffect(() => {
    if (searchOpen) {
      setTimeout(() => searchRef.current?.focus(), 50);
    } else {
      setQ('');
      setResults([]);
    }
  }, [searchOpen]);

  useEffect(() => {
    if (!searchOpen || q.trim().length < 1) {
      setResults([]);
      setSearchError('');
      setSearching(false);
      return;
    }
    let cancel = false;
    const t = setTimeout(() => {
      const term = q.trim();
      setSearching(true);
      setSearchError('');
      Promise.allSettled([
        api.patients(term, 'name'),
        api.patients(term, 'mrd'),
        api.patients(term, 'phone'),
      ]).then(settled => {
        if (cancel) return;
        const groups = settled.flatMap(item => item.status === 'fulfilled' ? [item.value] : []);
        setResults(mergePatients(groups));
        if (settled.every(item => item.status === 'rejected')) {
          const reason = settled[0].status === 'rejected' ? settled[0].reason : null;
          setSearchError(reason instanceof Error ? reason.message : 'Search failed');
        }
      }).finally(() => {
        if (!cancel) setSearching(false);
      });
    }, 200);
    return () => {
      cancel = true;
      clearTimeout(t);
    };
  }, [q, searchOpen]);

  useEffect(() => {
    if (!user || !['registration', 'billing', 'pharmacy'].includes(user.role)) return;
    let cancel = false;
    api.doctors().then(async list => {
      if (cancel) return;
      setDoctors(list);
      if (!user.acting_doctor_id && list.length) {
        const sameClinic = list.filter(d => d.clinic_id === user.clinic_id);
        const pool = sameClinic.length ? sameClinic : list;
        const preferred = pool.find(d => !/demo/i.test(d.doctor_name || '')) || pool[0];
        if (preferred) {
          await api.setActingDoctor(preferred.id);
          if (!cancel) await refreshUser();
        }
      }
    }).catch(() => { if (!cancel) setDoctors([]); });
    return () => { cancel = true; };
  }, [user?.id, user?.role, user?.acting_doctor_id]);

  const shortcuts = useMemo(() => [
    { keys: 'Ctrl+K', desc: 'Search name, phone, or MRD' },
    { keys: '/', desc: 'Quick patient search' },
    { keys: 'Alt+C', desc: 'Open calculators (keeps current page)' },
    { keys: 'O', desc: 'Toggle Old Reports (on revisit form)' },
    { keys: '?', desc: 'Show keyboard shortcuts' },
    { keys: 'Esc', desc: 'Close panels / search' },
  ], []);

  if (!user) return <Navigate to="/login" replace />;

  const role = user.role;
  const isDesk = role === 'registration' || role === 'billing' || role === 'pharmacy';
  const show = (path: string) => navVisible(role, path);
  const closeNav = () => setNavOpen(false);

  const openPatient = (id: number) => {
    setSearchOpen(false);
    navigate(`/patients/${id}`);
  };

  const onSearchSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (results[0]) openPatient(results[0].id);
  };

  const selectedDoctorId = user.acting_doctor_id
    || doctors.find(d => d.clinic_id === user.clinic_id)?.id
    || doctors[0]?.id
    || '';
  const workingDoctor = doctors.find(d => d.id === Number(selectedDoctorId));
  const displayName = role === 'doctor'
    ? `Dr. ${user.doctor_name}`
    : (workingDoctor ? `Dr. ${workingDoctor.doctor_name}` : user.doctor_name);

  const chooseDoctor = async (doctorId: number) => {
    if (!doctorId || doctorId === user.acting_doctor_id) return;
    setSwitching(true);
    try {
      await api.setActingDoctor(doctorId);
      await refreshUser();
      const params = new URLSearchParams(location.search);
      if (params.has('visit') || params.has('patient')) {
        params.delete('visit');
        params.delete('patient');
        const next = params.toString();
        navigate({ pathname: location.pathname, search: next ? `?${next}` : '' }, { replace: true });
      }
    } finally {
      setSwitching(false);
    }
  };
  const roleLabel = ROLE_LABELS[role] || role;
  const showRoleLine =
    role === 'doctor' ||
    roleLabel.toLowerCase() !== (user.doctor_name || '').toLowerCase();

  const openToolWindow = (path: string) => {
    closeNav();
    openAppWindow(path);
  };

  if (isPopup) {
    return (
      <div className="popup-shell">
        <div className="popup-topbar no-print">
          <strong>Endo EMR</strong>
          <span className="text-muted small ms-2">Separate window — your other page stays open</span>
          <button type="button" className="btn btn-sm btn-outline-secondary ms-auto" onClick={() => window.close()}>
            Close window
          </button>
        </div>
        <main className="main-content popup-main">
          <Outlet />
        </main>
      </div>
    );
  }

  return (
    <div className={`app-shell ${navOpen ? 'nav-open' : ''}`}>
      <button type="button" className="nav-toggle no-print" aria-label="Menu" onClick={() => setNavOpen(v => !v)}>
        <i className={`fas ${navOpen ? 'fa-times' : 'fa-bars'}`}></i>
      </button>
      {navOpen && <div className="nav-backdrop no-print" onClick={closeNav} />}

      <nav className="sidebar">
        <div className="sidebar-brand">
          <h5><i className="fas fa-heartbeat me-2"></i>Endo EMR</h5>
          <small>{displayName}</small>
          {showRoleLine && (
            <div className="small mt-1" style={{ opacity: 0.7 }}>{roleLabel}</div>
          )}
        </div>
        {isDesk && doctors.length > 0 && (
          <label className="doctor-switch">
            <span><i className="fas fa-user-md"></i> Working for</span>
            <select
              value={selectedDoctorId}
              disabled={switching}
              onChange={e => chooseDoctor(Number(e.target.value))}
            >
              {doctors.map(d => (
                <option key={d.id} value={d.id}>Dr. {d.doctor_name}</option>
              ))}
            </select>
          </label>
        )}
        <ul className="nav flex-column" onClick={closeNav}>
          {show('/') && (
            <>
              <div className="nav-section">Home</div>
              <li className="nav-item"><NavLink to="/" end className={linkClass}><i className="fas fa-home me-2"></i>Dashboard</NavLink></li>
            </>
          )}

          {(show('/patients') || show('/appointments') || show('/follow-ups') || show('/reminders') || show('/calculators')) && (
            <div className="nav-section">Clinical</div>
          )}
          {show('/patients') && <li className="nav-item"><NavLink to="/patients" className={linkClass}><i className="fas fa-users me-2"></i>Patients</NavLink></li>}
          {user?.role === 'registration' && show('/billing') && (
            <li className="nav-item"><NavLink to="/billing" className={linkClass}><i className="fas fa-file-invoice-dollar me-2"></i>Billing</NavLink></li>
          )}
          {show('/follow-ups') && <li className="nav-item"><NavLink to="/follow-ups" className={linkClass}><i className="fas fa-calendar-check me-2"></i>Follow-ups</NavLink></li>}
          {show('/appointments') && <li className="nav-item"><NavLink to="/appointments" className={linkClass}><i className="fas fa-calendar-alt me-2"></i>Schedule</NavLink></li>}
          {show('/reminders') && <li className="nav-item"><NavLink to="/reminders" className={linkClass}><i className="fab fa-whatsapp me-2"></i>Reminders</NavLink></li>}
          {show('/messages') && <li className="nav-item"><NavLink to="/messages" className={linkClass}><i className="fab fa-whatsapp me-2"></i>Messages</NavLink></li>}
          {show('/calculators') && (
            <li className="nav-item">
              <div className="nav-tool-row">
                <button
                  type="button"
                  className={`nav-link btn btn-link text-start flex-grow-1 ${calcOpen || location.pathname.startsWith('/calculators') ? 'active' : ''}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    closeNav();
                    setCalcOpen(true);
                  }}
                >
                  <i className="fas fa-calculator me-2"></i>Calculators
                </button>
                <button
                  type="button"
                  className="btn btn-sm nav-window-btn"
                  title="Open in new window"
                  onClick={(e) => {
                    e.stopPropagation();
                    openToolWindow('/calculators');
                  }}
                >
                  <i className="fas fa-external-link-alt"></i>
                </button>
              </div>
            </li>
          )}

          {(show('/billing') || show('/pharmacy') || show('/finance') || show('/stock-desk') || show('/analytics') || show('/medications') || show('/diagnoses') || show('/day-close')) && (
            <div className="nav-section">Practice</div>
          )}
          {show('/billing') && user?.role !== 'registration' && <li className="nav-item"><NavLink to="/billing" className={linkClass}><i className="fas fa-file-invoice-dollar me-2"></i>Billing</NavLink></li>}
          {show('/finance') && <li className="nav-item"><NavLink to="/finance" className={linkClass}><i className="fas fa-coins me-2"></i>Finance</NavLink></li>}
          {show('/day-close') && <li className="nav-item"><NavLink to="/day-close" className={linkClass}><i className="fas fa-lock me-2"></i>Day close</NavLink></li>}
          {show('/pharmacy') && <li className="nav-item"><NavLink to="/pharmacy" className={linkClass}><i className="fas fa-pills me-2"></i>Pharmacy</NavLink></li>}
          {show('/stock-desk') && <li className="nav-item"><NavLink to="/stock-desk" className={linkClass}><i className="fas fa-boxes me-2"></i>Stock desk</NavLink></li>}
          {show('/analytics') && <li className="nav-item"><NavLink to="/analytics" className={linkClass}><i className="fas fa-chart-bar me-2"></i>Analytics</NavLink></li>}
          {show('/medications') && (
            <li className="nav-item">
              <div className="nav-tool-row">
                <NavLink to="/medications" className={linkClass}><i className="fas fa-capsules me-2"></i>Medications</NavLink>
                <button type="button" className="btn btn-sm nav-window-btn" title="Open in new window" onClick={(e) => { e.preventDefault(); e.stopPropagation(); openToolWindow('/medications'); }}>
                  <i className="fas fa-external-link-alt"></i>
                </button>
              </div>
            </li>
          )}
          {show('/diagnoses') && (
            <li className="nav-item">
              <div className="nav-tool-row">
                <NavLink to="/diagnoses" className={linkClass}><i className="fas fa-stethoscope me-2"></i>Diagnoses</NavLink>
                <button type="button" className="btn btn-sm nav-window-btn" title="Open in new window" onClick={(e) => { e.preventDefault(); e.stopPropagation(); openToolWindow('/diagnoses'); }}>
                  <i className="fas fa-external-link-alt"></i>
                </button>
              </div>
            </li>
          )}

          <div className="nav-section">Account</div>
          {role === 'doctor' && <li className="nav-item"><NavLink to="/staff" className={linkClass}><i className="fas fa-user-plus me-2"></i>Desk logins</NavLink></li>}
          {role === 'doctor' && <li className="nav-item"><NavLink to="/clinic" className={linkClass}><i className="fas fa-clinic-medical me-2"></i>Clinic setup</NavLink></li>}
          <li className="nav-item"><NavLink to="/profile" className={linkClass}><i className="fas fa-user me-2"></i>Profile</NavLink></li>
          <li className="nav-item mt-2">
            <button className="nav-link btn btn-link text-start w-100" onClick={logout}>
              <i className="fas fa-sign-out-alt me-2"></i>Logout
            </button>
          </li>
        </ul>
        {role === 'doctor' && (
          <button type="button" className="btn btn-sm btn-outline-light w-100 mt-3 shortcut-hint no-print" onClick={() => setHelpOpen(true)}>
            Shortcuts (?)
          </button>
        )}
      </nav>

      <main className="main-content">
        <div className="sticky-chrome no-print">
        <div className="topbar">
          <button type="button" className="btn btn-sm btn-outline-secondary d-lg-none" onClick={() => setNavOpen(true)} aria-label="Menu">
            <i className="fas fa-bars"></i>
          </button>
          {isDesk && workingDoctor && (
            <div className="topbar-context">
              <i className="fas fa-user-md"></i>
              <span>Dr. {workingDoctor.doctor_name}</span>
            </div>
          )}
          <div className="topbar-actions">
            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
              {theme === 'dark' ? 'Light' : 'Dark'}
            </button>
            {show('/patients') && (
              <button type="button" className="btn btn-sm btn-outline-primary" onClick={() => setSearchOpen(true)}>
                <i className="fas fa-search"></i>
                <span>Search</span>
                <kbd>Ctrl+K</kbd>
              </button>
            )}
            {show('/calculators') && (
              <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setCalcOpen(true)} title="Calculators (keeps this page)">
                <i className="fas fa-calculator"></i>
                <span>Calculators</span>
              </button>
            )}
          </div>
        </div>
        <PatientBanner />
        </div>
        <Outlet key={`${user.acting_doctor_id || 0}-${user.acting_clinic_id || user.clinic_id || 0}`} />
      </main>

      {searchOpen && (
        <div className="quick-search-backdrop" onClick={() => setSearchOpen(false)}>
          <div className="quick-search-panel" onClick={e => e.stopPropagation()}>
            <form onSubmit={onSearchSubmit}>
              <input
                ref={searchRef}
                className="form-control form-control-lg"
                placeholder="Name, phone, or MRD"
                aria-label="Search patients"
                value={q}
                onChange={e => setQ(e.target.value)}
              />
            </form>
            <div className="quick-search-results">
              {results.map(p => (
                <button type="button" key={p.id} className="quick-search-item" onClick={() => openPatient(p.id)}>
                  <strong>{p.name}</strong>
                  <span>{p.mrd_number || 'No MRD'} · {p.age} · {p.sex}{p.contact ? ` · ${p.contact}` : ''}</span>
                </button>
              ))}
              {searching && <div className="empty-state">Searching…</div>}
              {searchError && <div className="empty-state is-error" role="alert">{searchError}</div>}
              {!searching && !searchError && q.trim() && results.length === 0 && <div className="empty-state">No matches</div>}
            </div>
          </div>
        </div>
      )}

      {helpOpen && (
        <div className="quick-search-backdrop" onClick={() => setHelpOpen(false)}>
          <div className="quick-search-panel help-panel" onClick={e => e.stopPropagation()}>
            <div className="d-flex justify-content-between align-items-center mb-3">
              <h5 className="mb-0">Keyboard shortcuts</h5>
              <button type="button" className="btn btn-sm btn-light" onClick={() => setHelpOpen(false)}><i className="fas fa-times"></i></button>
            </div>
            <ul className="list-unstyled mb-0">
              {shortcuts.map(s => (
                <li key={s.keys} className="d-flex justify-content-between py-2 border-bottom">
                  <span>{s.desc}</span>
                  <kbd>{s.keys}</kbd>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {calcOpen && (
        <ToolOverlay
          title="Clinical calculators"
          onClose={() => setCalcOpen(false)}
          onOpenWindow={() => {
            setCalcOpen(false);
            openAppWindow('/calculators');
          }}
        >
          <Calculators />
        </ToolOverlay>
      )}
    </div>
  );
}
