import React from 'react';
import { CheckCircle2, AlertCircle, FileText, Sparkles, Clock } from 'lucide-react';

export function StatusBadge({ job }) {
  if (job.applied_at) {
    return (
      <span className="badge badge-applied">
        <CheckCircle2 size={12} /> Applied
      </span>
    );
  }

  if (job.apply_status === 'failed') {
    return (
      <span className="badge badge-failed">
        <AlertCircle size={12} /> Failed
      </span>
    );
  }

  if (job.tailored_resume_path) {
    return (
      <span className="badge badge-ready">
        <Sparkles size={12} /> Ready
      </span>
    );
  }

  if (job.fit_score >= 7) {
    return (
      <span className="badge badge-tailored">
        <FileText size={12} /> High Match
      </span>
    );
  }

  if (job.fit_score !== null && job.fit_score !== undefined) {
    return (
      <span className="badge badge-pending">
        <Clock size={12} /> Scored
      </span>
    );
  }

  return (
    <span className="badge badge-pending">
      <Clock size={12} /> Discovered
    </span>
  );
}
