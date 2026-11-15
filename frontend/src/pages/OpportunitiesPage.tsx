import { useEffect, useState } from 'react';
import { Target, ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { getOpportunities } from '../api/client';

const STATUS_STYLES: Record<string, string> = {
  open: 'bg-blue-100 text-blue-700',
  won: 'bg-emerald-100 text-emerald-700',
  lost: 'bg-red-100 text-red-700',
};

const STAGE_STYLES: Record<string, string> = {
  discovery: 'bg-slate-100 text-slate-700',
  qualification: 'bg-cyan-100 text-cyan-700',
  proposal: 'bg-indigo-100 text-indigo-700',
  negotiation: 'bg-purple-100 text-purple-700',
  closed: 'bg-slate-200 text-slate-800',
};

export default function OpportunitiesPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [stageFilter, setStageFilter] = useState('');
  const [sortBy, setSortBy] = useState<'id' | 'amount' | 'created_at'>('amount');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    setLoading(true);
    getOpportunities({
      page,
      page_size: 25,
      q: q || undefined,
      status: statusFilter || undefined,
      stage: stageFilter || undefined,
      sort_by: sortBy,
      order,
    })
      .then(setData)
      .catch((e) => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false));
  }, [page, q, statusFilter, stageFilter, sortBy, order]);

  const fmtMoney = (n: number) =>
    n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `$${(n / 1e3).toFixed(0)}K` : `$${n}`;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Target size={24} /> Opportunity Pipeline
        </h1>
        <p className="text-slate-600 mt-1">
          {data ? `${data.total.toLocaleString()} opportunities` : 'Loading…'}
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[240px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search business ID or name…"
            value={q}
            onChange={(e) => { setQ(e.target.value); setPage(1); }}
            className="w-full pl-9 pr-4 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 outline-none"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="text-sm border border-slate-300 rounded-lg px-3 py-2 outline-none"
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="won">Won</option>
          <option value="lost">Lost</option>
        </select>

        <select
          value={stageFilter}
          onChange={(e) => { setStageFilter(e.target.value); setPage(1); }}
          className="text-sm border border-slate-300 rounded-lg px-3 py-2 outline-none"
        >
          <option value="">All stages</option>
          <option value="discovery">Discovery</option>
          <option value="qualification">Qualification</option>
          <option value="proposal">Proposal</option>
          <option value="negotiation">Negotiation</option>
          <option value="closed">Closed</option>
        </select>

        <select
          value={`${sortBy}:${order}`}
          onChange={(e) => {
            const [s, o] = e.target.value.split(':');
            setSortBy(s as any);
            setOrder(o as any);
          }}
          className="text-sm border border-slate-300 rounded-lg px-3 py-2 outline-none"
        >
          <option value="amount:desc">Amount (high → low)</option>
          <option value="amount:asc">Amount (low → high)</option>
          <option value="created_at:desc">Newest first</option>
        </select>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="p-12 flex justify-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-brand-600" />
          </div>
        ) : error ? (
          <div className="p-8 text-red-700">{error}</div>
        ) : !data?.items?.length ? (
          <div className="p-12 text-center text-slate-500">No opportunities match your filters.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Business ID</th>
                <th className="text-left px-4 py-3 font-medium">Name</th>
                <th className="text-left px-4 py-3 font-medium">Lead</th>
                <th className="text-left px-4 py-3 font-medium">Rep</th>
                <th className="text-right px-4 py-3 font-medium">Amount</th>
                <th className="text-left px-4 py-3 font-medium">Stage</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((opp: any) => (
                <tr key={opp.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 text-brand-600 font-medium">{opp.business_id}</td>
                  <td className="px-4 py-3 text-slate-700 truncate max-w-[200px]">{opp.name}</td>
                  <td className="px-4 py-3 text-slate-600 text-xs">{opp.lead_business_id}</td>
                  <td className="px-4 py-3 text-slate-700 truncate max-w-[150px]">{opp.rep_name}</td>
                  <td className="px-4 py-3 text-right font-semibold">{fmtMoney(opp.amount_usd)}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded ${STAGE_STYLES[opp.stage] || ''}`}>
                      {opp.stage}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded ${STATUS_STYLES[opp.status] || ''}`}>
                      {opp.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {data && data.pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <div className="text-sm text-slate-600">
            Page {data.page} of {data.pages} · {data.total.toLocaleString()} total
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={data.page === 1}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm hover:bg-slate-50 disabled:opacity-50 flex items-center gap-1"
            >
              <ChevronLeft size={16} /> Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
              disabled={data.page === data.pages}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm hover:bg-slate-50 disabled:opacity-50 flex items-center gap-1"
            >
              Next <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
