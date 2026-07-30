<script setup lang="ts">
import { Check, CopyDocument, Delete, MagicStick, Refresh, UserFilled } from "@element-plus/icons-vue";
import axios from "axios";
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { createManagedUser, deleteManagedUser, listManagedUsers, type CreatedUserAccount, type ManagedUser } from "../api/admin";
import { useAdminStore } from "../stores/admin";

const adminStore = useAdminStore();
const form = reactive({ username: "", password: "" });
const creating = ref(false);
const loading = ref(false);
const users = ref<ManagedUser[]>([]);
const createdAccount = ref<CreatedUserAccount | null>(null);

function validUsername(value: string) {
  return !value || /^[A-Za-z]+$/.test(value);
}

function isProtectedAccount(user: ManagedUser) {
  const username = user.username.trim().toLowerCase();
  const currentAdminUsername = adminStore.admin?.username?.trim().toLowerCase();
  return username === "admin" || Boolean(currentAdminUsername && username === currentAdminUsername);
}

function randomUsername() {
  const letters = "abcdefghijklmnopqrstuvwxyz";
  form.username = Array.from({ length: 10 }, () => letters[Math.floor(Math.random() * letters.length)]).join("");
}

function randomPassword() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789@#$%";
  form.password = Array.from({ length: 12 }, () => chars[Math.floor(Math.random() * chars.length)]).join("");
}

function copyTextFallback(value: string) {
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "-9999px";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("copy command failed");
}

async function copyText(value: string, label: string) {
  try {
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(value);
      } catch {
        copyTextFallback(value);
      }
    } else {
      copyTextFallback(value);
    }
    ElMessage.success(`${label}已复制`);
  } catch {
    ElMessage.error("复制失败，请检查浏览器剪贴板权限");
  }
}

async function createAccount() {
  if (!validUsername(form.username.trim())) {
    ElMessage.warning("账号名只能包含英文字母，不能包含数字、空格或中文");
    return;
  }
  if (form.password && form.password.length < 8) {
    ElMessage.warning("密码至少需要 8 位");
    return;
  }
  creating.value = true;
  try {
    createdAccount.value = await createManagedUser(form.username.trim() || undefined, form.password || undefined);
    form.username = "";
    form.password = "";
    await loadUsers();
    ElMessage.success("用户账号创建成功");
  } catch (error) {
    ElMessage.error(axios.isAxiosError(error) ? error.message : "账号创建失败");
  } finally {
    creating.value = false;
  }
}

async function loadUsers() {
  loading.value = true;
  try {
    users.value = await listManagedUsers();
  } catch (error) {
    ElMessage.error(axios.isAxiosError(error) ? error.message : "账号列表加载失败");
  } finally {
    loading.value = false;
  }
}

async function removeAccount(user: ManagedUser) {
  try {
    await ElMessageBox.confirm(
      `确认删除普通用户账号“${user.username}”？该账号的简历、岗位和面试记录也会被删除。`,
      "删除用户账号",
      {
        type: "warning",
        confirmButtonText: "删除账号",
        cancelButtonText: "取消",
        distinguishCancelAndClose: true,
        customClass: "admin-delete-message-box",
      },
    );
    await deleteManagedUser(user.id);
    users.value = users.value.filter((item) => item.id !== user.id);
    if (createdAccount.value?.id === user.id) createdAccount.value = null;
    ElMessage.success("用户账号已删除");
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(axios.isAxiosError(error) ? error.message : "删除账号失败");
  }
}

onMounted(loadUsers);
</script>

<template>
  <div class="admin-page">
    <section class="admin-page-heading">
      <div><span class="admin-kicker">ACCOUNT CENTER · USER ACCESS</span><h1>账号管理</h1><p>为用户创建安全、唯一的登录账号。</p></div>
      <el-button class="admin-refresh-button" plain :loading="loading" @click="loadUsers"><el-icon><Refresh /></el-icon> 刷新列表</el-button>
    </section>
    <section class="admin-user-layout">
      <el-card class="admin-create-card" shadow="never">
        <div class="admin-form-heading"><div class="admin-form-icon"><UserFilled /></div><div><span class="admin-kicker">NEW ACCOUNT</span><h2>创建用户账号</h2><p>可以手动填写，也可以使用随机生成。</p></div></div>
        <el-form label-position="top" @submit.prevent="createAccount">
          <el-form-item label="账号名"><div class="admin-input-action-row"><el-input v-model="form.username" size="large" placeholder="仅支持英文字母，例如 AlexUser"><template #prefix><UserFilled /></template></el-input><el-button class="admin-random-button" @click="randomUsername"><el-icon><MagicStick /></el-icon>随机</el-button></div><small class="admin-input-note">账号名只能使用 A-Z / a-z，系统会校验唯一性。</small></el-form-item>
          <el-form-item label="初始密码"><div class="admin-input-action-row"><el-input v-model="form.password" size="large" type="text" placeholder="留空则自动生成"><template #prefix><el-icon><Check /></el-icon></template></el-input><el-button class="admin-random-button" @click="randomPassword"><el-icon><MagicStick /></el-icon>随机</el-button></div><small class="admin-input-note">留空时自动生成 12 位安全密码。</small></el-form-item>
          <el-button type="primary" size="large" class="admin-create-button" :loading="creating" @click="createAccount">创建账号 <el-icon><UserFilled /></el-icon></el-button>
        </el-form>
      </el-card>

      <el-card v-if="createdAccount" class="admin-credential-card" shadow="never">
        <div class="credential-success"><span><el-icon><Check /></el-icon></span><div><strong>账号创建成功</strong><small>请及时复制并安全保存登录凭证</small></div></div>
        <div class="credential-row"><div><small>账号</small><strong>{{ createdAccount.username }}</strong></div><el-button text type="primary" @click="copyText(createdAccount.username, '账号')"><el-icon><CopyDocument /></el-icon>复制</el-button></div>
        <div class="credential-row"><div><small>密码</small><strong>{{ createdAccount.password }}</strong></div><el-button text type="primary" @click="copyText(createdAccount.password, '密码')"><el-icon><CopyDocument /></el-icon>复制</el-button></div>
        <div class="credential-email">系统邮箱：{{ createdAccount.email }}</div>
        <el-button class="copy-all-button" plain @click="copyText(`账号：${createdAccount.username}\n密码：${createdAccount.password}`, '账号和密码')">复制全部凭证</el-button>
      </el-card>
      <el-card v-else class="admin-credential-empty" shadow="never"><div class="empty-credential-icon"><UserFilled /></div><h3>等待创建账号</h3><p>创建成功后，账号和密码会在这里展示一次。</p></el-card>
    </section>

    <section class="admin-panel admin-users-panel">
      <div class="admin-panel-heading"><div><span class="admin-kicker">MANAGED USERS</span><h3>最近创建的账号</h3></div><span class="admin-record-count">最多展示 50 个</span></div>
      <el-table :data="users" stripe class="admin-table"><el-table-column label="账号" min-width="180"><template #default="scope"><strong>{{ scope.row.username }}</strong></template></el-table-column><el-table-column prop="email" label="系统邮箱" min-width="300" /><el-table-column label="创建时间" min-width="180"><template #default="scope">{{ new Date(scope.row.created_at).toLocaleString("zh-CN") }}</template></el-table-column><el-table-column label="操作" width="130" fixed="right"><template #default="scope"><span v-if="isProtectedAccount(scope.row)" class="admin-protected-label">管理员保留</span><el-button v-else class="admin-user-delete-button" text type="danger" @click="removeAccount(scope.row)"><el-icon><Delete /></el-icon>删除</el-button></template></el-table-column><template #empty><el-empty description="暂无用户账号" /></template></el-table>
    </section>
  </div>
</template>
