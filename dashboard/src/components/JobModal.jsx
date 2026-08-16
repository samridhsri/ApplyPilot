import React, { useState, useEffect } from 'react';
import { ScoreBadge } from './ScoreBadge';
import { StatusBadge } from './StatusBadge';
import { X, ExternalLink, CheckCircle, RotateCcw, AlertTriangle, FileText, Send, Sparkles, Building2, MapPin, DollarSign } from 'lucide-react';

export function JobModal({ job, onClose, onUpdateStatus }) {
  const [activeTab, setActiveTab] = useState('description');
  const [fullJob, setFullJob] = useState(job);
  const [loadingDetails, setLoadingDetails] = useState(false);

  useEffect(() => {
    if (!job?.url) return;

    let isMounted = true;
    setLoadingDetails(true);

    fetch(`/api/job?url=${encodeURIComponent(job.url)}`)
      .then((res) => res.json())
      .then((data) => {
        if (isMounted && !data.error) {
          setFullJob(data);
        }
      })
      .catch((err) => console.error('Error fetching job details:', err))
      .finally(() => {
        if (isMounted) setLoadingDetails(false);
      });

    return () => {
      isMounted = false;
    };
  }, [job?.url]);

  if (!job) return null;

  // Extract keywords if in reasoning
  let keywordsList = [];
  if (fullJob.score_reasoning) {
    const kwMatch = fullJob.score_reasoning.match(/KEYWORDS:\s*([^\n]+)/i);
    if (kwMatch && kwMatch[1]) {
      keywordsList = kwMatch[1].split(',').map((k) => k.trim()).filter(Boolean);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="drawer-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="drawer-header">
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span className="card-company" style={{ fontSize: '15px' }}>{fullJob.site || 'Company'}</span>
              <StatusBadge job={fullJob} />
            </div>
            <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: '22px', fontWeight: 800, color: 'var(--text-primary)' }}>
              {fullJob.title || 'Untitled Role'}
            </h2>
            <div className="card-meta" style={{ marginTop: '8px' }}>
              {fullJob.location && (
                <div className="card-meta-item">
                  <MapPin size={13} /> {fullJob.location}
                </div>
              )}
              {fullJob.salary && (
                <div className="card-meta-item" style={{ color: 'var(--emerald)' }}>
                  <DollarSign size={13} /> {fullJob.salary}
                </div>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <ScoreBadge score={fullJob.fit_score} />
            <button className="btn btn-ghost btn-sm" onClick={onClose} style={{ padding: '8px', borderRadius: '50%' }}>
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', padding: '14px', background: 'var(--bg-primary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          <a
            href={fullJob.application_url || fullJob.url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary btn-sm"
          >
            Apply URL <ExternalLink size={13} />
          </a>

          {!fullJob.applied_at ? (
            <button
              className="btn btn-success btn-sm"
              onClick={() => onUpdateStatus(fullJob.url, 'applied')}
            >
              <CheckCircle size={13} /> Mark Applied
            </button>
          ) : (
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => onUpdateStatus(fullJob.url, 'reset')}
            >
              <RotateCcw size={13} /> Reset Applied
            </button>
          )}

          {fullJob.apply_status !== 'failed' ? (
            <button
              className="btn btn-danger btn-sm"
              onClick={() => onUpdateStatus(fullJob.url, 'failed', 'Manual mark as failed')}
            >
              <AlertTriangle size={13} /> Mark Failed
            </button>
          ) : (
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => onUpdateStatus(fullJob.url, 'reset')}
            >
              <RotateCcw size={13} /> Retry Job
            </button>
          )}
        </div>

        {/* Tab Navigation */}
        <div className="status-tabs" style={{ width: '100%' }}>
          <button
            className={`status-tab-btn ${activeTab === 'description' ? 'active' : ''}`}
            onClick={() => setActiveTab('description')}
            style={{ flex: 1, justifyContent: 'center' }}
          >
            Description
          </button>
          <button
            className={`status-tab-btn ${activeTab === 'analysis' ? 'active' : ''}`}
            onClick={() => setActiveTab('analysis')}
            style={{ flex: 1, justifyContent: 'center' }}
          >
            AI Fit Analysis
          </button>
          {fullJob.tailored_resume_text && (
            <button
              className={`status-tab-btn ${activeTab === 'resume' ? 'active' : ''}`}
              onClick={() => setActiveTab('resume')}
              style={{ flex: 1, justifyContent: 'center' }}
            >
              Tailored Resume
            </button>
          )}
          {fullJob.cover_letter_text && (
            <button
              className={`status-tab-btn ${activeTab === 'cover' ? 'active' : ''}`}
              onClick={() => setActiveTab('cover')}
              style={{ flex: 1, justifyContent: 'center' }}
            >
              Cover Letter
            </button>
          )}
        </div>

        {/* Tab Contents */}
        {activeTab === 'description' && (
          <div className="drawer-section">
            <div className="drawer-section-title">
              <Building2 size={15} /> Job Description
            </div>
            <div className="drawer-body-text" style={{ maxHeight: '420px' }}>
              {fullJob.full_description || fullJob.description || 'No full description available for this posting.'}
            </div>
          </div>
        )}

        {activeTab === 'analysis' && (
          <div className="drawer-section" style={{ gap: '16px' }}>
            {keywordsList.length > 0 && (
              <div>
                <div className="drawer-section-title" style={{ marginBottom: '8px' }}>
                  <Sparkles size={15} /> ATS Match Keywords
                </div>
                <div className="keywords-cloud">
                  {keywordsList.map((kw, i) => (
                    <span key={i} className="keyword-tag">{kw}</span>
                  ))}
                </div>
              </div>
            )}

            <div>
              <div className="drawer-section-title" style={{ marginBottom: '8px' }}>
                <FileText size={15} /> Evaluator Reasoning
              </div>
              <div className="drawer-body-text" style={{ maxHeight: '320px' }}>
                {fullJob.score_reasoning || 'Not scored by LLM yet.'}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'resume' && (
          <div className="drawer-section">
            <div className="drawer-section-title">
              <Sparkles size={15} /> Tailored Resume Output
            </div>
            <div className="drawer-body-text" style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', maxHeight: '440px' }}>
              {fullJob.tailored_resume_text}
            </div>
          </div>
        )}

        {activeTab === 'cover' && (
          <div className="drawer-section">
            <div className="drawer-section-title">
              <Send size={15} /> Generated Cover Letter
            </div>
            <div className="drawer-body-text" style={{ maxHeight: '440px' }}>
              {fullJob.cover_letter_text}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
