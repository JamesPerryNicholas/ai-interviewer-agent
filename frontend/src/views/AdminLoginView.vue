<script setup lang="ts">
import { ArrowLeft, ArrowRight, Lock, Monitor, User } from "@element-plus/icons-vue";
import axios from "axios";
import { ref } from "vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";

import { useAdminStore } from "../stores/admin";
import logoIcon from "../image/png/logo-icon.svg";

const router = useRouter();
const adminStore = useAdminStore();
const username = ref("");
const password = ref("");
const loading = ref(false);

async function submit() {
  if (!username.value.trim() || !password.value) {
    ElMessage.warning("请输入管理员账号和密码");
    return;
  }
  loading.value = true;
  try {
    await adminStore.login(username.value.trim(), password.value);
    await router.replace("/admin/usage");
  } catch (error) {
    ElMessage.error(axios.isAxiosError(error) ? error.message : "管理员登录失败");
  } finally {
    loading.value = false;
  }
}

function goUserLogin() {
  void router.push("/login");
}
</script>

<template>
  <div class="admin-login-page">
    <div class="admin-login-orb admin-login-orb-one"></div>
    <div class="admin-login-orb admin-login-orb-two"></div>
    <main class="admin-login-shell">
      <section class="admin-login-showcase">
        <div class="admin-login-brand"><span class="admin-login-logo"><img :src="logoIcon" alt="Interviewly" /></span><div><strong>Interviewly</strong><small>ADMIN CONSOLE</small></div></div>
        <div class="admin-login-showcase-copy">
          <span class="admin-login-overline">AI INTERVIEW AGENT · CONTROL CENTER</span>
          <h1>让每一次<br /><em>AI 调用</em> 都可见。</h1>
          <p>统一掌握 Token 消耗、响应效率与用户账号，让系统运营更清晰、更从容。</p>
          <div class="admin-login-feature-list">
            <span><i>✓</i>实时用量监控</span>
            <span><i>✓</i>安全账号管理</span>
            <span><i>✓</i>运营数据洞察</span>
          </div>
        </div>
        <div class="admin-login-mini-dashboard">
          <div class="mini-dashboard-head"><span>本周 Token 消耗</span><b>+18.6%</b></div>
          <strong>24,680 <small>Tokens</small></strong>
          <div class="mini-dashboard-bars"><i style="height: 34%"></i><i style="height: 52%"></i><i style="height: 43%"></i><i style="height: 69%"></i><i style="height: 58%"></i><i style="height: 86%"></i><i class="active" style="height: 72%"></i></div>
          <div class="mini-dashboard-days"><span>周一</span><span>周三</span><span>周五</span><span>今天</span></div>
        </div>
        <div class="admin-login-showcase-footer"><span class="admin-secure-dot"></span>系统运行正常 <small>SECURE &amp; PRIVATE</small></div>
      </section>

      <section class="admin-login-card">
        <div class="admin-login-card-top"><span class="admin-login-lock"><el-icon><Lock /></el-icon></span><span>安全登录</span><b>管理端</b></div>
        <div class="admin-login-heading">
          <span class="admin-login-overline">WELCOME BACK</span>
          <h2>欢迎回来，管理员</h2>
          <p>登录后继续管理 AI Interview Agent。</p>
        </div>
        <el-form class="admin-login-form" label-position="top" @submit.prevent="submit">
          <el-form-item label="管理员账号">
            <el-input v-model="username" size="large" placeholder="请输入管理员账号" autocomplete="username">
              <template #prefix><el-icon><User /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item label="管理员密码">
            <el-input v-model="password" size="large" type="password" show-password placeholder="请输入管理员密码" autocomplete="current-password" @keyup.enter="submit">
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
          <div class="admin-login-hint"><span><i></i>仅限授权管理员使用</span><span>JWT 安全加密</span></div>
          <el-button class="admin-login-button" native-type="submit" type="primary" size="large" :loading="loading">
            进入管理后台 <el-icon><ArrowRight /></el-icon>
          </el-button>
        </el-form>
        <button class="admin-back-link" type="button" @click="goUserLogin"><el-icon><ArrowLeft /></el-icon> 返回用户登录</button>
      </section>
    </main>
  </div>
</template>
