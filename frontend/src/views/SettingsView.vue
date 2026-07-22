<script setup lang="ts">
import { Brush, Check, Clock, Key, Lock, Monitor, Refresh } from "@element-plus/icons-vue";
import axios from "axios";
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { changePassword, getLoginRecords } from "../api/user";
import { applyTheme, getThemeMode, type ThemeMode } from "../theme";
import type { LoginRecord } from "../types";

const currentPassword = ref("");
const newPassword = ref("");
const confirmPassword = ref("");
const changingPassword = ref(false);
const themeMode = ref<ThemeMode>(getThemeMode());
const loginRecords = ref<LoginRecord[]>([]);
const loadingRecords = ref(false);

const themeOptions: Array<{ value: ThemeMode; title: string; description: string; icon: typeof Brush }> = [
  { value: "light", title: "亮色", description: "适合白天使用", icon: Brush },
  { value: "dark", title: "暗色", description: "降低夜间视觉负担", icon: Monitor },
  { value: "system", title: "跟随系统", description: "自动匹配设备设置", icon: Refresh },
];

const passwordReady = computed(() => Boolean(currentPassword.value && newPassword.value && confirmPassword.value));

function selectTheme(mode: ThemeMode) {
  themeMode.value = mode;
  applyTheme(mode);
}

async function submitPassword() {
  if (!passwordReady.value) {
    ElMessage.warning("请完整填写密码信息");
    return;
  }
  if (newPassword.value.length < 8) {
    ElMessage.warning("新密码至少需要 8 位");
    return;
  }
  if (newPassword.value !== confirmPassword.value) {
    ElMessage.warning("两次输入的新密码不一致");
    return;
  }

  changingPassword.value = true;
  try {
    await changePassword(currentPassword.value, newPassword.value);
    currentPassword.value = "";
    newPassword.value = "";
    confirmPassword.value = "";
    ElMessage.success("密码修改成功");
  } catch (error) {
    ElMessage.error(axios.isAxiosError(error) ? error.message : "密码修改失败，请稍后重试");
  } finally {
    changingPassword.value = false;
  }
}

function formatLoginTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function deviceName(userAgent: string | null) {
  const agent = userAgent || "";
  const browser = agent.includes("Edg/") ? "Edge" : agent.includes("Chrome/") ? "Chrome" : agent.includes("Firefox/") ? "Firefox" : agent.includes("Safari/") ? "Safari" : "浏览器";
  const system = agent.includes("Windows") ? "Windows" : agent.includes("Mac OS") ? "macOS" : agent.includes("Android") ? "Android" : agent.includes("iPhone") ? "iPhone" : agent.includes("Linux") ? "Linux" : "未知设备";
  return `${system} · ${browser}`;
}

async function loadLoginRecords() {
  loadingRecords.value = true;
  try {
    loginRecords.value = (await getLoginRecords()).slice(0, 5);
  } catch (error) {
    ElMessage.error(axios.isAxiosError(error) ? error.message : "登录记录加载失败");
  } finally {
    loadingRecords.value = false;
  }
}

onMounted(loadLoginRecords);
</script>

<template>
  <div class="page-view settings-view">
    <section class="page-intro settings-intro">
      <div>
        <span class="eyebrow">ACCOUNT SETTINGS</span>
        <h1>设置</h1>
        <p>管理你的账号安全、主题偏好和登录活动。</p>
      </div>
    </section>

    <section class="settings-grid">
      <el-card class="surface-card settings-card password-card" shadow="never">
        <div class="settings-card-heading">
          <div class="settings-heading-icon purple"><el-icon><Key /></el-icon></div>
          <div><span class="eyebrow">SECURITY</span><h2>修改密码</h2><p>定期更新密码，保护你的面试资料和账号安全。</p></div>
        </div>
        <el-form class="settings-form" label-position="top" @submit.prevent="submitPassword">
          <el-form-item label="当前密码">
            <el-input v-model="currentPassword" type="password" show-password size="large" placeholder="请输入当前密码" autocomplete="current-password"><template #prefix><el-icon><Lock /></el-icon></template></el-input>
          </el-form-item>
          <el-form-item label="新密码">
            <el-input v-model="newPassword" type="password" show-password size="large" placeholder="至少 8 位字符" autocomplete="new-password"><template #prefix><el-icon><Key /></el-icon></template></el-input>
          </el-form-item>
          <el-form-item label="确认新密码">
            <el-input v-model="confirmPassword" type="password" show-password size="large" placeholder="再次输入新密码" autocomplete="new-password"><template #prefix><el-icon><Check /></el-icon></template></el-input>
          </el-form-item>
          <el-button class="settings-primary-button" native-type="submit" type="primary" size="large" :loading="changingPassword">保存新密码</el-button>
        </el-form>
      </el-card>

      <el-card class="surface-card settings-card theme-card" shadow="never">
        <div class="settings-card-heading">
          <div class="settings-heading-icon blue"><el-icon><Brush /></el-icon></div>
          <div><span class="eyebrow">APPEARANCE</span><h2>主题颜色</h2><p>选择你喜欢的工作区显示方式。</p></div>
        </div>
        <div class="theme-options">
          <button v-for="option in themeOptions" :key="option.value" class="theme-option" :class="{ selected: themeMode === option.value }" type="button" @click="selectTheme(option.value)">
            <span class="theme-preview" :class="`theme-preview-${option.value}`"><i></i><i></i><i></i></span>
            <span class="theme-option-copy"><strong>{{ option.title }}</strong><small>{{ option.description }}</small></span>
            <span v-if="themeMode === option.value" class="theme-check"><el-icon><Check /></el-icon></span>
          </button>
        </div>
      </el-card>
    </section>

    <el-card class="surface-card settings-card login-record-card" shadow="never">
      <div class="settings-card-heading login-record-heading">
        <div class="settings-heading-icon green"><el-icon><Clock /></el-icon></div>
        <div><span class="eyebrow">ACCOUNT ACTIVITY</span><h2>登录记录</h2><p>这里只展示成功登录，不会显示你的密码或登录凭证。</p></div>
        <el-button class="record-refresh-button" text :loading="loadingRecords" @click="loadLoginRecords"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
      <div v-loading="loadingRecords" class="login-record-list">
        <div v-for="record in loginRecords" :key="record.id" class="login-record-item">
          <div class="record-device-icon"><el-icon><Monitor /></el-icon></div>
          <div class="record-main"><strong>{{ deviceName(record.user_agent) }}</strong><small>{{ record.ip_address || "地址未知" }}</small></div>
          <div class="record-time"><strong>{{ formatLoginTime(record.login_at) }}</strong><small>登录成功</small></div>
          <span class="record-status"><i></i>登录成功</span>
        </div>
        <el-empty v-if="!loadingRecords && loginRecords.length === 0" description="暂时没有登录记录" :image-size="70" />
      </div>
    </el-card>
  </div>
</template>
