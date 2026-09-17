/**
 * Layout Component
 * Global wrapper containing Navigation Bar and main content area
 */

import React from 'react';
import { Outlet, Link, NavLink, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Layout.css';

const Layout: React.FC = () => {
  const { isAuthenticated, isLoading, user, logout } = useAuth();

  if (isLoading) {
    return (
      <div className="app-loading">
        <div className="spinner"></div>
        <p>Loading user session...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="layout">
      {/* Navigation Bar */}
      <nav className="navbar">
        <div className="navbar-container">
          <Link to="/analytics" className="navbar-logo">
            AI Presentation
          </Link>

          <ul className="nav-links">
            <li className="nav-item">
              <NavLink to="/analyzer" className="nav-link">
                Document Analyzer
              </NavLink>
            </li>

            <li className="nav-item">
              <NavLink to="/speech" className="nav-link">
                Speech Analyzer
              </NavLink>
            </li>

            <li className="nav-item">
              <NavLink to="/live-coach" className="nav-link">
                Live Coach
              </NavLink>
            </li>

            <li className="nav-item">
              <NavLink to="/practice" className="nav-link">
                AI Coach
              </NavLink>
            </li>

            {/* NEW FEATURE */}
            <li className="nav-item">
              <NavLink to="/presentation-rewriter" className="nav-link">
                Presentation Rewriter
              </NavLink>
            </li>

            {/* NEW FEATURE: GENERATOR */}
            <li className="nav-item">
              <NavLink to="/presentation-generator" className="nav-link">
                Presentation Generator
              </NavLink>
            </li>

            {/* DOWNLOAD APP */}
            <li className="nav-item">
              <NavLink to="/download" className="nav-link">
                Download App
              </NavLink>
            </li>
          </ul>

          <div className="navbar-actions">
            <Link to="/analytics" className="user-name">
              {user?.name}
            </Link>
            <button onClick={logout} className="logout-btn">
              Logout
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="main-content">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="footer">
        <p>&copy; 2026 AI Presentation Analyzer | FYP Project | <Link to="/download" style={{ color: '#6366f1', textDecoration: 'none' }}>Download Desktop & Mobile Apps</Link></p>
      </footer>
    </div>
  );
};

export default Layout;