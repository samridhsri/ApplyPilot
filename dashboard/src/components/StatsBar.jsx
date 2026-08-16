import React from 'react';
import { Briefcase, Target, Sparkles, Send, CheckCircle2 } from 'lucide-react';

export function StatsBar({ stats }) {
  if (!stats) return null;

  const total = stats.total || 0;
  const scored = stats.scored || 0;
  const withDesc = stats.with_description || 0;
  const tailored = stats.tailored || 0;
  const applied = stats.applied || 0;
  const readyToApply = stats.ready_to_apply || 0;

  const highMatchCount = (stats.score_distribution || [])
    .filter(([score]) => score >= 7)
    .reduce((acc, [, count]) => acc + count, 0);

  const cards = [
    {
      label: 'Total Discovered',
      value: total,
      subtext: `${withDesc} enriched with full description`,
      icon: Briefcase,
      accent: 'var(--accent-primary)',
    },
    {
      label: 'Scored by AI',
      value: scored,
      subtext: total > 0 ? `${Math.round((scored / total) * 100)}% of pipeline scored` : '0%',
      icon: Target,
      accent: 'var(--amber)',
    },
    {
      label: 'High Match (7-10★)',
      value: highMatchCount,
      subtext: 'Optimal fit for resume tailoring',
      icon: Sparkles,
      accent: 'var(--emerald)',
    },
    {
      label: 'Tailored Resumes',
      value: tailored,
      subtext: `${readyToApply} ready to submit`,
      icon: Sparkles,
      accent: 'var(--purple)',
    },
    {
      label: 'Applications Sent',
      value: applied,
      subtext: stats.apply_errors > 0 ? `${stats.apply_errors} errors logged` : 'Auto-submission completed',
      icon: Send,
      accent: 'var(--cyan)',
    },
  ];

  return (
    <div className="stats-grid">
      {cards.map((card, idx) => {
        const Icon = card.icon;
        return (
          <div key={idx} className="stat-card" style={{ '--stat-accent': card.accent }}>
            <div className="stat-header">
              <span>{card.label}</span>
              <div className="stat-icon-wrapper">
                <Icon size={16} />
              </div>
            </div>
            <div className="stat-value">{card.value}</div>
            <div className="stat-footer">{card.subtext}</div>
          </div>
        );
      })}
    </div>
  );
}
