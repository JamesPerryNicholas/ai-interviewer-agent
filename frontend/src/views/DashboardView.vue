<script setup lang="ts">
import { ArrowRight, CircleCheck, Clock, Document, TrendCharts } from "@element-plus/icons-vue";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { useUserStore } from "../stores/user";
import { getLatestResume } from "../api/resume";
import { listInterviews } from "../api/interview";
import { listJobs } from "../api/job";
import type { InterviewListItem, JobPosition, ResumeResponse } from "../types";

const router = useRouter();
const userStore = useUserStore();
const { locale, t } = useI18n();
const latestResume = ref<ResumeResponse | null>(null);
const history = ref<InterviewListItem[]>([]);
const jobs = ref<JobPosition[]>([]);
const todayLabel = computed(() => {
  const language = locale.value === "zh-CN" ? "zh-CN" : locale.value === "ja" ? "ja-JP" : locale.value === "es" ? "es-ES" : "en-US";
  return new Intl.DateTimeFormat(language, {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
}).format(new Date());
});
const totalSessions = computed(() => history.value.length);
const recentHistory = computed(() => history.value.slice(0, 5));
const scoredSessions = computed(() => history.value.filter((item) => item.total_score !== null));
const averageScore = computed(() => {
  if (!scoredSessions.value.length) return null;
  const total = scoredSessions.value.reduce((sum, item) => sum + (item.total_score || 0), 0);
  return Math.round(total / scoredSessions.value.length);
});
const thisWeekSessions = computed(() => {
  const now = new Date();
  const day = now.getDay() || 7;
  const weekStart = new Date(now);
  weekStart.setDate(now.getDate() - day + 1);
  weekStart.setHours(0, 0, 0, 0);
  return history.value.filter((item) => new Date(item.start_time) >= weekStart).length;
});
const readinessScore = computed(() => {
  let score = 0;
  if (latestResume.value) score += 25;
  if (latestResume.value?.extracted_info) score += 25;
  if (jobs.value.length) score += 25;
  if (history.value.length) score += 25;
  return score;
});
const resumeCompleteness = computed(() => {
  const resume = latestResume.value;
  if (!resume) return 0;

  let score = 30; // 已上传简历
  if (resume.content?.trim()) score += 20; // 已提取 PDF 文本
  if (resume.extracted_info) score += 30; // 已完成 AI 分析
  if (resume.extracted_info?.skills?.length) score += 10;
  if (resume.extracted_info?.projects?.length || resume.extracted_info?.experience?.trim()) score += 10;
  return Math.min(score, 100);
});
const detectedSkills = computed(() => latestResume.value?.extracted_info?.skills?.filter(Boolean) ?? []);
const resumeUploadLabel = computed(() => (
  latestResume.value
    ? `上传于 ${new Date(latestResume.value.created_at).toLocaleDateString("zh-CN")}`
    : "尚未上传简历"
));

onMounted(async () => {
  try {
    await userStore.loadUser();
  } catch {
    await router.push({ name: "login", query: { redirect: "/dashboard" } });
    return;
  }

  try {
    [latestResume.value, history.value, jobs.value] = await Promise.all([getLatestResume(), listInterviews(), listJobs()]);
  } catch {
    // A new account may not have uploaded a resume yet.
  }
});

function scoreColor(score: number | null) {
  if (score === null) return "info";
  if (score >= 85) return "success";
  if (score >= 70) return "warning";
  return "danger";
}

function formatHistoryDate(value: string) {
  return new Date(value).toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
}

function historyStatusLabel(status: string) {
  if (status === "completed") return "已完成";
  if (status === "ended_early") return "已提前结束";
  return "进行中";
}
</script>

<template>
  <div class="page-view dashboard-view">
    <section class="page-intro dashboard-intro">
      <div>
        <span class="eyebrow">{{ todayLabel }}</span>
        <h1>{{ t("dashboard.greeting", { name: userStore.user?.display_name || userStore.user?.username || "Candidate" }) }} <span class="wave">👋</span></h1>
        <p>{{ t("dashboard.subtitle") }}</p>
        <div v-if="userStore.user" class="account-meta">
          <strong>{{ userStore.user.display_name || userStore.user.username }}</strong>
          <span>{{ userStore.user.email }}</span>
        </div>
      </div>
      <el-button type="primary" size="large" class="primary-cta" @click="router.push('/interview/new')">
        {{ t("dashboard.start") }} <el-icon><ArrowRight /></el-icon>
      </el-button>
    </section>

    <section class="metric-grid">
      <el-card class="metric-card accent-card" shadow="never">
        <div class="metric-top"><span class="metric-label">{{ t("dashboard.readiness") }}</span><span class="metric-icon violet"><TrendCharts /></span></div>
        <div class="metric-value">{{ readinessScore }}<span>%</span></div>
        <el-progress :percentage="readinessScore" :show-text="false" :stroke-width="6" color="#6d5dfc" />
        <div class="metric-foot"><span class="positive">{{ latestResume?.extracted_info ? "简历已完成AI分析" : "请完成简历分析" }}</span></div>
      </el-card>
      <el-card class="metric-card" shadow="never">
        <div class="metric-top"><span class="metric-label">{{ t("dashboard.sessions") }}</span><span class="metric-icon blue"><Clock /></span></div>
        <div class="metric-value">{{ totalSessions }}</div>
        <div class="metric-foot"><span class="positive">{{ thisWeekSessions }} {{ t("dashboard.thisWeek") }}</span> · {{ totalSessions }} {{ t("dashboard.total") }}</div>
      </el-card>
      <el-card class="metric-card" shadow="never">
        <div class="metric-top"><span class="metric-label">{{ t("dashboard.average") }}</span><span class="metric-icon green"><CircleCheck /></span></div>
        <div class="metric-value">{{ averageScore ?? "--" }}<span v-if="averageScore !== null">/100</span></div>
        <div class="metric-foot"><span class="positive">{{ scoredSessions.length }} 场</span> 已生成报告</div>
      </el-card>
    </section>

    <section class="dashboard-columns">
      <el-card class="surface-card resume-summary" shadow="never">
        <div class="card-heading">
          <div><span class="eyebrow">{{ t("dashboard.foundation") }}</span><h3>{{ t("dashboard.resumeTitle") }}</h3></div>
          <el-button text type="primary" @click="router.push('/resume')">{{ t("common.manage") }} <el-icon><ArrowRight /></el-icon></el-button>
        </div>
        <div class="resume-status-row">
          <div class="document-icon"><el-icon><Document /></el-icon></div>
          <div class="resume-file-copy"><strong>{{ latestResume?.original_filename || "尚未上传简历" }}</strong><span>{{ resumeUploadLabel }}</span></div>
          <el-tag v-if="latestResume?.content" type="success" effect="light" round>{{ t("common.parsed") }}</el-tag>
          <el-tag v-else type="info" effect="light" round>待解析</el-tag>
        </div>
        <div class="resume-progress-label"><span>{{ t("dashboard.completeness") }}</span><strong>{{ resumeCompleteness }}%</strong></div>
        <el-progress :percentage="resumeCompleteness" :show-text="false" :stroke-width="8" color="#2eaa73" />
        <div class="resume-skills"><span>{{ t("dashboard.detected") }}</span><div><el-tag v-for="skill in detectedSkills" :key="skill" effect="plain" round>{{ skill }}</el-tag><small v-if="!detectedSkills.length">完成AI分析后显示技能</small></div></div>
      </el-card>

      <el-card class="surface-card next-step-card" shadow="never">
        <div class="next-step-glow"></div>
        <span class="eyebrow light">{{ t("dashboard.recommended") }}</span>
        <h3>{{ t("dashboard.nextTitle") }}<br /><em>{{ t("dashboard.nextAccent") }}</em></h3>
        <p>{{ t("dashboard.nextDescription") }}</p>
        <el-button class="light-cta" @click="router.push('/interview/new')">{{ t("common.begin") }} <el-icon><ArrowRight /></el-icon></el-button>
      </el-card>
    </section>

    <section class="surface-card history-card">
      <div class="card-heading">
        <div><span class="eyebrow">{{ t("dashboard.progress") }}</span><h3>{{ t("dashboard.recent") }}</h3></div>
        <el-button text type="primary" @click="router.push('/interview/history')">{{ t("common.viewAll") }} <el-icon><ArrowRight /></el-icon></el-button>
      </div>
      <div class="history-list">
        <el-empty v-if="!history.length" description="暂无面试记录" />
        <div v-for="item in recentHistory" :key="item.id" class="history-item" @click="item.report_id ? router.push(`/report/${item.id}`) : router.push(`/interview/${item.id}`)">
          <div class="history-type"><span class="history-dot"></span><div><strong>{{ item.position || "技术面试" }}</strong><small>{{ formatHistoryDate(item.start_time) }} · {{ historyStatusLabel(item.status) }}</small></div></div>
          <div class="history-score"><el-tag :type="scoreColor(item.total_score)" effect="light" round>{{ item.total_score === null ? "待生成" : `${item.total_score} / 100` }}</el-tag><el-icon><ArrowRight /></el-icon></div>
        </div>
      </div>
    </section>
  </div>
</template>
