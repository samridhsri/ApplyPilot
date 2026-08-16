import React from 'react';

export function ScoreBadge({ score }) {
  if (score === null || score === undefined || score === 0) {
    return <span className="score-badge score-null" title="Not scored yet">—</span>;
  }

  let colorClass = 'score-null';
  if (score >= 9) colorClass = 'score-9-10';
  else if (score >= 7) colorClass = 'score-7-8';
  else if (score >= 5) colorClass = 'score-5-6';
  else if (score >= 3) colorClass = 'score-3-4';
  else colorClass = 'score-1-2';

  return (
    <span className={`score-badge ${colorClass}`} title={`Fit Score: ${score}/10`}>
      {score}
    </span>
  );
}
