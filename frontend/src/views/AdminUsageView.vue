<script setup lang="ts">
import { Clock, DataAnalysis, Refresh, TrendCharts } from "@element-plus/icons-vue";
import * as echarts from "echarts";
import axios from "axios";
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { getUsageSummary, type UsageSummary } from "../api/admin";

const loading = ref(true);
const refreshing = ref(false);
const loadingRecent = ref(false);
const error = ref("");
const usage = ref<UsageSummary | null>(null);
const recentPage = ref(1);
const recentPageSize = 10;
const trendElement = ref<HTMLElement | null>(null);
const featureElement = ref<HTMLElement | null>(null);
let trendChart: echarts.ECharts | null = null;
let featureChart: echarts.ECharts | null = null;

const budgetPercent = computed(() => {
  if (!usage.value?.budget_tokens) return 0;
  return Math.min(100, Math.round((usage.value.today_tokens / usage.value.budget_tokens) * 100));
});
const featureLabels: Record<string, string> = {
  resume_analysis: "简历分析",
  resume_localization: "简历本地化",
  question_generation: "面试题生成",
  interview_chat: "模拟面试",
  interview_evaluation: "面试评分",
};

function featureName(feature: string) {
  return featureLabels[feature] || feature;
}

function formatNumber(value: number) {
  return value.toLocaleString("zh-CN");
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function renderCharts() {
  if (!usage.value) return;
  if (trendElement.value) {
    trendChart?.dispose();
    trendChart = echarts.init(trendElement.value);
    trendChart.setOption({
      grid: { left: 42, right: 18, top: 22, bottom: 28 },
      tooltip: { trigger: "axis", formatter: (params: Array<{ axisValue: string; data: number }>) => `${params[0]?.axisValue}<br/>Token：${formatNumber(params[0]?.data || 0)}` },
      xAxis: { type: "category", boundaryGap: false, data: usage.value.daily.map((item) => item.date.slice(5)), axisLine: { lineStyle: { color: "#eeeaf8" } }, axisLabel: { color: "#9a96aa", fontSize: 10 } },
      yAxis: { type: "value", splitLine: { lineStyle: { color: "#f2f0f7" } }, axisLabel: { color: "#aaa6b8", fontSize: 10 } },
      series: [{ type: "line", smooth: true, data: usage.value.daily.map((item) => item.total_tokens), symbol: "circle", symbolSize: 6, lineStyle: { color: "#6d5dfc", width: 3 }, itemStyle: { color: "#6d5dfc", borderColor: "#fff", borderWidth: 2 }, areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "rgba(109,93,252,.22)" }, { offset: 1, color: "rgba(109,93,252,0)" }]) } }],
    });
  }
  if (featureElement.value) {
    featureChart?.dispose();
    featureChart = echarts.init(featureElement.value);
    const featureData = usage.value.by_feature.map((item) => ({ name: featureName(item.feature), value: item.total_tokens }));
    featureChart.setOption({
      tooltip: { trigger: "item", formatter: "{b}<br/>Token：{c}（{d}%）" },
      legend: { bottom: 0, left: "center", textStyle: { color: "#898599", fontSize: 10 } },
      series: [{ type: "pie", radius: ["42%", "68%"], center: ["50%", "43%"], label: { show: false }, data: featureData.length ? featureData : [{ name: "暂无数据", value: 1, itemStyle: { color: "#eeeef5" } }], itemStyle: { borderColor: "#fff", borderWidth: 3 } }],
      color: ["#6d5dfc", "#5b9cf6", "#44c49a", "#f0b85c", "#e87b91"],
    });
  }
}

async function loadUsage(isRefresh = false, page = recentPage.value) {
  if (isRefresh) refreshing.value = true;
  else if (usage.value) loadingRecent.value = true;
  else loading.value = true;
  error.value = "";
  recentPage.value = page;
  try {
    usage.value = await getUsageSummary(7, page, recentPageSize);
    await nextTick();
    renderCharts();
  } catch (requestError) {
    error.value = axios.isAxiosError(requestError) ? requestError.message : "用量数据加载失败";
    if (isRefresh) ElMessage.error(error.value);
  } finally {
    loading.value = false;
    refreshing.value = false;
    loadingRecent.value = false;
  }
}

function changeRecentPage(page: number) {
  void loadUsage(false, page);
}

function resizeCharts() {
  trendChart?.resize();
  featureChart?.resize();
}

onMounted(() => {
  void loadUsage();
  window.addEventListener("resize", resizeCharts);
});
onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeCharts);
  trendChart?.dispose();
  featureChart?.dispose();
});
</script>

<template>
  <div class="admin-page">
    <section class="admin-page-heading">
      <div><span class="admin-kicker">OVERVIEW · TOKEN USAGE</span><h1>用量与成本看板</h1><p>掌握 AI 调用、Token 消耗和响应效率。</p></div>
      <el-button class="admin-refresh-button" plain :loading="refreshing" :disabled="refreshing" @click="loadUsage(true)"><el-icon><Refresh /></el-icon> 刷新数据</el-button>
    </section>
    <el-alert v-if="error" :title="error" type="error" :closable="false" class="admin-alert" />
    <el-skeleton v-if="loading && !usage" :rows="8" animated />
    <template v-else-if="usage">
      <section class="admin-budget-card">
        <div><span>今日 Token 消耗</span><strong>{{ formatNumber(usage.today_tokens) }}</strong><small v-if="usage.budget_tokens">/ {{ formatNumber(usage.budget_tokens) }}</small></div>
        <el-progress :percentage="budgetPercent" :show-text="false" :stroke-width="7" color="#6d5dfc" />
        <span class="admin-budget-caption">{{ usage.budget_tokens ? `今日预算使用 ${budgetPercent}%` : "当前未设置每日预算" }}</span>
      </section>
      <section class="admin-stat-grid">
        <el-card class="admin-stat-card purple" shadow="never"><div class="admin-stat-icon"><TrendCharts /></div><span>近 7 日 Token 消耗</span><strong>{{ formatNumber(usage.total_tokens) }}</strong><small>输入 {{ formatNumber(usage.prompt_tokens) }} · 输出 {{ formatNumber(usage.completion_tokens) }}</small></el-card>
        <el-card class="admin-stat-card blue" shadow="never"><div class="admin-stat-icon"><DataAnalysis /></div><span>LLM 调用次数</span><strong>{{ usage.total_calls }}</strong><small>当前统计窗口内的调用记录</small></el-card>
        <el-card class="admin-stat-card green" shadow="never"><div class="admin-stat-icon"><Clock /></div><span>平均响应时间</span><strong>{{ usage.average_latency_ms }}<em>ms</em></strong><small>P90 {{ usage.p90_latency_ms }}ms · P99 {{ usage.p99_latency_ms }}ms</small></el-card>
      </section>
      <section class="admin-chart-grid">
        <el-card class="admin-panel" shadow="never"><div class="admin-panel-heading"><div><span class="admin-kicker">LAST 7 DAYS</span><h3>Token 消耗趋势</h3></div><span class="admin-panel-unit">Tokens</span></div><div ref="trendElement" class="admin-chart"></div></el-card>
        <el-card class="admin-panel" shadow="never"><div class="admin-panel-heading"><div><span class="admin-kicker">LAST 7 DAYS</span><h3>调用分布</h3></div><span class="admin-panel-unit">按功能</span></div><div ref="featureElement" class="admin-chart admin-pie-chart"></div></el-card>
      </section>
      <section class="admin-panel admin-record-panel">
        <div class="admin-panel-heading"><div><span class="admin-kicker">RECENT ACTIVITY</span><h3>最近调用记录</h3></div><span class="admin-record-count">共 {{ usage.recent_total }} 条记录</span></div>
        <el-table :data="usage.recent" stripe class="admin-table"><el-table-column label="时间" min-width="145"><template #default="scope">{{ formatDate(scope.row.created_at) }}</template></el-table-column><el-table-column label="功能" min-width="125"><template #default="scope"><el-tag effect="light" round>{{ featureName(scope.row.feature) }}</el-tag></template></el-table-column><el-table-column prop="model" label="模型" min-width="125" /><el-table-column label="输入 Token" min-width="110"><template #default="scope">{{ formatNumber(scope.row.prompt_tokens) }}</template></el-table-column><el-table-column label="输出 Token" min-width="110"><template #default="scope">{{ formatNumber(scope.row.completion_tokens) }}</template></el-table-column><el-table-column label="总计" min-width="100"><template #default="scope"><strong>{{ formatNumber(scope.row.total_tokens) }}</strong></template></el-table-column><el-table-column label="延迟" min-width="90"><template #default="scope">{{ scope.row.latency_ms }}ms</template></el-table-column><template #empty><el-empty description="暂无调用记录" /></template></el-table>
        <div v-if="usage.recent_total > recentPageSize" class="admin-record-pagination"><el-pagination :current-page="recentPage" :page-size="recentPageSize" :total="usage.recent_total" :disabled="loadingRecent" background layout="prev, pager, next, jumper" @current-change="changeRecentPage" /></div>
      </section>
    </template>
  </div>
</template>
