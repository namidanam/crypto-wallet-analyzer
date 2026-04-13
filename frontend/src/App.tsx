import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import FloatingTerminal from './components/FloatingTerminal';
import WalletsComparison from './pages/WalletsComparison';
import SystemDiagnostics from './pages/SystemDiagnostics';
import Dashboard from './pages/Dashboard';
import PastAnalyses from './pages/PastAnalyses';
import ApiReference from './pages/ApiReference';
import Support from './pages/Support';
import AboutFounders from './pages/AboutFounders';
import Login from './pages/Login';
import { useAuthStore } from './store/authStore';

/** Redirects unauthenticated users to /login */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

/** Inner layout that has access to location (must be inside <Router>) */
function AppLayout() {
  const location = useLocation();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const showTerminal = isAuthenticated && location.pathname !== '/login';

  return (
    <div className="vault-app-container">
      {showTerminal && <FloatingTerminal />}
      <main className="vault-content">
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />

          {/* Protected */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/wallets" element={<ProtectedRoute><WalletsComparison /></ProtectedRoute>} />
          <Route path="/past-analyses" element={<ProtectedRoute><PastAnalyses /></ProtectedRoute>} />
          <Route path="/diagnostics" element={<ProtectedRoute><SystemDiagnostics /></ProtectedRoute>} />
          <Route path="/api" element={<ProtectedRoute><ApiReference /></ProtectedRoute>} />
          <Route path="/support" element={<ProtectedRoute><Support /></ProtectedRoute>} />
          <Route path="/founders" element={<ProtectedRoute><AboutFounders /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AppLayout />
    </Router>
  );
}
