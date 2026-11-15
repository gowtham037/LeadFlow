import { useState } from 'react';
import { Settings, RefreshCw, Zap, CheckCircle, AlertCircle, ListChecks } from 'lucide-react';
import {
  runValidation, triggerRescore, triggerRouting, triggerTasks, triggerOpportunities,
} from '../api/client';

function ActionCard({
  title, description, icon: Icon, color, onClick, loading,
}: {
  title: string; description: string; icon: any; color: string;
  onClick: () => Promise<void> | void; loading: boolean;
}) {
  const [localLoading, setLocalLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const handle = async () => {
    setLocalLoading(true);
    setResult(null);
    setErr(null);
    try {
      await onClick();
      setResult('Completed');
    } catch (e: any) {
      setErr(e.response?.data?.detail || e.message);
    } finally {
      setLocalLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-start gap-3 mb-3">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
          <Icon size={20} />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-slate-900">{title}</h3>
          <p className="text-sm text-slate-600 mt-0.5">{description}</p>
        </div>
      </div>
      <button
        onClick={handle}
        disabled={localLoading || loading}
        className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg"
      >
        {localLoading ? (
          <>
            <RefreshCw size={14} className="animate-spin" /> Running…
          </>
        ) : (
          'Run'
        )}
      </button>
      {result && (
        <div className="mt-2 text-sm text-emerald-600 flex items-center gap-1">
          <CheckCircle size={14} /> {result}
        </div>
      )}
      {err && (
        <div className="mt-2 text-sm text-red-600 flex items-center gap-1">
          <AlertCircle size={14} /> {err}
        </div>
      )}
    </div>
  );
}

export default function AdminPage() {
  const [validation, setValidation] = useState<any>(null);
  const [validating, setValidating] = useState(false);

  const handleValidate = async () => {
    setValidating(true);
    try {
      const report = await runValidation();
      setValidation(report);
    } catch (e: any) {
      alert(e.response?.data?.detail || e.message);
    } finally {
      setValidating(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Settings size={24} /> Administration
        </h1>
        <p className="text-slate-600 mt-1">
          Run engines manually, audit data quality
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <ActionCard
          title="Re-score All Leads"
          description="Recompute scores for all 20k baseline leads using the v1 rule"
          icon={Zap}
          color="bg-purple-100 text-purple-700"
          onClick={async () => { await triggerRescore(); }}
          loading={false}
        />
        <ActionCard
          title="Route Qualified Leads"
          description="Assign territory + product matched reps to unassigned qualified leads"
          icon={ListChecks}
          color="bg-blue-100 text-blue-700"
          onClick={async () => { await triggerRouting(); }}
          loading={false}
        />
        <ActionCard
          title="Generate Follow-up Tasks"
          description="Create SLA-aware tasks for HOT/WARM/NURTURE leads with consent"
          icon={ListChecks}
          color="bg-amber-100 text-amber-700"
          onClick={async () => { await triggerTasks(); }}
          loading={false}
        />
        <ActionCard
          title="Convert Leads to Opportunities"
          description="Create opportunities for converted leads missing an opp record"
          icon={Zap}
          color="bg-emerald-100 text-emerald-700"
          onClick={async () => { await triggerOpportunities(); }}
          loading={false}
        />
        <ActionCard
          title="Run Data Validation"
          description="Execute all 18 data quality checks and generate report"
          icon={CheckCircle}
          color="bg-emerald-100 text-emerald-700"
          onClick={handleValidate}
          loading={validating}
        />
      </div>

      {validation && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-slate-900 text-lg">Validation Report</h2>
            <div className="flex gap-4 text-sm">
              <span className="text-emerald-600">✅ {validation.passed} passed</span>
              <span className="text-red-600">❌ {validation.failed} failed</span>
              {validation.critical > 0 && (
                <span className="text-red-800 font-semibold">
                  🚨 {validation.critical} critical
                </span>
              )}
            </div>
          </div>
          <div className="text-xs text-slate-500 mb-4">
            Executed {new Date(validation.executed_at).toLocaleString()}
          </div>
          <div className="space-y-2">
            {validation.checks?.map((check: any, i: number) => (
              <div
                key={i}
                className={`flex items-start justify-between gap-4 p-3 rounded-lg ${
                  check.passed ? 'bg-emerald-50' : 'bg-red-50'
                }`}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span>{check.passed ? '✅' : '❌'}</span>
                    <span className="font-medium text-sm">{check.name}</span>
                    <span className="text-xs text-slate-500">[{check.category}]</span>
                  </div>
                  {!check.passed && check.details && (
                    <div className="text-xs text-red-700 mt-1 ml-6">{check.details}</div>
                  )}
                </div>
                <div className="text-right">
                  <div className="text-sm font-semibold">{check.count_violations}</div>
                  <div className="text-xs text-slate-500">{check.severity}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
