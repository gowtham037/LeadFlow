import { useEffect, useState } from 'react';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts';
import { TrendingUp, Users, Target, DollarSign, AlertCircle, CheckCircle } from 'lucide-react';
import { getDashboard } from '../api/client';

const COLORS = ['#ef4444', '#f59e0b', '#3b82f6', '#94a3b8'];
const CATEGORY_LABELS: Record<string, string> = {
  hot: 'Hot', warm: 'Warm', nurture: 'Nurture', cold: 'Cold',
};

function KpiCard({
  icon: Icon, label, value, sub, color,
}: {
  icon: any; label: string; value: string; sub?: string; color: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-slate-600">{label}</span>
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
          <Icon size={18} />
        </div>
      </div>
      <div className="text-2xl font-bold text-slate-900">{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboard()
      .then(setData)
      .catch((e) => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-800">
          <AlertCircle className="inline mr-2" size={18} />
          {error}
        </div>
      </div>
    );
  }

  const leads = data.leads;
  const opps = data.opportunities;
  const funnel = data.funnel || [];
  const scoreCats = data.score_categories || [];
  const sla = data.sla || {};

  const pieData = scoreCats.map((s: any) => ({
    name: CATEGORY_LABELS[s.category] || s.category,
    value: s.leads,
    converted: s.converted,
    rate: s.conversion_rate,
  }));

  const fmtMoney = (n: number) =>
    n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `$${(n / 1e3).toFixed(0)}K` : `$${n}`;

  const fmtPct = (n: number) => `${(n * 100).toFixed(1)}%`;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Executive Dashboard</h1>
        <p className="text-slate-600 mt-1">
          Live pipeline intelligence across {leads.total_leads.toLocaleString()} leads
        </p>
      </div>

      {/* KPI row 1 — leads */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          icon={Users} label="Total Leads"
          value={leads.total_leads.toLocaleString()}
          sub={`${leads.hot_leads} hot · ${leads.warm_leads} warm`}
          color="bg-blue-100 text-blue-700"
        />
        <KpiCard
          icon={TrendingUp} label="Conversion Rate"
          value={fmtPct(leads.conversion_rate)}
          sub={`${leads.converted_leads.toLocaleString()} converted`}
          color="bg-emerald-100 text-emerald-700"
        />
        <KpiCard
          icon={Target} label="Opportunities"
          value={opps.total_opportunities.toLocaleString()}
          sub={`${opps.open_count} open · ${fmtPct(opps.win_rate)} win rate`}
          color="bg-purple-100 text-purple-700"
        />
        <KpiCard
          icon={DollarSign} label="Revenue Won"
          value={fmtMoney(opps.revenue_won)}
          sub={`${fmtMoney(opps.pipeline_value_open)} open pipeline`}
          color="bg-amber-100 text-amber-700"
        />
      </div>

      {/* KPI row 2 — ops */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <KpiCard
          icon={CheckCircle} label="Won Deals"
          value={opps.won_count.toLocaleString()}
          sub={`avg ${opps.avg_won_cycle_days.toFixed(1)} days to close`}
          color="bg-emerald-100 text-emerald-700"
        />
        <KpiCard
          icon={AlertCircle} label="Open Anomalies"
          value={`${sla.pending_overdue_count} overdue tasks`}
          sub={`${sla.total_tasks.toLocaleString()} total tasks`}
          color="bg-red-100 text-red-700"
        />
        <KpiCard
          icon={Users} label="Avg Deal Size"
          value={fmtMoney(opps.avg_deal_size)}
          sub={`${opps.lost_count} lost · ${fmtMoney(opps.revenue_lost)} lost value`}
          color="bg-slate-100 text-slate-700"
        />
      </div>

      {/* Funnel + Pie */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-4">Conversion Funnel</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={funnel} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis type="number" stroke="#64748b" fontSize={12} />
              <YAxis type="category" dataKey="name" stroke="#64748b" fontSize={12} width={130} />
              <Tooltip
                formatter={(v: any) => v.toLocaleString()}
                contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0' }}
              />
              <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-4">Score Distribution</h2>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                outerRadius={100}
                dataKey="value"
                label={({ name, value }: any) => `${name}: ${value}`}
                labelLine={false}
              >
                {pieData.map((_entry: any, i: number) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Score category performance — the money table */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h2 className="font-semibold text-slate-900 mb-1">Scoring Strategy Performance</h2>
        <p className="text-sm text-slate-500 mb-4">
          Conversion rate and revenue by lead tier — proves the scoring engine prioritizes correctly
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left px-3 py-2 font-medium">Tier</th>
                <th className="text-right px-3 py-2 font-medium">Leads</th>
                <th className="text-right px-3 py-2 font-medium">Converted</th>
                <th className="text-right px-3 py-2 font-medium">Conv. Rate</th>
                <th className="text-right px-3 py-2 font-medium">Won</th>
                <th className="text-right px-3 py-2 font-medium">Revenue</th>
              </tr>
            </thead>
            <tbody>
              {scoreCats.map((s: any) => (
                <tr key={s.category} className="border-t border-slate-100">
                  <td className="px-3 py-2">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                      s.category === 'hot' ? 'bg-red-100 text-red-700' :
                      s.category === 'warm' ? 'bg-amber-100 text-amber-700' :
                      s.category === 'nurture' ? 'bg-blue-100 text-blue-700' :
                      'bg-slate-100 text-slate-700'
                    }`}>
                      {CATEGORY_LABELS[s.category] || s.category}
                    </span>
                  </td>
                  <td className="text-right px-3 py-2">{s.leads.toLocaleString()}</td>
                  <td className="text-right px-3 py-2">{s.converted.toLocaleString()}</td>
                  <td className="text-right px-3 py-2 font-medium">{fmtPct(s.conversion_rate)}</td>
                  <td className="text-right px-3 py-2">{s.won}</td>
                  <td className="text-right px-3 py-2 font-medium">{fmtMoney(s.revenue_won)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Top campaigns + reps */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-4">Top Campaigns</h2>
          <table className="w-full text-sm">
            <thead className="text-slate-600">
              <tr>
                <th className="text-left pb-2 font-medium">Campaign</th>
                <th className="text-right pb-2 font-medium">Leads</th>
                <th className="text-right pb-2 font-medium">Conv.</th>
                <th className="text-right pb-2 font-medium">Revenue</th>
              </tr>
            </thead>
            <tbody>
              {(data.top_campaigns || []).map((c: any) => (
                <tr key={c.campaign_id} className="border-t border-slate-100">
                  <td className="py-2 truncate max-w-[200px]">{c.campaign_name}</td>
                  <td className="text-right py-2">{c.lead_count}</td>
                  <td className="text-right py-2">{fmtPct(c.conversion_rate)}</td>
                  <td className="text-right py-2 font-medium">{fmtMoney(c.revenue_won)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-4">Top Sales Reps</h2>
          <table className="w-full text-sm">
            <thead className="text-slate-600">
              <tr>
                <th className="text-left pb-2 font-medium">Rep</th>
                <th className="text-right pb-2 font-medium">Leads</th>
                <th className="text-right pb-2 font-medium">Won</th>
                <th className="text-right pb-2 font-medium">Revenue</th>
              </tr>
            </thead>
            <tbody>
              {(data.top_reps || []).map((r: any) => (
                <tr key={r.rep_id} className="border-t border-slate-100">
                  <td className="py-2 truncate max-w-[200px]">{r.full_name}</td>
                  <td className="text-right py-2">{r.assigned_leads}</td>
                  <td className="text-right py-2">{r.won_count}</td>
                  <td className="text-right py-2 font-medium">{fmtMoney(r.revenue_won)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
