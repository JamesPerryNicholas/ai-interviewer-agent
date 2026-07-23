import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { getAdminProfile, loginAdmin, logoutAdmin, ADMIN_KEY, ADMIN_TOKEN_KEY, type AdminAccount } from "../api/admin";

function readAdmin(): AdminAccount | null {
  const stored = localStorage.getItem(ADMIN_KEY);
  if (!stored) return null;
  try {
    return JSON.parse(stored) as AdminAccount;
  } catch {
    localStorage.removeItem(ADMIN_KEY);
    return null;
  }
}

export const useAdminStore = defineStore("admin", () => {
  const token = ref(localStorage.getItem(ADMIN_TOKEN_KEY) ?? "");
  const admin = ref<AdminAccount | null>(readAdmin());
  const sessionValidated = ref(false);
  let validationPromise: Promise<AdminAccount | null> | null = null;
  const isAuthenticated = computed(() => Boolean(token.value));

  async function login(username: string, password: string) {
    const result = await loginAdmin(username, password);
    token.value = result.access_token;
    admin.value = result.admin;
    sessionValidated.value = true;
    localStorage.setItem(ADMIN_TOKEN_KEY, result.access_token);
    localStorage.setItem(ADMIN_KEY, JSON.stringify(result.admin));
  }

  async function loadAdmin() {
    if (!token.value) return null;
    try {
      admin.value = await getAdminProfile();
      sessionValidated.value = true;
      localStorage.setItem(ADMIN_KEY, JSON.stringify(admin.value));
      return admin.value;
    } catch (error) {
      clearSession();
      throw error;
    }
  }

  async function ensureSession() {
    if (!token.value) return false;
    if (sessionValidated.value && admin.value) return true;

    validationPromise ??= loadAdmin().finally(() => {
      validationPromise = null;
    });
    return Boolean(await validationPromise);
  }

  function clearSession() {
    token.value = "";
    admin.value = null;
    sessionValidated.value = false;
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    localStorage.removeItem(ADMIN_KEY);
  }

  async function logout() {
    try {
      if (token.value) await logoutAdmin();
    } finally {
      clearSession();
    }
  }

  return { token, admin, isAuthenticated, login, loadAdmin, ensureSession, logout };
});
