import axios from 'axios';

// Base URL is empty because Vite proxies /api → backend:8002
const api = axios.create({
  baseURL: '',
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT from localStorage on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('leadflow_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401, clear the token so auth context reacts and redirects to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('leadflow_token');
      localStorage.removeItem('leadflow_user');
    }
    return Promise.reject(err);
  },
);

export default api;

// ---------- Auth ----------

export interface UserInfo {
  business_id: string;
  email: string;
  full_name: string;
  role: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>('/api/auth/login', { email, password });
  return data;
}

export async function fetchMe(): Promise<UserInfo> {
  const { data } = await api.get<UserInfo>('/api/auth/me');
  return data;
}

// ---------- Analytics ----------

export async function getDashboard(): Promise<any> {
  const { data } = await api.get('/api/analytics/dashboard');
  return data;
}

export async function getLeadKPIs(): Promise<any> {
  const { data } = await api.get('/api/analytics/lead-kpis');
  return data;
}

export async function getOpportunityKPIs(): Promise<any> {
  const { data } = await api.get('/api/analytics/opportunity-kpis');
  return data;
}

export async function getFunnel(): Promise<any[]> {
  const { data } = await api.get('/api/analytics/funnel');
  return data;
}

export async function getCampaignPerformance(): Promise<any[]> {
  const { data } = await api.get('/api/analytics/campaign-performance');
  return data;
}

export async function getRepPerformance(): Promise<any[]> {
  const { data } = await api.get('/api/analytics/rep-performance');
  return data;
}

export async function getScoreCategoryPerformance(): Promise<any[]> {
  const { data } = await api.get('/api/analytics/score-category-performance');
  return data;
}

export async function getSLACompliance(): Promise<any> {
  const { data } = await api.get('/api/analytics/sla-compliance');
  return data;
}

// ---------- Leads ----------

export interface LeadListItem {
  id: number;
  business_id: string;
  company_name: string;
  contact_email: string;
  source: string;
  status: string;
  current_score: number | null;
  current_score_category: string | null;
  assigned_rep_name: string | null;
  created_at: string;
}

export interface LeadListResponse {
  items: LeadListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export async function getLeads(params: {
  page?: number;
  page_size?: number;
  q?: string;
  status?: string;
  category?: string;
  source?: string;
  sort_by?: string;
  order?: string;
}): Promise<LeadListResponse> {
  const { data } = await api.get<LeadListResponse>('/api/leads', { params });
  return data;
}

export async function getLead(businessId: string): Promise<any> {
  const { data } = await api.get(`/api/leads/${businessId}`);
  return data;
}

export async function getLeadSummary(): Promise<any> {
  const { data } = await api.get('/api/leads/stats/summary');
  return data;
}

// ---------- Opportunities ----------

export async function getOpportunities(params: {
  page?: number;
  page_size?: number;
  q?: string;
  status?: string;
  stage?: string;
  sort_by?: string;
  order?: string;
}): Promise<any> {
  const { data } = await api.get('/api/opportunities', { params });
  return data;
}

export async function getOpportunity(businessId: string): Promise<any> {
  const { data } = await api.get(`/api/opportunities/${businessId}`);
  return data;
}

export async function getOpportunitySummary(): Promise<any> {
  const { data } = await api.get('/api/opportunities/stats/summary');
  return data;
}

export async function advanceOpportunity(
  businessId: string,
  toStage: string,
  notes?: string,
): Promise<any> {
  const { data } = await api.post(`/api/opportunities/${businessId}/advance`, {
    to_stage: toStage,
    notes,
  });
  return data;
}

export async function closeOpportunity(
  businessId: string,
  status: 'won' | 'lost',
  wonReason?: string,
  lostReason?: string,
): Promise<any> {
  const { data } = await api.post(`/api/opportunities/${businessId}/close`, {
    status,
    won_reason: wonReason,
    lost_reason: lostReason,
  });
  return data;
}

// ---------- Exceptions ----------

export async function getExceptions(params: {
  page?: number;
  page_size?: number;
  status?: string;
  severity?: string;
  issue_type?: string;
}): Promise<any> {
  const { data } = await api.get('/api/exceptions', { params });
  return data;
}

export async function getException(businessId: string): Promise<any> {
  const { data } = await api.get(`/api/exceptions/${businessId}`);
  return data;
}

export async function resolveException(
  businessId: string,
  status: string,
  details?: string,
): Promise<any> {
  const { data } = await api.patch(`/api/exceptions/${businessId}`, {
    status,
    resolution_details: details,
  });
  return data;
}

export async function getExceptionSummary(): Promise<any> {
  const { data } = await api.get('/api/exceptions/stats/summary');
  return data;
}

// ---------- Admin ----------

export async function triggerRescore(): Promise<any> {
  const { data } = await api.post('/api/admin/rescore');
  return data;
}

export async function triggerRouting(): Promise<any> {
  const { data } = await api.post('/api/admin/route');
  return data;
}

export async function triggerTasks(): Promise<any> {
  const { data } = await api.post('/api/admin/tasks');
  return data;
}

export async function triggerOpportunities(): Promise<any> {
  const { data } = await api.post('/api/admin/opportunities');
  return data;
}

export async function runValidation(): Promise<any> {
  const { data } = await api.get('/api/admin/validate');
  return data;
}

export async function getPipelineStats(): Promise<any> {
  const { data } = await api.get('/api/admin/pipeline-stats');
  return data;
}

