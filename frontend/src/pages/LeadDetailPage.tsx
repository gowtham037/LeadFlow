import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, User, Building2, Mail, CheckCircle, XCircle, Clock } from 'lucide-react';
import { getLead } from '../api/client';

function ScoreBar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-slate-600">{label}</span>
        <span className="font-medium text-slate-900">
          {value} / {max}
        </span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-brand-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function LeadDetailPage() {
  const { businessId } = useParams<{ businessId: string }>();
  const [lead, setLead] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!businessId) return;
    setLoading(true);
    getLead(businessId)
      .then(setLead)
      .catch((e) => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false));
  }, [businessId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (error || !lead) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-800">
          {error || 'Lead not found'}
        </div>
        <Link to="/leads" className="inline-flex items-center gap-1 text-brand-600 mt-4">
          <ArrowLeft size={16} /> Back to leads
        </Link>
      </div>
    );
  }

  const cat = lead.current_score_category;
  const catColor =
    cat === 'hot' ? 'bg-red-100 text-red-700' :
    cat === 'warm' ? 'bg-amber-100 text-amber-700' :
    cat === 'nurture' ? 'bg-blue-100 text-blue-700' :
    'bg-slate-100 text-slate-700';

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <Link to="/leads" className="inline-flex items-center gap-1 text-slate-600 hover:text-slate-900 text-sm">
        <ArrowLeft size={16} /> Back to leads
      </Link>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="text-sm text-slate-500">{lead.business_id}</div>
            <h1 className="text-2xl font-bold text-slate-900 mt-1">
              {lead.company?.name || 'Unknown company'}
            </h1>
            <div className="text-slate-600 mt-1">
              {lead.contact?.first_name} {lead.contact?.last_name}
              {lead.contact?.title && ` · ${lead.contact.title}`}
            </div>
          </div>
          <div className="text-right">
            <div className="text-4xl font-bold text-slate-900">
              {lead.current_score ?? '—'}
            </div>
            {cat && (
              <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium mt-1 ${catColor}`}>
                {cat}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Score breakdown */}
      {lead.score_detail && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="font-semibold text-slate-900 mb-4">Score Explanation</h2>
          <div className="space-y-3">
            <ScoreBar label="Fit" value={lead.score_detail.fit} max={30} />
            <ScoreBar label="Intent" value={lead.score_detail.intent} max={35} />
            <ScoreBar label="Engagement" value={lead.score_detail.engagement} max={25} />
            <ScoreBar label="Recency" value={lead.score_detail.recency} max={10} />
          </div>

          <details className="mt-6">
            <summary className="cursor-pointer text-sm font-medium text-brand-600 hover:text-brand-700">
              Show feature-level contributions ({lead.score_detail.contributions?.length || 0} features)
            </summary>
            <div className="mt-3 space-y-2">
              {lead.score_detail.contributions?.map((c: any, i: number) => (
                <div key={i} className="flex items-start justify-between gap-4 text-sm border-b border-slate-100 py-2">
                  <div>
                    <code className="text-xs bg-slate-100 px-1.5 py-0.5 rounded">
                      {c.feature}
                    </code>
                    <div className="text-slate-600 text-xs mt-1">{c.explanation}</div>
                  </div>
                  <div className="text-right whitespace-nowrap">
                    <span className="font-medium">{c.points}</span>
                    <span className="text-slate-400"> / {c.weight_max}</span>
                  </div>
                </div>
              ))}
            </div>
          </details>

          <div className="mt-4 text-xs text-slate-500">
            Rule version: {lead.score_detail.rule_version} · Scored at{' '}
            {new Date(lead.score_detail.scored_at).toLocaleString()}
          </div>
        </div>
      )}

      {/* Detail grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
            <Building2 size={18} /> Company
          </h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-600">Name</dt>
              <dd className="font-medium">{lead.company?.name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Industry</dt>
              <dd>{lead.company?.industry}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Employees</dt>
              <dd>{lead.company?.employee_count?.toLocaleString()}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Annual revenue</dt>
              <dd>${(lead.company?.annual_revenue_usd || 0).toLocaleString()}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Country</dt>
              <dd>{lead.company?.country}</dd>
            </div>
          </dl>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
            <User size={18} /> Lead
          </h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-600">Status</dt>
              <dd className="font-medium">{lead.status}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Source</dt>
              <dd>{lead.source}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Assigned rep</dt>
              <dd>{lead.assigned_rep?.full_name || '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Tasks</dt>
              <dd>{lead.tasks_count}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Created</dt>
              <dd>{new Date(lead.created_at).toLocaleDateString()}</dd>
            </div>
            {lead.converted_at && (
              <div className="flex justify-between">
                <dt className="text-slate-600">Converted</dt>
                <dd>{new Date(lead.converted_at).toLocaleDateString()}</dd>
              </div>
            )}
          </dl>
        </div>
      </div>

      {/* Consents */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
          <Mail size={18} /> Consent Status (per-channel)
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {lead.consents?.map((c: any) => (
            <div
              key={c.channel}
              className={`flex items-center gap-2 p-3 rounded-lg border ${
                c.status === 'granted'
                  ? 'bg-emerald-50 border-emerald-200'
                  : 'bg-red-50 border-red-200'
              }`}
            >
              {c.status === 'granted' ? (
                <CheckCircle size={16} className="text-emerald-600" />
              ) : (
                <XCircle size={16} className="text-red-600" />
              )}
              <div>
                <div className="text-sm font-medium capitalize">{c.channel}</div>
                <div className="text-xs capitalize">{c.status}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
