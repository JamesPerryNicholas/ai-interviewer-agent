import request from "./request";
import type { AuthUser, LoginResponse, RegisterPayload } from "../types";

export function register(payload: RegisterPayload) {
  return request.post<AuthUser>("/api/auth/register", payload).then((response) => response.data);
}

export function login(account: string, password: string) {
  return request.post<LoginResponse>("/api/auth/login", { account, password }).then((response) => response.data);
}

export function getProfile() {
  return request.get<AuthUser>("/api/user/profile").then((response) => response.data);
}

export async function logout(): Promise<void> {
  await request.post("/api/auth/logout");
}
