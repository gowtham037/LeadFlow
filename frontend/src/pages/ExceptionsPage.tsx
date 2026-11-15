import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle } from 'lucide-react';
import { getExceptions, resolveException } from '../api/client';

const SEVERITY_STYLES: Record<string, string> = {
  low: 'bg-slate-100 text-slate-700',
  medium: 'bg-blue-100 text-blue-700',
  high: 'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
};

const STATUS_STYLES: Record<string, string> = {
  open: 'bg-red-50 text-red-700',
  investigating: 'bg-amber-50 text-amber-700',
  resolved: 'bg-emerald-50 text-emerald-700',
  dismissed: 'bg-slate-50 text-slate-600',
};

export default function ExceptionsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');

  const reload = () => {
    setLoading(true);
    getExceptions({
      page_size: 100,
      status: statusFilter || undefined,
      severity: severityFilter || undefined,
    })
      .then(setData)
      .catch((e) => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, severityFilter]);

  const handleResolve = async (businessId: string) => {
    const details = prompt('Resolution details (optional):');
    try {
      await resolveException(businessId, 'resolved', details || undefined);
      reload();
    } catch (e: any) {
      alert(e.response?.data?.detail || e.message);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <AlertTriangle size={24} /> Exception Center
        </h1>
        <p className="text-slate-600 mt-1">
          {data ? `${data.total} anomalies surfaced` : 'Loading…'} — every violation is
          recorded, none silently fixed
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 flex gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm border border-slate-300 rounded-lg px-3 py-2 outline-none"
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="investigating">Investigating</option>
          <option value="resolved">Resolved</option>
          <option value="dismissed">Dismissed</option>
        </select>
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="text-sm border border-slate-300 rounded-lg px-3 py-2 outline-none"
        >
          <option value="">All severities</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="critical">Critical</option>
        </select>
      </div>

      {loading ? (
        <div className="p-12 flex justify-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-brand-600" />
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700">{error}</div>
      ) : !data?.items?.length ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-500">
          No exceptions match your filters. 🎉
        </div>
      ) : (
        <div className="space-y-3">
          {data.items.map((exc: any) => (
            <div key={exc.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="flex-1 min-w-[240px]">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-slate-900">{exc.business_id}</span>
                    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded ${SEVERITY_STYLES[exc.severity] || ''}`}>
                      {exc.severity.toUpperCase()}
                    </span>
                    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded ${STATUS_STYLES[exc.status] || ''}`}>
                      {exc.status}
                    </span>
                  </div>
                  <div className="text-sm text-slate-600 mt-2">
                    <strong>Type:</strong> {exc.issue_type} · {exc.entity_type}{' '}
                    <code className="bg-slate-100 px-1 rounded">{exc.entity_id}</code>
                  </div>
                  <div className="text-sm text-slate-600 mt-1">
                    <strong>Expected:</strong> {exc.expected_behavior}
                  </div>
                  <div className="text-sm text-red-700 mt-1">
                    <strong>Actual:</strong> {exc.actual_behavior}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <div className="text-xs text-slate-500">
                    Detected {new Date(exc.detected_at).toLocaleString()}
                  </div>
                  {exc.status === 'open' || exc.status === 'investigating' ? (
                    <button
                      onClick={() => handleResolve(exc.business_id)}
                      className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm rounded-lg"
                    >
                      <CheckCircle size={14} /> Resolve
                    </button>
                  ) : (
                    <div className="text-xs text-emerald-600 flex items-center gap-1">
                      <CheckCircle size={12} /> Resolved
                      {exc.resolved_at && ` · ${new Date(exc.resolved_at).toLocaleDateString()}`}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
