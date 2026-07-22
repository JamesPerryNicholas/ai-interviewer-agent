<script setup lang="ts">
import { Check, Document, UploadFilled } from "@element-plus/icons-vue";
import axios from "axios";
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { useI18n } from "vue-i18n";

import { analyzeResume as analyzeResumeRequest, getLatestResume, uploadResume } from "../api/resume";
import { generateQuestions, listJobs } from "../api/job";
import type { GeneratedQuestion, JobPosition, ResumeAnalysis, ResumeResponse } from "../types";

const { t } = useI18n();
const fileInput = ref<HTMLInputElement | null>(null);
const selectedFile = ref<File | null>(null);
const resumeRecord = ref<ResumeResponse | null>(null);
const uploadProgress = ref(0);
const parseError = ref("");
const parseStatus = ref<"empty" | "ready" | "parsing" | "done" | "error">("empty");
const analysis = ref<ResumeAnalysis | null>(null);
const analysisStatus = ref<"idle" | "analyzing" | "done" | "error">("idle");
const analysisError = ref("");
const jobs = ref<JobPosition[]>([]);
const selectedJobId = ref<number | null>(null);
const questions = ref<GeneratedQuestion[]>([]);
const questionStatus = ref<"idle" | "generating" | "done" | "error">("idle");

const levelLabels: Record<string, string> = {
  entry: "入门",
  junior: "初级",
  mid: "中级",
  senior: "高级",
  lead: "专家",
  unknown: "待评估",
};

function questionCategoryLabel(category: string) {
  return t(`resume.questionCategories.${category}`);
}

function questionDifficultyLabel(difficulty: string) {
  return t(`resume.questionDifficulties.${difficulty}`);
}

function levelLabel(level: string) {
  return levelLabels[level.toLowerCase()] ?? "待评估";
}

function acceptFile(rawFile: File | undefined) {
  if (!rawFile) return;

  // Some browsers leave File.type empty, so the extension is the source of truth.
  const isPdf = rawFile.name.toLowerCase().endsWith(".pdf")
    && (!rawFile.type || rawFile.type === "application/pdf");
  if (!isPdf) {
    ElMessage.error(t("resume.onlyPdf"));
    return false;
  }

  selectedFile.value = rawFile;
  uploadProgress.value = 0;
  parseError.value = "";
  analysis.value = null;
  analysisStatus.value = "idle";
  analysisError.value = "";
  questions.value = [];
  questionStatus.value = "idle";
  parseStatus.value = "ready";
  return false;
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  acceptFile(input.files?.[0]);
}

function handleFileDrop(event: DragEvent) {
  acceptFile(event.dataTransfer?.files?.[0]);
}

function openFilePicker() {
  fileInput.value?.click();
}

async function parseResume() {
  if (!selectedFile.value) return;

  parseStatus.value = "parsing";
  uploadProgress.value = 0;
  parseError.value = "";

  try {
    resumeRecord.value = await uploadResume(selectedFile.value, (percentage) => {
      uploadProgress.value = percentage;
    });
    uploadProgress.value = 100;
    analysis.value = resumeRecord.value.extracted_info;
    analysisStatus.value = analysis.value ? "done" : "idle";
    parseStatus.value = "done";
    ElMessage.success(t("resume.success"));
  } catch (error) {
    parseStatus.value = "error";
    parseError.value = axios.isAxiosError(error) ? error.message : "简历解析失败，请稍后重试";
    ElMessage.error(parseError.value);
  }
}

function clearFile() {
  selectedFile.value = null;
  if (fileInput.value) fileInput.value.value = "";
  uploadProgress.value = 0;
  parseError.value = "";
  parseStatus.value = resumeRecord.value ? "done" : "empty";
}

async function analyzeResume() {
  if (!resumeRecord.value) return;

  analysisStatus.value = "analyzing";
  analysisError.value = "";

  try {
    analysis.value = await analyzeResumeRequest(resumeRecord.value.id);
    resumeRecord.value.extracted_info = analysis.value;
    analysisStatus.value = "done";
    ElMessage.success(t("resume.analysisSuccess"));
  } catch (error) {
    analysisStatus.value = "error";
    analysisError.value = axios.isAxiosError(error) ? error.message : "简历分析失败，请稍后重试";
    ElMessage.error(analysisError.value);
  }
}

async function generateInterviewQuestions() {
  if (!resumeRecord.value || !selectedJobId.value) {
    ElMessage.warning(t("resume.selectJob"));
    return;
  }

  questionStatus.value = "generating";
  try {
    questions.value = await generateQuestions(resumeRecord.value.id, selectedJobId.value);
    questionStatus.value = "done";
    ElMessage.success(t("resume.questionGenerationSuccess"));
  } catch (error) {
    questionStatus.value = "error";
    ElMessage.error(axios.isAxiosError(error) ? error.message : t("resume.questionGenerationFailed"));
  }
}

async function loadLatestResume() {
  try {
    resumeRecord.value = await getLatestResume();
    analysis.value = resumeRecord.value.extracted_info;
    analysisStatus.value = analysis.value ? "done" : "idle";
    parseStatus.value = "done";
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return;
    }

    ElMessage.error(axios.isAxiosError(error) ? error.message : "简历加载失败，请稍后重试");
  }
}

async function loadJobsForResume() {
  try {
    jobs.value = await listJobs();
  } catch (error) {
    ElMessage.error(axios.isAxiosError(error) ? error.message : t("resume.jobsLoadFailed"));
  }
}

onMounted(() => {
  void loadLatestResume();
  void loadJobsForResume();
});
</script>

<template>
  <div class="page-view resume-view">
    <section class="page-intro">
      <div><span class="eyebrow">{{ t("resume.eyebrow") }}</span><h1>{{ t("resume.title") }}</h1><p>{{ t("resume.subtitle") }}</p></div>
      <el-tag v-if="parseStatus === 'done'" type="success" effect="light" round><el-icon><Check /></el-icon> {{ t("common.profileReady") }}</el-tag>
    </section>

    <section class="resume-layout">
      <el-card class="surface-card upload-card" shadow="never">
        <div class="card-heading"><div><span class="eyebrow">{{ t("resume.stepUpload") }}</span><h3>{{ t("resume.uploadTitle") }}</h3></div><span class="format-note">{{ t("resume.format") }}</span></div>
        <div
          class="resume-uploader"
          role="button"
          tabindex="0"
          @click="openFilePicker"
          @keydown.enter.prevent="openFilePicker"
          @keydown.space.prevent="openFilePicker"
          @dragover.prevent
          @drop.prevent="handleFileDrop"
        >
          <input ref="fileInput" class="resume-file-input" type="file" accept=".pdf,application/pdf" @click.stop @change="handleFileChange" />
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div class="upload-title">{{ t("resume.drop") }}</div>
          <div class="upload-subtitle">or <em>{{ t("resume.browse") }}</em> {{ t("resume.fromComputer") }}</div>
        </div>
        <div v-if="selectedFile" class="selected-file">
          <div class="document-icon"><el-icon><Document /></el-icon></div>
          <div class="selected-file-copy"><strong>{{ selectedFile.name }}</strong><span>{{ (selectedFile.size / 1024 / 1024).toFixed(2) }} MB · {{ t("resume.ready") }}</span></div>
          <el-button text type="danger" @click="clearFile">{{ t("common.remove") }}</el-button>
        </div>
        <el-progress v-if="parseStatus === 'parsing'" :percentage="uploadProgress" :stroke-width="8" />
        <el-button class="parse-button" type="primary" size="large" :loading="parseStatus === 'parsing'" :disabled="!selectedFile || parseStatus === 'parsing'" @click="parseResume">{{ parseStatus === 'done' ? t("resume.reparse") : t("resume.parse") }}</el-button>
        <el-button v-if="resumeRecord && parseStatus === 'done'" class="analyze-button" type="success" size="large" :loading="analysisStatus === 'analyzing'" :disabled="analysisStatus === 'analyzing'" @click="analyzeResume">{{ analysisStatus === 'done' ? t("resume.reanalyze") : t("resume.analyze") }}</el-button>
        <div v-if="analysis" class="question-controls">
          <el-select v-model="selectedJobId" clearable :placeholder="t('resume.selectJobPlaceholder')">
            <el-option v-for="job in jobs" :key="job.id" :label="`${job.position} · ${job.company}`" :value="job.id" />
          </el-select>
          <el-button type="warning" size="large" :loading="questionStatus === 'generating'" :disabled="!selectedJobId || questionStatus === 'generating'" @click="generateInterviewQuestions">{{ t("resume.generateQuestions") }}</el-button>
        </div>
        <p class="privacy-note">{{ t("resume.privacy") }}</p>
      </el-card>

      <el-card class="surface-card parse-card" shadow="never">
        <div class="card-heading"><div><span class="eyebrow">{{ t("resume.stepStatus") }}</span><h3>{{ t("resume.statusTitle") }}</h3></div><span class="status-pulse" :class="parseStatus"></span></div>
        <div class="parse-visual" :class="parseStatus">
          <div class="parse-ring"><el-icon v-if="parseStatus === 'done'"><Check /></el-icon><span v-else>PDF</span></div>
          <div class="parse-lines"><i></i><i></i><i></i><i></i></div>
        </div>
        <h4>{{ parseStatus === 'done' ? t("resume.extracted") : parseStatus === 'parsing' ? t("resume.reading") : parseStatus === 'error' ? t("resume.onlyPdf") : t("resume.waiting") }}</h4>
        <p>{{ parseStatus === 'done' ? t("resume.extractedDescription") : parseStatus === 'error' ? parseError : t("resume.waitingDescription") }}</p>
        <div class="parse-steps"><span :class="{ complete: ['parsing', 'done'].includes(parseStatus) }">01 <small>{{ t("resume.upload") }}</small></span><b></b><span :class="{ complete: parseStatus === 'done' }">02 <small>{{ t("resume.extract") }}</small></span><b></b><span :class="{ complete: parseStatus === 'done' }">03 <small>{{ t("resume.readyStep") }}</small></span></div>
      </el-card>
    </section>

    <section v-if="analysis" class="surface-card analysis-card">
      <div class="card-heading"><div><span class="eyebrow">{{ t("resume.aiAnalysis") }}</span><h3>{{ t("resume.analysisTitle") }}</h3></div><el-tag type="success" effect="light" round>{{ levelLabel(analysis.level) }}</el-tag></div>
      <div class="analysis-section"><span class="analysis-label">{{ t("resume.skills") }}</span><div class="skill-list"><el-tag v-for="skill in analysis.skills" :key="skill" effect="plain" round>{{ skill }}</el-tag><span v-if="!analysis.skills.length" class="analysis-empty">—</span></div></div>
      <div class="analysis-section"><span class="analysis-label">{{ t("resume.projects") }}</span><ul class="analysis-list"><li v-for="project in analysis.projects" :key="project">{{ project }}</li><li v-if="!analysis.projects.length" class="analysis-empty">—</li></ul></div>
      <div class="analysis-section"><span class="analysis-label">{{ t("resume.experience") }}</span><p class="analysis-copy">{{ analysis.experience || "—" }}</p></div>
      <div class="analysis-section"><span class="analysis-label">{{ t("resume.suggestions") }}</span><ul class="analysis-list"><li v-for="suggestion in analysis.suggestions" :key="suggestion">{{ suggestion }}</li><li v-if="!analysis.suggestions.length" class="analysis-empty">—</li></ul></div>
    </section>

    <section v-if="questions.length" class="surface-card questions-card">
      <div class="card-heading"><div><span class="eyebrow">{{ t("resume.generatedQuestions") }}</span><h3>{{ t("resume.questionsTitle") }}</h3><p class="question-reference-note">以下面试题仅供准备和参考，点击“开始面试”后系统会重新生成一套全新的模拟面试题。</p></div><el-tag type="warning" effect="light" round>{{ questions.length }}</el-tag></div>
      <div class="question-list">
        <article v-for="(item, index) in questions" :key="item.id || `${item.question}-${index}`" class="question-item">
          <div class="question-number">{{ String(index + 1).padStart(2, "0") }}</div>
          <div class="question-copy"><div class="question-meta"><el-tag size="small" effect="plain">{{ questionCategoryLabel(item.category) }}</el-tag><el-tag size="small" type="warning" effect="plain">{{ questionDifficultyLabel(item.difficulty) }}</el-tag></div><p>{{ item.question }}</p></div>
        </article>
      </div>
    </section>

    <transition name="report-generation-fade">
      <div v-if="analysisStatus === 'analyzing'" class="report-generation-overlay resume-analysis-overlay" role="alert" aria-live="assertive" aria-busy="true">
        <section class="report-generation-card" aria-label="正在分析简历">
          <div class="report-generation-orbit"><span></span></div>
          <span class="report-generation-eyebrow">AI RESUME ANALYSIS</span>
          <h2>AI正在分析简历中</h2>
          <p>AI 正在读取你的经历并整理能力画像，请稍候片刻。</p>
          <div class="report-generation-steps">
            <span><i></i>读取简历内容</span>
            <span><i></i>提取技能与项目经历</span>
            <span><i></i>生成能力画像</span>
          </div>
          <small>分析期间页面暂不可操作</small>
        </section>
      </div>
    </transition>

    <transition name="report-generation-fade">
      <div v-if="questionStatus === 'generating'" class="report-generation-overlay question-generation-overlay" role="alert" aria-live="assertive" aria-busy="true">
        <section class="report-generation-card" aria-label="正在生成面试题">
          <div class="report-generation-orbit"><span></span></div>
          <span class="report-generation-eyebrow">AI INTERVIEW PREPARATION</span>
          <h2>面试题正在生成中</h2>
          <p>AI 正在结合你的简历、目标岗位和求职状态，生成个性化准备题目。</p>
          <div class="report-generation-steps">
            <span><i></i>读取能力画像与岗位要求</span>
            <span><i></i>设计个性化问题</span>
            <span><i></i>匹配问题难度与方向</span>
          </div>
          <strong class="question-reference-warning">以下面试题仅供准备和参考，不直接用于模拟面试</strong>
          <small>生成期间页面暂不可操作</small>
        </section>
      </div>
    </transition>
  </div>
</template>
