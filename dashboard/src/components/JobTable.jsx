import React from 'react';
import { ScoreBadge } from './ScoreBadge';
import { StatusBadge } from './StatusBadge';
import { ExternalLink, ChevronUp, ChevronDown, MapPin, Building2 } from 'lucide-react';

export function JobTable({ jobs, onSelectJob, sortBy, order, onSort }) {
  const renderSortIndicator = (column) => {
    if (sortBy !== column) return null;
    return order === 'asc' ? <ChevronUp size={14} style={{ display: 'inline', marginLeft: 4 }} /> : <ChevronDown size={14} style={{ display: 'inline', marginLeft: 4 }} />;
  };

  return (
    <div className="table-container">
      <table className="job-table">
        <thead>
          <tr>
            <th className="sortable" onClick={() => onSort('score')} style={{ width: '80px', textAlign: 'center' }}>
              Fit {renderSortIndicator('score')}
            </th>
            <th className="sortable" onClick={() => onSort('title')}>
              Job Title & Details {renderSortIndicator('title')}
            </th>
            <th className="sortable" onClick={() => onSort('site')} style={{ width: '180px' }}>
              Source {renderSortIndicator('site')}
            </th>
            <th style={{ width: '150px' }}>Status</th>
            <th className="sortable" onClick={() => onSort('date')} style={{ width: '130px' }}>
              Discovered {renderSortIndicator('date')}
            </th>
            <th style={{ width: '60px', textAlign: 'center' }}>Link</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.url} onClick={() => onSelectJob(job)}>
              <td style={{ textAlign: 'center' }}>
                <ScoreBadge score={job.fit_score} />
              </td>
              <td>
                <div className="table-title">{job.title || 'Untitled Role'}</div>
                <div className="table-company-row">
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <Building2 size={12} /> {job.site || 'Unknown'}
                  </span>
                  {job.location && (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--text-muted)' }}>
                      • <MapPin size={12} /> {job.location}
                    </span>
                  )}
                  {job.salary && (
                    <span style={{ color: 'var(--emerald)', fontWeight: 500 }}>
                      • {job.salary}
                    </span>
                  )}
                </div>
              </td>
              <td>
                <span className="keyword-tag" style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--text-secondary)' }}>
                  {job.site || 'Direct'}
                </span>
              </td>
              <td>
                <StatusBadge job={job} />
              </td>
              <td style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {job.discovered_at ? job.discovered_at.split('T')[0] : '—'}
              </td>
              <td style={{ textAlign: 'center' }} onClick={(e) => e.stopPropagation()}>
                <a
                  href={job.application_url || job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-ghost btn-sm"
                  style={{ padding: '6px', borderRadius: '6px' }}
                  title="Open Job Posting"
                >
                  <ExternalLink size={14} />
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
