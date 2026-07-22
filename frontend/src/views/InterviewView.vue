<script setup lang="ts">
import { ArrowDown, ArrowRight, ArrowUp, ChatDotRound, CircleCheck, CopyDocument, Cpu, MagicStick, Mic, Paperclip, RefreshLeft, UserFilled } from "@element-plus/icons-vue";
import axios from "axios";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { endInterviewEarly, finishInterview, getInterviewHistory, recallInterviewMessage, startInterview, streamInterview } from "../api/interview";
import { listJobs } from "../api/job";
import { getReport } from "../api/report";
import { getLatestResume } from "../api/resume";
import { useUserStore } from "../stores/user";
import type { ChatMessage, JobPosition, ResumeResponse } from "../types";

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const { t } = useI18n();

const draft = ref("");
const messages = ref<ChatMessage[]>([]);
const isLoading = ref(false);
const isThinking = ref(false);
const loadError = ref("");
const activeInterviewId = ref<number | null>(null);
const activeInterviewStatus = ref("in_progress");
const completedQuestions = ref(0);
const totalQuestions = ref(0);
const activePosition = ref("");
const jobs = ref<JobPosition[]>([]);
const latestResume = ref<ResumeResponse | null>(null);
const selectedJobId = ref<number | null>(null);
const isStartLoading = ref(false);
const isFinishLoading = ref(false);
const showFinishDialog = ref(false);
const showEndInterviewDialog = ref(false);
const hasReport = ref(false);
const messagesContainer = ref<HTMLElement | null>(null);
const composerInput = ref<{ focus?: () => void } | null>(null);
const messageMenu = ref<{ x: number; y: number; message: ChatMessage | null }>({ x: 0, y: 0, message: null });
const isMessagesScrolling = ref(false);
let messagesScrollbarTimer: number | undefined;

const routeInterviewId = computed(() => String(route.params.id ?? "new"));
const isStartMode = computed(() => routeInterviewId.value === "new");
const progress = computed(() => totalQuestions.value ? Math.min(100, Math.max(0, (completedQuestions.value / totalQuestions.value) * 100)) : 0);
const currentQuestionLabel = computed(() => t("interview.questionProgress", { current: totalQuestions.value ? Math.min(completedQuestions.value + 1, totalQuestions.value) : 0, total: totalQuestions.value || 0 }));
const remainingQuestionCount = computed(() => Math.max(totalQuestions.value - completedQuestions.value, 0));
const isInterviewCompleted = computed(() => ["completed", "ended_early"].includes(activeInterviewStatus.value));
const reportActionLabel = computed(() => hasReport.value ? "查看报告" : "生成报告");
const interviewTitle = computed(() => activePosition.value ? `${activePosition.value}深入练习` : t("interview.title"));
const interviewRole = computed(() => activePosition.value || t("interview.role"));
const TYPEWRITER_INTERVAL_MS = 28;
const userAvatarUrl = computed(() => userStore.user?.avatar_url ? `http://localhost:8000${userStore.user.avatar_url}` : "");

function formatTime(value: string | Date) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function mapMessages(items: Array<{ id: number; role: "user" | "assistant"; content: string; created_at: string }>) {
  messages.value = items.map((item) => ({ id: item.id, role: item.role === "assistant" ? "ai" : "user", content: item.content, time: formatTime(item.created_at) }));
}

async function scrollToBottom() {
  await nextTick();
  if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
}

function revealMessagesScrollbar() {
  isMessagesScrolling.value = true;
  if (messagesScrollbarTimer !== undefined) window.clearTimeout(messagesScrollbarTimer);
  messagesScrollbarTimer = window.setTimeout(() => {
    isMessagesScrolling.value = false;
    messagesScrollbarTimer = undefined;
  }, 900);
}

function createAssistantTypewriter(message: ChatMessage) {
  const characters: string[] = [];
  let streamFinished = false;
  let cancelled = false;
  let timer: number | undefined;
  let isRendering = false;
  let resolveDrained: (() => void) | undefined;
  const drained = new Promise<void>((resolve) => { resolveDrained = resolve; });

  const renderNext = () => {
    if (cancelled) return;
    const character = characters.shift();
    if (character !== undefined) {
      message.content += character;
      void scrollToBottom();
      timer = window.setTimeout(renderNext, TYPEWRITER_INTERVAL_MS);
      return;
    }

    isRendering = false;
    if (streamFinished) resolveDrained?.();
  };

  const ensureRendering = () => {
    if (isRendering || cancelled) return;
    isRendering = true;
    timer = window.setTimeout(renderNext, 0);
  };

  return {
    enqueue(chunk: string) {
      // Array.from preserves emoji and other multi-byte characters as one unit.
      characters.push(...Array.from(chunk));
      ensureRendering();
    },
    finish() {
      streamFinished = true;
      ensureRendering();
    },
    waitForDrain() {
      return drained;
    },
    cancel() {
      cancelled = true;
      characters.length = 0;
      if (timer !== undefined) window.clearTimeout(timer);
      resolveDrained?.();
    },
  };
}

async function loadStartOptions() {
  isLoading.value = true;
  loadError.value = "";
  try {
    const [resume, savedJobs] = await Promise.all([getLatestResume(), listJobs()]);
    latestResume.value = resume;
    jobs.value = savedJobs;
    selectedJobId.value = savedJobs[0]?.id ?? null;
    activePosition.value = savedJobs[0]?.position ?? "";
  } catch (error) {
    loadError.value = axios.isAxiosError(error) ? error.message : t("interview.loadSetupFailed");
  } finally {
    isLoading.value = false;
  }
}

async function loadHistory(silent = false) {
  const id = Number(routeInterviewId.value);
  if (!Number.isInteger(id) || id <= 0) {
    await loadStartOptions();
    return;
  }
  if (!silent) isLoading.value = true;
  loadError.value = "";
  try {
    const history = await getInterviewHistory(id);
    activeInterviewId.value = history.interview.id;
    activeInterviewStatus.value = history.interview.status;
    completedQuestions.value = history.interview.completed_questions || 0;
    totalQuestions.value = history.interview.total_questions || 0;
    activePosition.value = history.interview.position || "";
    hasReport.value = false;
    if (isInterviewCompleted.value) {
      showFinishDialog.value = false;
      try {
        await getReport(history.interview.id);
        hasReport.value = true;
      } catch {
        // The interview may be completed before report generation finishes.
      }
    }
    mapMessages(history.messages);
    // Render the real message list before calculating scrollHeight. If the
    // loading state is still visible here, the later list render resets the
    // chat viewport back to the top.
    if (!silent) isLoading.value = false;
    await scrollToBottom();
    if (isInterviewCompleted.value && !hasReport.value) showFinishDialog.value = true;
  } catch (error) {
    activeInterviewId.value = null;
    loadError.value = axios.isAxiosError(error) ? error.message : t("interview.loadInterviewFailed");
  } finally {
    if (!silent) isLoading.value = false;
  }
}

async function createInterview() {
  if (!latestResume.value || !selectedJobId.value) {
    ElMessage.warning(t("interview.missingResources"));
    return;
  }
  isStartLoading.value = true;
  try {
    const result = await startInterview(latestResume.value.id, selectedJobId.value);
    activeInterviewStatus.value = result.interview.status;
    completedQuestions.value = result.interview.completed_questions || 0;
    totalQuestions.value = result.interview.total_questions || 0;
    await router.replace(`/interview/${result.interview.id}`);
  } catch (error) {
    const detail = axios.isAxiosError(error) ? error.response?.data?.detail : "";
    if (axios.isAxiosError(error) && error.response?.status === 400 && (String(detail).includes("生成面试题") || String(detail).includes("旧版面试题") || String(detail).includes("8 个面试问题"))) {
      try {
        await ElMessageBox.alert(
          `<div class="missing-question-guide">
            <p>您还未为当前岗位生成面试题，暂时无法开始模拟面试。</p>
            <strong>请按以下步骤操作：</strong>
            <ol>
              <li>点击左侧「我的简历」</li>
              <li>选择已保存的岗位</li>
              <li>先点击「AI分析简历」</li>
              <li>再点击「生成面试题」</li>
            </ol>
            <small>完成后返回模拟面试，即可开始答题。</small>
          </div>`,
          "还未生成面试题",
          {
            type: "warning",
            confirmButtonText: "去我的简历",
            dangerouslyUseHTMLString: true,
            customClass: "missing-question-message-box",
            showClose: true,
          },
        );
        await router.push("/resume");
      } catch {
        // The user closed the guide dialog.
      }
      return;
    }
    ElMessage.error(detail || (axios.isAxiosError(error) ? error.message : t("interview.startFailed")));
  } finally {
    isStartLoading.value = false;
  }
}

async function sendMessage(content = draft.value) {
  const text = content.trim();
  if (!text || !activeInterviewId.value || isThinking.value) return;
  if (isInterviewCompleted.value) {
    ElMessage.warning("本次面试已经结束，不能继续回答");
    return;
  }
  messages.value.push({ id: `user-${Date.now()}`, role: "user", content: text, time: formatTime(new Date()) });
  draft.value = "";
  // Keep this temporary message reactive. Mutating a plain object after it is
  // inserted into a ref array does not reliably trigger a Vue render, which
  // made the response appear all at once when history was reloaded.
  const assistantMessage = reactive<ChatMessage>({
    id: `assistant-${Date.now()}`,
    role: "ai",
    content: "",
    time: formatTime(new Date()),
  });
  messages.value.push(assistantMessage);
  const typewriter = createAssistantTypewriter(assistantMessage);
  isThinking.value = true;
  await scrollToBottom();
  try {
    await streamInterview(activeInterviewId.value, text, (chunk) => {
      typewriter.enqueue(chunk);
    });
    typewriter.finish();
    // Do not reload history until every received character has been visibly
    // rendered. Otherwise Vue replaces the temporary message with full text.
    await typewriter.waitForDrain();
    // Keep the chat mounted after streaming. A normal history reload toggles
    // the loading view and causes a visible flash after the last character.
    await loadHistory(true);
  } catch (error) {
    typewriter.cancel();
    messages.value = messages.value.filter((message) => message.id !== assistantMessage.id);
    if (error instanceof Error && error.message.toLowerCase().includes("no longer active")) {
      activeInterviewStatus.value = "completed";
      await loadHistory();
      ElMessage.warning("本次面试已经结束，已切换为只读模式");
    } else {
      ElMessage.error(error instanceof Error ? error.message : t("interview.continueFailed"));
    }
  } finally {
    isThinking.value = false;
  }
}

function openMessageMenu(event: MouseEvent, message: ChatMessage) {
  if (typeof message.id !== "number") return;
  const menuWidth = 158;
  const menuHeight = message.role === "user" ? 142 : 96;
  messageMenu.value = { x: Math.min(event.clientX, window.innerWidth - menuWidth - 8), y: Math.min(event.clientY, window.innerHeight - menuHeight - 8), message };
}

function closeMessageMenu() { messageMenu.value.message = null; }

async function copyMessage(message: ChatMessage) {
  try {
    await navigator.clipboard.writeText(message.content);
    ElMessage.success("已复制");
  } catch {
    ElMessage.error("复制失败，请手动选择文本");
  } finally {
    closeMessageMenu();
  }
}

function quoteMessage(message: ChatMessage) {
  const quote = message.content.split("\n").map((line) => `> ${line}`).join("\n");
  draft.value = `${quote}\n\n${draft.value}`.trimStart();
  closeMessageMenu();
  void nextTick(() => composerInput.value?.focus?.());
}

async function recallUserMessage(message: ChatMessage) {
  if (message.role !== "user" || typeof message.id !== "number" || !activeInterviewId.value || isThinking.value) return;
  try {
    const history = await recallInterviewMessage(activeInterviewId.value, message.id);
    activePosition.value = history.interview.position || "";
    mapMessages(history.messages);
    ElMessage.success("消息已撤回");
  } catch (error) {
    ElMessage.error(axios.isAxiosError(error) ? error.message : "消息撤回失败");
  } finally {
    closeMessageMenu();
  }
}

function copySelectedMessage() { if (messageMenu.value.message) void copyMessage(messageMenu.value.message); }
function quoteSelectedMessage() { if (messageMenu.value.message) quoteMessage(messageMenu.value.message); }
function recallSelectedMessage() { if (messageMenu.value.message) void recallUserMessage(messageMenu.value.message); }

async function generateReport() {
  if (!activeInterviewId.value || isFinishLoading.value) return;
  isFinishLoading.value = true;
  try {
    await finishInterview(activeInterviewId.value);
    showFinishDialog.value = false;
    await router.push(`/report/${activeInterviewId.value}`);
  } catch (error) {
    ElMessage.error(axios.isAxiosError(error) ? (error.response?.data?.detail || error.message) : "报告生成失败");
  } finally {
    isFinishLoading.value = false;
  }
}

async function endInterviewManually() {
  if (!activeInterviewId.value || isFinishLoading.value || isInterviewCompleted.value) return;
  showEndInterviewDialog.value = true;
  return;
  const remaining = Math.max(totalQuestions.value - completedQuestions.value, 0);
  try {
    await ElMessageBox.confirm(
      remaining > 0
        ? `当前还有 ${remaining} 个问题未完成。结束后将只根据已完成的回答生成报告。`
        : "本次面试已完成全部问题，是否结束并生成报告？",
      "结束面试",
      {
        confirmButtonText: "结束并生成报告",
        cancelButtonText: "继续面试",
        type: "warning",
      },
    );
  } catch {
    return;
  }

  isFinishLoading.value = true;
  try {
    await endInterviewEarly(activeInterviewId.value as number);
    activeInterviewStatus.value = "ended_early";
    showFinishDialog.value = false;
    await router.push(`/report/${activeInterviewId.value}`);
  } catch (error: any) {
    ElMessage.error(axios.isAxiosError(error) ? (error.response?.data?.detail || error.message) : "结束面试失败，请稍后重试");
  } finally {
    isFinishLoading.value = false;
  }
}

async function confirmEndInterview() {
  const interviewId = activeInterviewId.value;
  if (!interviewId || isFinishLoading.value) return;
  showEndInterviewDialog.value = false;
  isFinishLoading.value = true;
  try {
    await endInterviewEarly(interviewId);
    activeInterviewStatus.value = "ended_early";
    showFinishDialog.value = false;
    await router.push(`/report/${interviewId}`);
  } catch (error) {
    const detail = axios.isAxiosError(error) ? error.response?.data?.detail : "";
    ElMessage.error(detail || (error instanceof Error ? error.message : "结束面试失败，请稍后重试"));
  } finally {
    isFinishLoading.value = false;
  }
}

function openReportAction() {
  if (!activeInterviewId.value) return;
  if (hasReport.value) {
    void router.push(`/report/${activeInterviewId.value}`);
    return;
  }
  showFinishDialog.value = true;
}

onMounted(() => {
  void userStore.loadUser().catch(() => undefined);
  void loadHistory();
});
onBeforeUnmount(() => {
  if (messagesScrollbarTimer !== undefined) window.clearTimeout(messagesScrollbarTimer);
});
watch(routeInterviewId, () => {
  activeInterviewId.value = null;
  activeInterviewStatus.value = "in_progress";
  completedQuestions.value = 0;
  totalQuestions.value = 0;
  hasReport.value = false;
  messages.value = [];
  showFinishDialog.value = false;
  showEndInterviewDialog.value = false;
  void loadHistory();
});
</script>

<template>
  <div class="page-view interview-view" @click="closeMessageMenu">
    <section v-if="isStartMode" class="surface-card interview-start-card">
      <div class="interview-start-icon"><el-icon><Cpu /></el-icon></div>
      <span class="eyebrow">{{ t("interview.context") }}</span>
      <h1>{{ t("interview.startTitle") }}</h1>
      <p>{{ t("interview.startDescription") }}</p>
      <el-skeleton v-if="isLoading" :rows="3" animated />
      <el-alert v-else-if="loadError" :title="loadError" type="error" :closable="false" />
      <template v-else>
        <div class="interview-start-grid"><div class="start-resource"><span class="eyebrow">{{ t("nav.resume") }}</span><strong>{{ latestResume?.original_filename || t("interview.noResume") }}</strong></div><el-select v-model="selectedJobId" :placeholder="t('interview.selectJob')" :disabled="!jobs.length"><el-option v-for="job in jobs" :key="job.id" :label="`${job.position} · ${job.company}`" :value="job.id" /></el-select></div>
        <el-button type="primary" size="large" :loading="isStartLoading" :disabled="!latestResume || !jobs.length" @click="createInterview">{{ t("dashboard.start") }} <el-icon><ArrowUp /></el-icon></el-button>
      </template>
    </section>

    <transition name="report-generation-fade">
      <div v-if="isStartMode && isStartLoading" class="report-generation-overlay question-generation-overlay" role="alert" aria-live="assertive" aria-busy="true">
        <section class="report-generation-card" aria-label="正在生成模拟面试题">
          <div class="report-generation-orbit"><span></span></div>
          <span class="report-generation-eyebrow">AI INTERVIEW PREPARATION</span>
          <h2>面试题正在加载中</h2>
          <p>AI 面试官正在根据你的简历、岗位和历史面试记录生成全新的 8 道问题。</p>
          <div class="report-generation-steps">
            <span><i></i>读取简历能力画像</span>
            <span><i></i>匹配目标岗位要求</span>
            <span><i></i>生成本场专属问题</span>
          </div>
          <small>请稍候，生成期间页面暂不可操作</small>
        </section>
      </div>
    </transition>

    <template v-if="!isStartMode">
      <section class="interview-header"><div class="interview-title"><div class="interview-bot-mark"><el-icon><Cpu /></el-icon></div><div><span class="eyebrow">{{ t("interview.live", { id: activeInterviewId }) }}</span><h1>{{ interviewTitle }}</h1></div></div><div class="interview-controls"><span class="live-status" :class="{ completed: isInterviewCompleted }"><i></i> {{ isInterviewCompleted ? "面试已完成" : t("interview.active") }}</span><el-button v-if="!isInterviewCompleted" type="danger" plain :loading="isFinishLoading" @click="endInterviewManually">结束面试</el-button><el-button v-if="isInterviewCompleted" type="primary" plain @click="openReportAction">{{ reportActionLabel }}</el-button><el-button text><el-icon><MagicStick /></el-icon> {{ t("interview.coachNotes") }}</el-button><el-button text><el-icon><ArrowDown /></el-icon></el-button></div></section>
      <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" class="interview-error" />
      <section v-else class="chat-shell">
        <div class="chat-context"><div><span class="eyebrow">{{ t("interview.context") }}</span><strong>{{ interviewRole }}</strong></div><div class="context-progress"><span>{{ currentQuestionLabel }}</span><el-progress :percentage="progress" :show-text="false" :stroke-width="5" color="#6d5dfc" /></div></div>
         <div ref="messagesContainer" class="chat-messages" :class="{ 'is-user-scrolling': isMessagesScrolling }" tabindex="0" @wheel="revealMessagesScrollbar" @touchmove="revealMessagesScrollbar" @keydown="revealMessagesScrollbar"><div v-if="isLoading" class="chat-loading"><el-icon class="is-loading"><MagicStick /></el-icon> {{ t("interview.loadingHistory") }}</div><template v-else><div v-for="message in messages" :key="message.id" class="message-row" :class="message.role" @contextmenu.prevent="openMessageMenu($event, message)"><el-avatar :size="34" :src="message.role === 'user' ? userAvatarUrl : undefined" :class="message.role === 'ai' ? 'ai-avatar' : 'user-avatar'"><el-icon v-if="message.role === 'ai'"><MagicStick /></el-icon><el-icon v-else-if="!userAvatarUrl"><UserFilled /></el-icon></el-avatar><div class="message-body"><div class="message-meta"><strong>{{ message.role === "ai" ? t("interview.ai") : t("interview.you") }}</strong><span>{{ message.time }}</span></div><div class="message-bubble">{{ message.content }}<span v-if="message.role === 'ai' && !message.content && isThinking" class="typing"><i></i><i></i><i></i></span></div></div></div></template></div>
        <div class="chat-composer-area"><div class="chat-composer"><el-button text circle :disabled="isInterviewCompleted"><el-icon><Paperclip /></el-icon></el-button><el-input ref="composerInput" v-model="draft" type="textarea" :autosize="{ minRows: 1, maxRows: 4 }" resize="none" :placeholder="isInterviewCompleted ? '面试已结束，无法继续发送' : t('interview.placeholder')" :disabled="isThinking || isInterviewCompleted" @keydown.enter.exact.prevent="sendMessage()" /><el-button text circle class="mic-button" :disabled="isInterviewCompleted"><el-icon><Mic /></el-icon></el-button><el-button type="primary" circle class="send-button" :disabled="!draft.trim() || isThinking || isInterviewCompleted" @click="sendMessage()"><el-icon><ArrowUp /></el-icon></el-button></div><small class="composer-hint">{{ isInterviewCompleted ? "你可以在报告页面查看逐题评分和PDF报告" : t("interview.hint") }}</small></div>
      </section>
    </template>

    <div v-if="messageMenu.message" class="message-context-menu" :style="{ left: `${messageMenu.x}px`, top: `${messageMenu.y}px` }" @click.stop><button type="button" @click="copySelectedMessage"><el-icon><CopyDocument /></el-icon><span>复制</span></button><button type="button" @click="quoteSelectedMessage"><el-icon><ChatDotRound /></el-icon><span>引用</span></button><button v-if="messageMenu.message.role === 'user'" type="button" class="danger" @click="recallSelectedMessage"><el-icon><RefreshLeft /></el-icon><span>撤回</span></button></div>

    <transition name="finish-dialog-fade"><div v-if="showFinishDialog" class="finish-dialog-backdrop" @click.self="showFinishDialog = false"><section class="finish-dialog" role="dialog" aria-modal="true" aria-labelledby="finish-dialog-title"><button type="button" class="finish-dialog-close" aria-label="关闭" @click="showFinishDialog = false">×</button><div class="finish-dialog-glow"></div><div class="finish-dialog-icon"><el-icon><CircleCheck /></el-icon><span></span></div><span class="finish-dialog-eyebrow">INTERVIEW COMPLETE</span><h2 id="finish-dialog-title">AI模拟面试已完毕</h2><p class="finish-dialog-description">你的回答已经全部保存。点击下方按钮，让AI面试官为你生成专属评分报告。</p><div class="finish-dialog-summary"><span><el-icon><CircleCheck /></el-icon>回答记录已保存</span><span><el-icon><CircleCheck /></el-icon>生成逐题分析</span><span><el-icon><CircleCheck /></el-icon>生成PDF报告</span></div><button type="button" class="finish-report-button" :disabled="isFinishLoading" @click="generateReport"><span v-if="!isFinishLoading">生成报告 <el-icon><ArrowRight /></el-icon></span><span v-else>正在生成报告...</span></button><button type="button" class="finish-continue-button" :disabled="isFinishLoading" @click="showFinishDialog = false">返回查看面试记录</button></section></div></transition>
  </div>

    <transition name="end-interview-fade">
      <div v-if="showEndInterviewDialog" class="end-interview-backdrop" @click.self="showEndInterviewDialog = false">
        <section class="end-interview-dialog" role="dialog" aria-modal="true" aria-labelledby="end-interview-title">
          <button type="button" class="end-interview-close" aria-label="关闭" @click="showEndInterviewDialog = false">×</button>
          <div class="end-interview-icon"><el-icon><Cpu /></el-icon></div>
          <span class="end-interview-eyebrow">INTERVIEW SESSION</span>
          <h2 id="end-interview-title">要结束本次面试吗？</h2>
          <p>结束后，AI 将基于已完成的有效回答生成本次面试报告。</p>
          <div class="end-interview-progress">
            <div><span>当前进度</span><strong>{{ completedQuestions }} / {{ totalQuestions }} 题</strong></div>
            <el-progress :percentage="progress" :show-text="false" :stroke-width="7" color="#6d5dfc" />
          </div>
          <div v-if="remainingQuestionCount > 0" class="end-interview-note"><span>!</span><template v-if="completedQuestions === 0">请先回答至少一道有效问题后再结束面试。</template><template v-else>还有 {{ remainingQuestionCount }} 个问题未完成，报告将仅评估已完成回答。</template></div>
          <div class="end-interview-actions">
            <button type="button" class="end-interview-cancel" @click="showEndInterviewDialog = false">继续回答</button>
            <button type="button" class="end-interview-confirm" :disabled="completedQuestions === 0" @click="confirmEndInterview">结束并生成报告 <el-icon><ArrowRight /></el-icon></button>
          </div>
        </section>
      </div>
    </transition>

    <transition name="report-generation-fade">
      <div v-if="isFinishLoading" class="report-generation-overlay" role="alert" aria-live="assertive" aria-busy="true">
        <section class="report-generation-card" aria-label="正在生成面试报告">
          <div class="report-generation-orbit"><span></span></div>
          <span class="report-generation-eyebrow">AI INTERVIEW ANALYSIS</span>
          <h2>正在生成你的面试报告</h2>
          <p>AI 正在分析你的回答表现，请稍候片刻。</p>
          <div class="report-generation-steps">
            <span><i></i>整理回答记录</span>
            <span><i></i>评估能力表现</span>
            <span><i></i>生成专属报告</span>
          </div>
          <small>报告完成后将自动为你打开</small>
        </section>
      </div>
    </transition>
</template>
