import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { getProfile, login as loginRequest } from "../api/auth";
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

  const isAuthenticated = computed(() => Boolean(token.value));
  const username = computed(() => user.value?.username ?? "Candidate");

  async function login(account: string, password: string) {
    const result = await loginRequest(account, password);
    token.value = result.access_token;
    localStorage.setItem(TOKEN_KEY, result.access_token);
    await loadUser();
  }

  async function loadUser() {
    if (!token.value) {
      user.value = null;
      return null;
    }

    try {
      user.value = await getProfile();
      localStorage.setItem(USER_KEY, JSON.stringify(user.value));
      return user.value;
    } catch (error) {
      logout();
      throw error;
    }
  }

  function logout() {
    token.value = "";
    user.value = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  function setUser(profile: AuthUser) {
    user.value = profile;
    localStorage.setItem(USER_KEY, JSON.stringify(profile));
  }

  return { token, user, username, isAuthenticated, login, logout, loadUser, setUser };
});
