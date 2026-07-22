<script setup lang="ts">
import { ArrowLeft, ArrowRight, ChatDotRound } from "@element-plus/icons-vue";
import axios from "axios";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { listInterviews } from "../api/interview";
import type { InterviewListItem } from "../types";

const router = useRouter();
const interviews = ref<InterviewListItem[]>([]);
const loading = ref(true);
const error = ref("");

function formatInterviewDate(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusLabel(status: string) {
  if (status === "completed") return "已完成";
  if (status === "ended_early") return "已提前结束";
  if (status === "cancelled") return "已取消";
  return "进行中";
}

function statusType(item: InterviewListItem) {
  if (item.report_id && item.total_score !== null) return "success";
  if (["completed", "ended_early"].includes(item.status)) return "info";
  return "warning";
}

function openInterview(item: InterviewListItem) {
  router.push(item.report_id ? `/report/${item.id}` : `/interview/${item.id}`);
}

onMounted(async () => {
  try {
    interviews.value = await listInterviews();
  } catch (requestError) {
    error.value = axios.isAxiosError(requestError) ? requestError.message : "历史面试加载失败";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="page-view interview-history-view">
    <section class="page-intro">
      <div>
        <el-button text class="back-button" @click="router.push('/interview/new')">
          <el-icon><ArrowLeft /></el-icon> 返回模拟面试
        </el-button>
        <span class="eyebrow">面试记录</span>
        <h1>历史面试</h1>
        <p>查看之前的面试过程和评分结果，继续复盘和提升。</p>
      </div>
      <el-button type="primary" @click="router.push('/interview/new')">
        开始新面试 <el-icon><ArrowRight /></el-icon>
      </el-button>
    </section>

    <section class="surface-card interview-history-page-card">
      <el-skeleton v-if="loading" :rows="6" animated />
      <el-alert v-else-if="error" :title="error" type="warning" :closable="false" />
      <el-empty v-else-if="!interviews.length" description="暂无历史面试，完成第一次模拟面试后会显示在这里" />
      <div v-else class="interview-history-page-list">
        <button
          v-for="(item, index) in interviews"
          :key="item.id"
          type="button"
          class="interview-history-page-item"
          @click="openInterview(item)"
        >
          <span class="interview-history-page-icon"><el-icon><ChatDotRound /></el-icon></span>
          <span class="interview-history-page-copy">
            <strong>{{ item.position || "技术面试" }}</strong>
            <small>第 {{ interviews.length - index }} 场 · {{ formatInterviewDate(item.start_time) }}</small>
          </span>
          <span class="interview-history-page-result">
            <el-tag :type="statusType(item)" effect="light" round>
              {{ item.report_id && item.total_score !== null ? `${item.total_score} 分` : statusLabel(item.status) }}
            </el-tag>
            <span class="interview-history-page-action">
              {{ item.report_id ? "查看报告" : ["completed", "ended_early"].includes(item.status) ? "查看记录" : "继续面试" }}
              <el-icon><ArrowRight /></el-icon>
            </span>
          </span>
        </button>
      </div>
    </section>
  </div>
</template>
