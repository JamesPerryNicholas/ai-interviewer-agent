import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { getProfile, login as loginRequest, logout as logoutRequest } from "../api/auth";
import { TOKEN_KEY, USER_KEY } from "../api/request";
import type { AuthUser } from "../types";

function readStoredUser(): AuthUser | null {
  const storedUser = localStorage.getItem(USER_KEY);
  if (!storedUser) return null;

  try {
    return JSON.parse(storedUser) as AuthUser;
  } catch {
    localStorage.removeItem(USER_KEY);
    return null;
  }
}

export const useUserStore = defineStore("user", () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) ?? "");
  const user = ref<AuthUser | null>(readStoredUser());
  const sessionValidated = ref(false);
  let validationPromise: Promise<AuthUser | null> | null = null;

  const isAuthenticated = computed(() => Boolean(token.value));
  const username = computed(() => user.value?.username ?? "Candidate");

  async function login(account: string, password: string) {
    const result = await loginRequest(account, password);
    setToken(result.access_token);
    await loadUser();
  }

  function setToken(accessToken: string) {
    token.value = accessToken;
    sessionValidated.value = false;
    localStorage.setItem(TOKEN_KEY, accessToken);
  }

  async function loadUser() {
    if (!token.value) {
      user.value = null;
      return null;
    }

    try {
      user.value = await getProfile();
      sessionValidated.value = true;
      localStorage.setItem(USER_KEY, JSON.stringify(user.value));
      return user.value;
    } catch (error) {
      clearSession();
      throw error;
    }
  }

  async function ensureSession() {
    if (!token.value) return false;
    if (sessionValidated.value && user.value) return true;

    validationPromise ??= loadUser().finally(() => {
      validationPromise = null;
    });
    return Boolean(await validationPromise);
  }

  function clearSession() {
    token.value = "";
    user.value = null;
    sessionValidated.value = false;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  async function logout() {
    try {
      if (token.value) await logoutRequest();
    } finally {
      clearSession();
    }
  }

  function setUser(profile: AuthUser) {
    user.value = profile;
    localStorage.setItem(USER_KEY, JSON.stringify(profile));
  }

  return { token, user, username, isAuthenticated, login, logout, loadUser, ensureSession, setToken, setUser };
});
