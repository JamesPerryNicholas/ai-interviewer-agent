import axios from "axios";
import { API_BASE_URL } from "./base";

export const ADMIN_TOKEN_KEY = "ai-interviewer-admin-token";
export const ADMIN_KEY = "ai-interviewer-admin";

export interface AdminAccount {
  id: number;
  username: string;
  created_at: string;
}

export interface AdminLoginResponse {
  access_token: string;
  token_type: string;
  admin: AdminAccount;
}

export interface UsageDailyPoint {
  date: string;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
}

export interface UsageFeaturePoint {
  feature: string;
  total_tokens: number;
  calls: number;
}

export interface UsageRecord {
  id: number;
  feature: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency_ms: number;
  created_at: string;
}

export interface UsageSummary {
  range_days: number;
  budget_tokens: number | null;
  total_tokens: number;
  total_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  today_tokens: number;
  daily: UsageDailyPoint[];
  by_feature: UsageFeaturePoint[];
  p50_latency_ms: number;
  p90_latency_ms: number;
  p99_latency_ms: number;
  average_latency_ms: number;
  recent: UsageRecord[];
  recent_total: number;
  recent_page: number;
  recent_page_size: number;
}

export interface CreatedUserAccount {
  id: number;
  username: string;
  password: string;
  email: string;
  created_at: string;
}

export interface ManagedUser {
  id: number;
  username: string;
  email: string;
  created_at: string;
}

const adminRequest = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: { "Content-Type": "application/json" },
});

adminRequest.interceptors.request.use((config) => {
  const token = localStorage.getItem(ADMIN_TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

adminRequest.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail;
    if (detail) error.message = Array.isArray(detail) ? detail.map((item: { msg?: string }) => item.msg).join("；") : String(detail);
    if (error.response?.status === 401) {
      localStorage.removeItem(ADMIN_TOKEN_KEY);
      localStorage.removeItem(ADMIN_KEY);
      if (window.location.pathname !== "/login_Admin") {
        window.location.replace("/login_Admin");
      }
    }
    return Promise.reject(error);
  },
);

export async function loginAdmin(username: string, password: string): Promise<AdminLoginResponse> {
  const response = await adminRequest.post<AdminLoginResponse>("/api/admin/auth/login", { username, password });
  return response.data;
}

export async function getAdminProfile(): Promise<AdminAccount> {
  const response = await adminRequest.get<AdminAccount>("/api/admin/me");
  return response.data;
}

export async function logoutAdmin(): Promise<void> {
  await adminRequest.post("/api/admin/auth/logout");
}

export async function getUsageSummary(days = 7, page = 1, pageSize = 10): Promise<UsageSummary> {
  const response = await adminRequest.get<UsageSummary>("/api/admin/usage/summary", { params: { days, page, page_size: pageSize } });
  return response.data;
}

export async function createManagedUser(username?: string, password?: string): Promise<CreatedUserAccount> {
  const response = await adminRequest.post<CreatedUserAccount>("/api/admin/users", { username: username || null, password: password || null });
  return response.data;
}

export async function listManagedUsers(): Promise<ManagedUser[]> {
  const response = await adminRequest.get<ManagedUser[]>("/api/admin/users");
  return response.data;
}

export async function deleteManagedUser(userId: number): Promise<void> {
  await adminRequest.delete(`/api/admin/users/${userId}`);
}
