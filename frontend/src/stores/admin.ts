import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { getAdminProfile, loginAdmin, ADMIN_KEY, ADMIN_TOKEN_KEY, type AdminAccount } from "../api/admin";

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
  const isAuthenticated = computed(() => Boolean(token.value));

  async function login(username: string, password: string) {
    const result = await loginAdmin(username, password);
    token.value = result.access_token;
    admin.value = result.admin;
    localStorage.setItem(ADMIN_TOKEN_KEY, result.access_token);
    localStorage.setItem(ADMIN_KEY, JSON.stringify(result.admin));
  }

  async function loadAdmin() {
    if (!token.value) return null;
    try {
      admin.value = await getAdminProfile();
      localStorage.setItem(ADMIN_KEY, JSON.stringify(admin.value));
      return admin.value;
    } catch (error) {
      logout();
      throw error;
    }
  }

  function logout() {
    token.value = "";
    admin.value = null;
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    localStorage.removeItem(ADMIN_KEY);
  }

  return { token, admin, isAuthenticated, login, loadAdmin, logout };
});
