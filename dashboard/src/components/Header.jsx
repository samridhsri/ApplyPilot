import React from 'react';
import { Compass, RefreshCw, Layers } from 'lucide-react';

export function Header({ totalJobs, onRefresh, loading }) {
  return (
    <header className="header-glass">
      <div className="brand-section">
        <div className="brand-logo">
          <Compass size={24} />
        </div>
        <div>
          <div className="brand-title">
            ApplyPilot <span className="brand-badge">Autonomous OS</span>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Tracking {totalJobs || 0} discovered jobs in SQLite Database
          </p>
        </div>
      </div>

      <div className="header-actions">
        <button
          className="btn btn-ghost btn-sm"
          onClick={onRefresh}
          disabled={loading}
          title="Refresh Data from DB"
        >
          <RefreshCw size={14} className={loading ? 'loading-spinner' : ''} />
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>
    </header>
  );
}
