import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { StatsBar } from './components/StatsBar';
import { JobTable } from './components/JobTable';
import { JobGrid } from './components/JobGrid';
import { JobModal } from './components/JobModal';
import {
  Search,
  LayoutGrid,
  List,
  ChevronLeft,
  ChevronRight,
  Filter,
  CheckCircle2,
  Sparkles,
  Inbox,
  AlertCircle,
} from 'lucide-react';

export function App() {
  const [stats, setStats] = useState(null);
  const [sites, setSites] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [totalJobs, setTotalJobs] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);

  // Filter states
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedSite, setSelectedSite] = useState('all');
  const [minScore, setMinScore] = useState('');
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState('score');
  const [order, setOrder] = useState('desc');
  const [viewMode, setViewMode] = useState('table'); // 'table' | 'grid'

  // Modal / Drawer state
  const [selectedJob, setSelectedJob] = useState(null);

  // Load stats & sites
  const fetchStatsAndSites = useCallback(() => {
    fetch('/api/stats')
      .then((res) => res.json())
      .then((data) => setStats(data))
      .catch((err) => console.error('Error fetching stats:', err));

    fetch('/api/sites')
      .then((res) => res.json())
      .then((data) => setSites(data.sites || []))
      .catch((err) => console.error('Error fetching sites:', err));
  }, []);

  // Load jobs with current filters
  const fetchJobs = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({
      page: page.toString(),
      limit: '50',
      status: statusFilter,
      site: selectedSite,
      search: search,
      sort_by: sortBy,
      order: order,
    });

    if (minScore) params.append('min_score', minScore);

    fetch(`/api/jobs?${params.toString()}`)
      .then((res) => res.json())
      .then((data) => {
        setJobs(data.jobs || []);
        setTotalJobs(data.total || 0);
        setTotalPages(data.pages || 1);
      })
      .catch((err) => console.error('Error fetching jobs:', err))
      .finally(() => setLoading(false));
  }, [page, statusFilter, selectedSite, search, minScore, sortBy, order]);

  useEffect(() => {
    fetchStatsAndSites();
  }, [fetchStatsAndSites]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchJobs();
    }, 200);
    return () => clearTimeout(timer);
  }, [fetchJobs]);

  const handleSort = (column) => {
    if (sortBy === column) {
      setOrder(order === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setOrder('desc');
    }
  };

  const handleUpdateStatus = async (url, status, reason = '') => {
    try {
      const res = await fetch('/api/jobs/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, status, reason }),
      });
      const data = await res.json();
      if (data.status === 'ok') {
        // Refresh local items
        fetchJobs();
        fetchStatsAndSites();
        if (selectedJob && selectedJob.url === url) {
          setSelectedJob((prev) => ({
            ...prev,
            applied_at: status === 'applied' ? new Date().toISOString() : null,
            apply_status: status === 'failed' ? 'failed' : null,
          }));
        }
      }
    } catch (e) {
      console.error('Failed to update job status:', e);
    }
  };

  return (
    <div className="app-container">
      <Header
        totalJobs={stats?.total || totalJobs}
        onRefresh={() => {
          fetchStatsAndSites();
          fetchJobs();
        }}
        loading={loading}
      />

      <StatsBar stats={stats} />

      {/* Control & Filter Center */}
      <div className="controls-card">
        {/* Search */}
        <div className="search-wrapper">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Search by role, company, location, or ATS keyword..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>

        {/* Status Tabs */}
        <div className="status-tabs">
          <button
            className={`status-tab-btn ${statusFilter === 'all' ? 'active' : ''}`}
            onClick={() => {
              setStatusFilter('all');
              setPage(1);
            }}
          >
            All
          </button>
          <button
            className={`status-tab-btn ${statusFilter === 'high_fit' ? 'active' : ''}`}
            onClick={() => {
              setStatusFilter('high_fit');
              setPage(1);
            }}
          >
            <Sparkles size={13} style={{ color: 'var(--emerald)' }} /> 7+ Match
          </button>
          <button
            className={`status-tab-btn ${statusFilter === 'ready' ? 'active' : ''}`}
            onClick={() => {
              setStatusFilter('ready');
              setPage(1);
            }}
          >
            Ready to Apply
          </button>
          <button
            className={`status-tab-btn ${statusFilter === 'applied' ? 'active' : ''}`}
            onClick={() => {
              setStatusFilter('applied');
              setPage(1);
            }}
          >
            <CheckCircle2 size={13} style={{ color: 'var(--cyan)' }} /> Applied
          </button>
          <button
            className={`status-tab-btn ${statusFilter === 'failed' ? 'active' : ''}`}
            onClick={() => {
              setStatusFilter('failed');
              setPage(1);
            }}
          >
            Failed
          </button>
          <button
            className={`status-tab-btn ${statusFilter === 'unscored' ? 'active' : ''}`}
            onClick={() => {
              setStatusFilter('unscored');
              setPage(1);
            }}
          >
            Unscored
          </button>
        </div>

        {/* Dropdowns & View toggles */}
        <div className="filter-group">
          {/* Site Filter */}
          <select
            className="custom-select"
            value={selectedSite}
            onChange={(e) => {
              setSelectedSite(e.target.value);
              setPage(1);
            }}
          >
            <option value="all">All Job Sources ({sites.length})</option>
            {sites.map((site) => (
              <option key={site} value={site}>
                {site}
              </option>
            ))}
          </select>

          {/* Min Score Filter */}
          <select
            className="custom-select"
            value={minScore}
            onChange={(e) => {
              setMinScore(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Any Score</option>
            <option value="9">Score 9-10 (Perfect)</option>
            <option value="8">Score 8+ (Strong)</option>
            <option value="7">Score 7+ (Eligible)</option>
            <option value="5">Score 5+ (Moderate)</option>
          </select>

          {/* View Mode Toggle */}
          <div className="view-mode-toggle">
            <button
              className={`view-btn ${viewMode === 'table' ? 'active' : ''}`}
              onClick={() => setViewMode('table')}
              title="Table View"
            >
              <List size={16} />
            </button>
            <button
              className={`view-btn ${viewMode === 'grid' ? 'active' : ''}`}
              onClick={() => setViewMode('grid')}
              title="Card Grid View"
            >
              <LayoutGrid size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Main Job Listing View */}
      {loading && jobs.length === 0 ? (
        <div className="empty-state">
          <div className="loading-spinner"></div>
          <p>Loading jobs from database...</p>
        </div>
      ) : jobs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">
            <Inbox size={28} />
          </div>
          <h3>No jobs found matching your criteria</h3>
          <p>Try clearing filters or running the discovery stage (`applypilot run discover`).</p>
        </div>
      ) : viewMode === 'table' ? (
        <JobTable
          jobs={jobs}
          onSelectJob={setSelectedJob}
          sortBy={sortBy}
          order={order}
          onSort={handleSort}
        />
      ) : (
        <JobGrid jobs={jobs} onSelectJob={setSelectedJob} />
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="pagination-wrapper">
          <div>
            Showing <strong>{(page - 1) * 50 + 1}</strong> to{' '}
            <strong>{Math.min(page * 50, totalJobs)}</strong> of <strong>{totalJobs}</strong> jobs
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              className="btn btn-ghost btn-sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft size={14} /> Previous
            </button>
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              Page {page} of {totalPages}
            </span>
            <button
              className="btn btn-ghost btn-sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Next <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Detail Modal / Drawer */}
      {selectedJob && (
        <JobModal
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
          onUpdateStatus={handleUpdateStatus}
        />
      )}
    </div>
  );
}
