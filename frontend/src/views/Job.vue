<script setup lang="ts">
import { Briefcase, Delete, Plus } from "@element-plus/icons-vue";
import axios from "axios";
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useI18n } from "vue-i18n";

import { createJob, deleteJob, listJobs } from "../api/job";
import type { JobPosition } from "../types";

const { t } = useI18n();
const jobs = ref<JobPosition[]>([]);
const saving = ref(false);
const loading = ref(false);
const deletingJobId = ref<number | null>(null);
const form = reactive({
  company: "",
  position: "",
  description: "",
});

async function loadJobs() {
  loading.value = true;
  try {
    jobs.value = await listJobs();
  } catch (error) {
    ElMessage.error(axios.isAxiosError(error) ? error.message : t("job.loadFailed"));
  } finally {
    loading.value = false;
  }
}

async function saveJob() {
  if (!form.company.trim() || !form.position.trim() || !form.description.trim()) {
    ElMessage.warning(t("job.required"));
    return;
  }

  saving.value = true;
  try {
    const job = await createJob({
      company: form.company.trim(),
      position: form.position.trim(),
      description: form.description.trim(),
    });
    jobs.value = [job, ...jobs.value];
    form.company = "";
    form.position = "";
    form.description = "";
    ElMessage.success(t("job.success"));
  } catch (error) {
    ElMessage.error(axios.isAxiosError(error) ? error.message : t("job.saveFailed"));
  } finally {
    saving.value = false;
  }
}

async function removeJob(job: JobPosition) {
  try {
    await ElMessageBox.confirm(
        `确定删除“${job.position}”岗位信息吗？删除后，关联的面试记录和面试报告将彻底消失，且无法恢复。`,
      "删除岗位",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
        customClass: "job-delete-message-box",
        showClose: true,
        closeOnClickModal: false,
      },
    );
  } catch {
    return;
  }

  deletingJobId.value = job.id;
  try {
    await deleteJob(job.id);
    jobs.value = jobs.value.filter((item) => item.id !== job.id);
    ElMessage.success("岗位已删除");
  } catch (error) {
    const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined;
    ElMessage.error(detail || "岗位删除失败");
  } finally {
    deletingJobId.value = null;
  }
}

onMounted(loadJobs);
</script>

<template>
  <div class="page-view job-view">
    <section class="page-intro">
      <div><span class="eyebrow">{{ t("job.eyebrow") }}</span><h1>{{ t("job.title") }}</h1><p>{{ t("job.subtitle") }}</p></div>
    </section>

    <section class="job-layout">
      <el-card class="surface-card job-form-card" shadow="never">
        <div class="card-heading"><div><span class="eyebrow">{{ t("job.newEyebrow") }}</span><h3>{{ t("job.formTitle") }}</h3></div><el-icon class="job-icon"><Plus /></el-icon></div>
        <el-form :model="form" label-position="top" @submit.prevent="saveJob">
          <el-form-item :label="t('job.company')"><el-input v-model="form.company" :placeholder="t('job.companyPlaceholder')" /></el-form-item>
          <el-form-item :label="t('job.position')"><el-input v-model="form.position" :placeholder="t('job.positionPlaceholder')" /></el-form-item>
          <el-form-item :label="t('job.description')"><el-input v-model="form.description" type="textarea" :rows="10" :placeholder="t('job.descriptionPlaceholder')" /></el-form-item>
          <el-button type="primary" size="large" :loading="saving" @click="saveJob">{{ t("job.save") }}</el-button>
        </el-form>
      </el-card>

      <el-card class="surface-card job-list-card" shadow="never">
        <div class="card-heading"><div><span class="eyebrow">{{ t("job.savedEyebrow") }}</span><h3>{{ t("job.listTitle") }}</h3></div><el-tag round effect="plain">{{ jobs.length }}</el-tag></div>
        <div v-loading="loading" class="job-list">
          <div v-for="job in jobs" :key="job.id" class="job-item">
            <div class="job-item-icon"><el-icon><Briefcase /></el-icon></div>
            <div class="job-item-copy"><strong>{{ job.position }}</strong><span>{{ job.company }}</span><p>{{ job.description }}</p></div>
            <el-button class="job-delete-button" text type="danger" :loading="deletingJobId === job.id" @click.stop="removeJob(job)">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </div>
          <el-empty v-if="!loading && !jobs.length" :description="t('job.empty')" />
        </div>
      </el-card>
    </section>
  </div>
</template>
