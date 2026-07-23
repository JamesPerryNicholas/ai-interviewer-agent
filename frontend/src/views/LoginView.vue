<script setup lang="ts">
import { ArrowDown, Lock, MagicStick } from "@element-plus/icons-vue";
import { computed, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import type { FormInstance, FormRules } from "element-plus";

import { localeOptions, setLocale, type SupportedLocale } from "../i18n";
import { useUserStore } from "../stores/user";

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();
const { locale, t } = useI18n();
const currentLanguage = computed(() => localeOptions.find((item) => item.value === locale.value) ?? localeOptions[0]);
const formRef = ref<FormInstance>();
const loading = ref(false);

const form = reactive({
  account: "",
  password: "",
});

// Login accepts a username such as "admin"; the account field is intentionally
// validated only for being non-empty, not against an email format.
const rules: FormRules = {
  account: [
    {
      required: true,
      type: "string",
      message: () => t("login.requiredAccount"),
      trigger: "blur",
    },
  ],
  password: [
    { required: true, message: () => t("login.requiredPassword"), trigger: "blur" },
    { min: 8, message: () => t("login.passwordLength"), trigger: "blur" },
  ],
};

function changeLanguage(value: SupportedLocale) {
  setLocale(value);
}

async function handleLogin() {
  if (!formRef.value) return;
  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) return;

  loading.value = true;
  try {
    await userStore.login(form.account, form.password);
    ElMessage.success(t("login.welcome"));
    const requestedRedirect = typeof route.query.redirect === "string" ? route.query.redirect : "";
    // A numeric report/interview route may belong to the previous account.
    // Only preserve account-independent destinations after a fresh login.
    const safeRedirects = new Set([
      "/dashboard",
      "/resume",
      "/jobs",
      "/profile",
      "/settings",
      "/interview/history",
      "/interview/new",
    ]);
    const redirect = safeRedirects.has(requestedRedirect) ? requestedRedirect : "/dashboard";
    await router.push(redirect);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "登录失败，请稍后重试");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <section class="login-visual">
      <div class="visual-grid"></div>
      <div class="visual-content">
        <div class="brand-lockup login-brand">
          <div class="brand-mark">AI</div>
          <div>
            <strong>Interviewly</strong>
            <span>AI INTERVIEW STUDIO</span>
          </div>
        </div>
        <div class="visual-copy">
          <span class="eyebrow light">{{ t("login.heroEyebrow") }}</span>
          <h1>{{ t("login.heroTitle") }}<br /><em>{{ t("login.heroAccent") }}</em></h1>
          <p>{{ t("login.heroDescription") }}</p>
        </div>
        <div class="quote-card">
          <div class="quote-mark">“</div>
          <p>{{ t("login.quote") }}</p>
          <span>{{ t("login.quoteBy") }}</span>
        </div>
      </div>
      <div class="visual-orbit orbit-one"></div>
      <div class="visual-orbit orbit-two"></div>
    </section>

    <main class="login-panel">
      <div class="login-form-wrap">
        <div class="login-language">
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
        </div>
        <div class="mobile-brand brand-lockup">
          <div class="brand-mark">AI</div>
          <div>
            <strong>Interviewly</strong>
            <span>AI INTERVIEW STUDIO</span>
          </div>
        </div>
        <div class="login-heading">
          <div class="heading-icon"><el-icon><MagicStick /></el-icon></div>
          <span class="eyebrow">{{ t("login.eyebrow") }}</span>
          <h2>{{ t("login.title") }}</h2>
          <p>{{ t("login.description") }}</p>
        </div>

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleLogin">
          <el-form-item :label="t('login.account')" prop="account">
            <el-input v-model="form.account" size="large" :placeholder="t('login.accountPlaceholder')" autocomplete="username" />
          </el-form-item>
          <el-form-item :label="t('login.password')" prop="password">
            <el-input v-model="form.password" size="large" type="password" show-password :placeholder="t('login.passwordPlaceholder')" autocomplete="current-password">
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
          <div class="form-meta">
            <el-checkbox>{{ t("login.remember") }}</el-checkbox>
            <a href="#" @click.prevent>{{ t("login.forgot") }}</a>
          </div>
          <el-button class="login-button" type="primary" size="large" native-type="submit" :loading="loading">
            {{ t("login.submit") }}
          </el-button>
        </el-form>

        <div class="demo-note">
          <span class="demo-dot"></span>
          <span>{{ t("login.demo") }}</span>
        </div>
        <p class="login-footer">{{ t("login.terms") }} <a href="#" @click.prevent>{{ t("login.termsLink") }}</a> {{ t("login.privacy") }}.</p>
      </div>
    </main>
  </div>
</template>
