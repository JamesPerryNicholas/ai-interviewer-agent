<script setup lang="ts">
import logoIcon from "../image/png/logo-icon.svg";
import {
  ArrowDown,
  Bell,
  ChatDotRound,
  Clock,
  Document,
  House,
  Setting,
  UserFilled,
} from "@element-plus/icons-vue";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { localeOptions, setLocale, type SupportedLocale } from "../i18n";
import { useUserStore } from "../stores/user";
import { apiUrl } from "../api/base";

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const { locale, t } = useI18n();

const activeMenu = computed(() => route.path);
const currentLanguage = computed(() => localeOptions.find((item) => item.value === locale.value) ?? localeOptions[0]);
const pageTitle = computed(() => {
  const titleKey = typeof route.meta.titleKey === "string" ? route.meta.titleKey : "nav.overview";
  return t(titleKey);
});
const profileName = computed(() => userStore.user?.display_name || userStore.user?.username || "Candidate");
const profileStatus = computed(() => userStore.user?.career_status || t("nav.candidate"));
const avatarUrl = computed(() => apiUrl(userStore.user?.avatar_url));

function handleMenuSelect(path: string) {
  router.push(path);
}

function changeLanguage(value: SupportedLocale) {
  setLocale(value);
}

async function logout() {
  await userStore.logout();
  await router.push("/login");
}
</script>

<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <div class="brand-lockup">
        <div class="brand-mark">
        <img :src="logoIcon" alt="Interviewly" />
        </div>
        <div>
          <strong>Interviewly</strong>
          <span>AI INTERVIEW STUDIO</span>
        </div>
      </div>

      <div class="sidebar-label">{{ t("nav.workspace") }}</div>
      <el-menu :default-active="activeMenu" class="app-menu" @select="handleMenuSelect">
        <el-menu-item index="/dashboard">
          <el-icon><House /></el-icon>
          <span>{{ t("nav.overview") }}</span>
        </el-menu-item>
        <el-menu-item index="/resume">
          <el-icon><Document /></el-icon>
          <span>{{ t("nav.resume") }}</span>
        </el-menu-item>
        <el-menu-item index="/jobs">
          <el-icon><Document /></el-icon>
          <span>{{ t("nav.jobs") }}</span>
        </el-menu-item>
        <el-menu-item index="/interview/new">
          <el-icon><ChatDotRound /></el-icon>
          <span>{{ t("nav.practice") }}</span>
        </el-menu-item>
        <el-menu-item index="/interview/history">
          <el-icon><Clock /></el-icon>
          <span>历史面试</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-bottom">
        <el-menu :default-active="activeMenu" class="app-menu" @select="handleMenuSelect">
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>{{ t("nav.settings") }}</span>
          </el-menu-item>
        </el-menu>
        <div class="sidebar-tip">
          <span class="tip-dot"></span>
          <div>
            <strong>{{ t("nav.coachOnline") }}</strong>
            <small>{{ t("nav.ready") }}</small>
          </div>
        </div>
      </div>
    </aside>

    <section class="app-main">
      <header class="topbar">
        <div class="breadcrumb-area">
          <span class="eyebrow">AI INTERVIEW AGENT</span>
          <span class="breadcrumb-separator">/</span>
          <span class="breadcrumb-current">{{ pageTitle }}</span>
        </div>
        <div class="topbar-actions">
          <el-dropdown trigger="click" @command="changeLanguage">
            <button class="language-trigger" type="button" :aria-label="t('nav.language')">
              <span>{{ currentLanguage.short }}</span>
              <el-icon><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-for="item in localeOptions" :key="item.value" :command="item.value" :disabled="item.value === locale">
                  {{ item.label }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button class="icon-button" circle text :aria-label="t('nav.notifications')">
            <el-icon><Bell /></el-icon>
          </el-button>
          <el-divider direction="vertical" />
          <el-dropdown trigger="click">
            <button class="profile-trigger" type="button">
              <el-avatar :size="34" class="profile-avatar" :src="avatarUrl">
                <el-icon><UserFilled /></el-icon>
              </el-avatar>
              <span class="profile-copy">
                <strong>{{ profileName }}</strong>
                <small>{{ profileStatus }}</small>
              </span>
              <el-icon class="profile-chevron"><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push('/profile')">{{ t("nav.profile") }}</el-dropdown-item>
                <el-dropdown-item divided @click="logout">{{ t("nav.signOut") }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="page-content">
        <RouterView />
      </main>
    </section>
  </div>
</template>
