import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, ChevronLeft, ChevronRight, Filter } from 'lucide-react';
import { getLeads } from '../api/client';
import type { LeadListItem } from '../api/client';

const CATEGORY_STYLES: Record<string, string> = {
  hot: 'bg-red-100 text-red-700',
  warm: 'bg-amber-100 text-amber-700',
  nurture: 'bg-blue-100 text-blue-700',
  cold: 'bg-slate-100 text-slate-700',
};

const STATUS_STYLES: Record<string, string> = {
  new: 'bg-slate-100 text-slate-700',
  scored: 'bg-indigo-100 text-indigo-700',
  qualified: 'bg-blue-100 text-blue-700',
  assigned: 'bg-purple-100 text-purple-700',
  working: 'bg-amber-100 text-amber-700',
  converted: 'bg-emerald-100 text-emerald-700',
  disqualified: 'bg-red-100 text-red-700',
  recycled: 'bg-slate-100 text-slate-700',
};

function Badge({ label, style }: { label: string; style: string }) {
  return (
    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded ${style}`}>
      {label}
    </span>
  );
}

export default function LeadsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [q, setQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [sortBy, setSortBy] = useState<'id' | 'score' | 'created_at'>('id');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    setLoading(true);
    getLeads({
      page,
      page_size: pageSize,
      q: q || undefined,
      status: statusFilter || undefined,
      category: categoryFilter || undefined,
      sort_by: sortBy,
      order,
    })
      .then(setData)
      .catch((e) => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false));
  }, [page, pageSize, q, statusFilter, categoryFilter, sortBy, order]);

  const handleSearch = (val: string) => {
    setQ(val);
    setPage(1);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Lead Management</h1>
        <p className="text-slate-600 mt-1">
          {data ? `${data.total.toLocaleString()} leads · filtered and paginated` : 'Loading…'}
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[240px]">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            type="text"
            placeholder="Search business ID, company, email…"
            value={q}
            onChange={(e) => handleSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter size={16} className="text-slate-500" />
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="text-sm border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-brand-500 outline-none"
          >
            <option value="">All statuses</option>
            <option value="new">New</option>
            <option value="scored">Scored</option>
            <option value="qualified">Qualified</option>
            <option value="assigned">Assigned</option>
            <option value="working">Working</option>
            <option value="converted">Converted</option>
            <option value="disqualified">Disqualified</option>
          </select>

          <select
            value={categoryFilter}
            onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
            className="text-sm border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-brand-500 outline-none"
          >
            <option value="">All tiers</option>
            <option value="hot">Hot</option>
            <option value="warm">Warm</option>
            <option value="nurture">Nurture</option>
            <option value="cold">Cold</option>
          </select>

          <select
            value={`${sortBy}:${order}`}
            onChange={(e) => {
              const [s, o] = e.target.value.split(':');
              setSortBy(s as any);
              setOrder(o as any);
            }}
            className="text-sm border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-brand-500 outline-none"
          >
            <option value="id:desc">Newest first</option>
            <option value="score:desc">Score (high → low)</option>
            <option value="score:asc">Score (low → high)</option>
            <option value="created_at:desc">Created (recent)</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="p-12 flex justify-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-brand-600" />
          </div>
        ) : error ? (
          <div className="p-8 text-red-700">{error}</div>
        ) : !data?.items?.length ? (
          <div className="p-12 text-center text-slate-500">
            No leads match your filters.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Business ID</th>
                <th className="text-left px-4 py-3 font-medium">Company</th>
                <th className="text-left px-4 py-3 font-medium">Contact</th>
                <th className="text-right px-4 py-3 font-medium">Score</th>
                <th className="text-left px-4 py-3 font-medium">Tier</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Rep</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((lead: LeadListItem) => (
                <tr
                  key={lead.id}
                  className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                >
                  <td className="px-4 py-3">
                    <Link
                      to={`/leads/${lead.business_id}`}
                      className="text-brand-600 hover:text-brand-700 font-medium"
                    >
                      {lead.business_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-700 truncate max-w-[180px]">
                    {lead.company_name}
                  </td>
                  <td className="px-4 py-3 text-slate-600 truncate max-w-[200px]">
                    {lead.contact_email}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold">
                    {lead.current_score ?? '—'}
                  </td>
                  <td className="px-4 py-3">
                    {lead.current_score_category ? (
                      <Badge
                        label={lead.current_score_category}
                        style={CATEGORY_STYLES[lead.current_score_category] || ''}
                      />
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      label={lead.status}
                      style={STATUS_STYLES[lead.status] || ''}
                    />
                  </td>
                  <td className="px-4 py-3 text-slate-600 truncate max-w-[150px]">
                    {lead.assigned_rep_name || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <div className="text-sm text-slate-600">
            Page {data.page} of {data.pages} · {data.total.toLocaleString()} total
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={data.page === 1}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
            >
              <ChevronLeft size={16} /> Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
              disabled={data.page === data.pages}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
            >
              Next <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
