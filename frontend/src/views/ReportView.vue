<script setup lang="ts">
import { ArrowLeft, CircleCheck, Download, TrendCharts } from "@element-plus/icons-vue";
import axios from "axios";
import * as echarts from "echarts";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { useRoute, useRouter } from "vue-router";

import { downloadReportPdf, getReport } from "../api/report";
import type { EvaluationReport } from "../types";

const route = useRoute();
const router = useRouter();
const report = ref<EvaluationReport | null>(null);
const loading = ref(true);
const downloading = ref(false);
const error = ref("");
const radarElement = ref<HTMLElement | null>(null);
let radarChart: echarts.ECharts | null = null;

const interviewId = computed(() => Number(route.params.id));
const scoreColor = computed(() => (report.value && report.value.total_score >= 80 ? "#2eaa73" : "#6d5dfc"));

async function loadReport() {
  if (!Number.isInteger(interviewId.value) || interviewId.value <= 0) {
    error.value = "无效的面试编号";
    loading.value = false;
    return;
  }
  loading.value = true;
  try {
    report.value = await getReport(interviewId.value);
    await nextTick();
    renderRadar();
  } catch (requestError) {
    if (axios.isAxiosError(requestError) && requestError.response?.status === 404) {
      ElMessage.warning("该面试报告不存在或不属于当前账号");
      await router.replace("/interview/history");
      return;
    }
    error.value = "暂时无法加载评分报告，请确认面试已经结束";
    ElMessage.error(requestError instanceof Error ? requestError.message : error.value);
  } finally {
    loading.value = false;
  }
}

function renderRadar() {
  if (!radarElement.value || !report.value) return;
  radarChart?.dispose();
  radarChart = echarts.init(radarElement.value);
  radarChart.setOption({
    radar: {
      indicator: [
        { name: "技术能力", max: 100 },
        { name: "沟通表达", max: 100 },
        { name: "综合表现", max: 100 },
      ],
      radius: "66%",
      splitNumber: 4,
      axisName: { color: "#797687", fontSize: 12 },
      splitArea: { areaStyle: { color: ["#fff", "#fbfaff"] } },
      splitLine: { lineStyle: { color: "#e8e5f3" } },
      axisLine: { lineStyle: { color: "#e8e5f3" } },
    },
    series: [{
      type: "radar",
      data: [{
        value: [report.value.technical_score, report.value.communication_score, report.value.total_score],
        areaStyle: { color: "rgba(109, 93, 252, .18)" },
        lineStyle: { color: "#6d5dfc", width: 2 },
        itemStyle: { color: "#6d5dfc" },
      }],
    }],
  });
}

function resizeRadar() {
  radarChart?.resize();
}

async function downloadPdf() {
  downloading.value = true;
  try {
    await downloadReportPdf(interviewId.value);
    ElMessage.success("PDF报告已开始下载");
  } catch (requestError) {
    ElMessage.error(requestError instanceof Error ? requestError.message : "PDF下载失败");
  } finally {
    downloading.value = false;
  }
}

watch(report, () => void nextTick(renderRadar));
onMounted(() => {
  void loadReport();
  window.addEventListener("resize", resizeRadar);
});
onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeRadar);
  radarChart?.dispose();
});
</script>

<template>
  <div class="page-view report-view">
    <section class="page-intro report-intro">
      <div>
        <el-button text class="back-button" @click="router.back"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <span class="eyebrow">面试评估</span>
        <h1>面试评分报告</h1>
        <p>AI根据完整面试过程生成的能力反馈、逐题分析与提升建议。</p>
      </div>
      <el-button type="primary" plain :loading="downloading" @click="downloadPdf"><el-icon><Download /></el-icon> 下载PDF报告</el-button>
    </section>

    <el-skeleton v-if="loading" :rows="8" animated />
    <el-alert v-else-if="error" :title="error" type="warning" :closable="false" />
    <template v-else-if="report">
      <section class="report-hero surface-card">
        <div class="score-ring" :style="{ borderRightColor: scoreColor }"><div><strong>{{ report.total_score }}</strong><span>/ 100</span></div></div>
        <div class="score-copy"><span class="eyebrow">综合评分</span><h2>{{ report.total_score >= 80 ? "表现优秀，继续保持" : "基础扎实，仍有提升空间" }}</h2><p>评分依据包括技术能力、项目真实性、沟通表达和问题深度。</p><div class="score-meta"><span><i class="score-dot green"></i> 技术能力 {{ report.technical_score }}</span><span><i class="score-dot violet"></i> 沟通表达 {{ report.communication_score }}</span></div></div>
        <div ref="radarElement" class="report-radar"></div>
      </section>

      <section class="report-columns">
        <el-card class="surface-card report-list-card" shadow="never"><div class="card-heading"><div><span class="eyebrow">能力亮点</span><h3>优点</h3></div><span class="round-icon green"><CircleCheck /></span></div><ul class="insight-list positive-list"><li v-for="item in report.strengths" :key="item"><span><CircleCheck /></span>{{ item }}</li></ul></el-card>
        <el-card class="surface-card report-list-card" shadow="never"><div class="card-heading"><div><span class="eyebrow">改进方向</span><h3>不足</h3></div><span class="round-icon amber"><TrendCharts /></span></div><ul class="insight-list improvement-list"><li v-for="item in report.weaknesses" :key="item"><span>↗</span>{{ item }}</li></ul></el-card>
      </section>

      <section class="surface-card suggestions-card"><div class="card-heading"><div><span class="eyebrow">下一步计划</span><h3>学习建议</h3></div></div><div class="suggestion-grid"><div v-for="(suggestion, index) in report.suggestions" :key="suggestion" class="suggestion-item"><div class="suggestion-number">{{ String(index + 1).padStart(2, "0") }}</div><div><strong>建议 {{ index + 1 }}</strong><p>{{ suggestion }}</p></div></div></div></section>

      <section v-if="report.answers.length" class="surface-card answer-review-card">
        <div class="card-heading"><div><span class="eyebrow">回答复盘</span><h3>逐题评分与分析</h3></div></div>
        <div v-for="(answer, index) in report.answers" :key="answer.id" class="answer-review-item">
          <div class="answer-review-heading"><strong>第 {{ index + 1 }} 题</strong><el-tag type="success" effect="light" round>{{ answer.score ?? "待评估" }} / 100</el-tag></div>
          <p v-if="answer.question"><b>面试官问题：</b>{{ answer.question }}</p>
          <p><b>你的回答：</b>{{ answer.answer }}</p>
          <p v-if="answer.analysis"><b>AI分析：</b>{{ answer.analysis }}</p>
        </div>
      </section>
    </template>
  </div>
</template>
