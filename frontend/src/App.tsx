import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { Incidents } from './pages/Incidents';
import { Detection } from './pages/Detection';
import { Actions } from './pages/Actions';
import { AgentLogs } from './pages/AgentLogs';
import { Settings } from './pages/Settings';
import { MLMetrics } from './pages/MLMetrics';
import { AuthPage } from './pages/AuthPage';
import { OrganizationPage } from './pages/Organization';
import { AcceptInvite } from './pages/AcceptInvite';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<AuthPage />} />
          <Route
            path="/invite/:token"
            element={
              <ProtectedRoute>
                <AcceptInvite />
              </ProtectedRoute>
            }
          />

          {/* Protected routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout>
                  <Dashboard />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/incidents"
            element={
              <ProtectedRoute>
                <Layout>
                  <Incidents />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/incidents/:id"
            element={
              <ProtectedRoute>
                <Layout>
                  <Incidents />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/detection"
            element={
              <ProtectedRoute>
                <Layout>
                  <Detection />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/actions"
            element={
              <ProtectedRoute>
                <Layout>
                  <Actions />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/logs"
            element={
              <ProtectedRoute>
                <Layout>
                  <AgentLogs />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/ml-metrics"
            element={
              <ProtectedRoute>
                <Layout>
                  <MLMetrics />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <Layout>
                  <Settings />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/organization"
            element={
              <ProtectedRoute>
                <Layout>
                  <OrganizationPage />
                </Layout>
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
