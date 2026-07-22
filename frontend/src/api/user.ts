import request from "./request";
import type { AuthUser, LoginRecord } from "../types";

export async function updateProfile(displayName: string, careerStatus: string, avatar?: File): Promise<AuthUser> {
  const formData = new FormData();
  formData.append("display_name", displayName);
  formData.append("career_status", careerStatus);
  if (avatar) formData.append("avatar", avatar);
  const response = await request.patch<AuthUser>("/api/user/profile", formData);
  return response.data;
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await request.patch("/api/user/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function getLoginRecords(): Promise<LoginRecord[]> {
  const response = await request.get<LoginRecord[]>("/api/user/login-records");
  return response.data;
}
