import React from 'react';
import { ScoreBadge } from './ScoreBadge';
import { StatusBadge } from './StatusBadge';
import { ExternalLink, MapPin, DollarSign, Calendar } from 'lucide-react';

export function JobGrid({ jobs, onSelectJob }) {
  return (
    <div className="job-grid">
      {jobs.map((job) => (
        <div key={job.url} className="job-card" onClick={() => onSelectJob(job)}>
          <div>
            <div className="card-header">
              <div>
                <span className="card-company">{job.site || 'General'}</span>
                <h3 className="card-title">{job.title || 'Untitled Role'}</h3>
              </div>
              <ScoreBadge score={job.fit_score} />
            </div>

            <div className="card-meta" style={{ marginTop: '8px' }}>
              {job.location && (
                <div className="card-meta-item">
                  <MapPin size={13} /> {job.location}
                </div>
              )}
              {job.salary && (
                <div className="card-meta-item" style={{ color: 'var(--emerald)' }}>
                  <DollarSign size={13} /> {job.salary}
                </div>
              )}
              {job.discovered_at && (
                <div className="card-meta-item">
                  <Calendar size={13} /> {job.discovered_at.split('T')[0]}
                </div>
              )}
            </div>

            {job.score_reasoning && (
              <div className="card-reasoning" style={{ marginTop: '14px' }}>
                {job.score_reasoning.replace(/^[A-Z]+:\s*/gm, '').trim()}
              </div>
            )}
          </div>

          <div className="card-footer">
            <StatusBadge job={job} />
            <a
              href={job.application_url || job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-ghost btn-sm"
              onClick={(e) => e.stopPropagation()}
            >
              Open URL <ExternalLink size={12} />
            </a>
          </div>
        </div>
      ))}
    </div>
  );
}
