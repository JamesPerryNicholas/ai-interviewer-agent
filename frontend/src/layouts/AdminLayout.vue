<script setup lang="ts">
import { DataAnalysis, Key, SwitchButton, UserFilled } from "@element-plus/icons-vue";
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAdminStore } from "../stores/admin";
import logoIcon from "../image/png/logo-icon.svg";

const route = useRoute();
const router = useRouter();
const adminStore = useAdminStore();
const activeMenu = computed(() => route.path);

async function logout() {
  await adminStore.logout();
  await router.replace("/login_Admin");
}
</script>

<template>
  <div class="admin-shell">
    <aside class="admin-sidebar">
      <div class="admin-brand"><div class="admin-brand-mark"><img :src="logoIcon" alt="Interviewly" /></div><div><strong>Interviewly</strong><span>ADMIN CONSOLE</span></div></div>
      <div class="admin-sidebar-label">管理中心</div>
      <el-menu :default-active="activeMenu" class="admin-menu" @select="(path: string) => router.push(path)">
        <el-menu-item index="/admin/usage"><el-icon><DataAnalysis /></el-icon><span>用量看板</span></el-menu-item>
        <el-menu-item index="/admin/users"><el-icon><UserFilled /></el-icon><span>账号管理</span></el-menu-item>
      </el-menu>
      <div class="admin-sidebar-bottom"><div class="admin-security-tip"><el-icon><Key /></el-icon><div><strong>安全模式</strong><small>管理员权限已启用</small></div></div></div>
    </aside>
    <main class="admin-main">
      <header class="admin-topbar"><div><span class="admin-topbar-kicker">AI INTERVIEW AGENT</span><span class="admin-topbar-separator">/</span><span>管理后台</span></div><div class="admin-profile-menu"><div class="admin-profile" tabindex="0" role="button" aria-label="管理员菜单"><span class="admin-online-dot"></span><span>{{ adminStore.admin?.username || "Admin" }}</span><el-avatar :size="32" class="admin-avatar"><el-icon><UserFilled /></el-icon></el-avatar></div><div class="admin-profile-dropdown"><div class="admin-profile-dropdown-heading"><el-icon><UserFilled /></el-icon><div><strong>{{ adminStore.admin?.username || "Admin" }}</strong><small>管理员账号</small></div></div><button class="admin-profile-logout" type="button" @click="logout"><el-icon><SwitchButton /></el-icon>退出后台</button></div></div></header>
      <div class="admin-content"><RouterView /></div>
    </main>
  </div>
</template>
