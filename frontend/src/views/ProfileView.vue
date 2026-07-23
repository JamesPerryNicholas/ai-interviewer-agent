<script setup lang="ts">
import { Camera, Check, Close, Lock, RefreshLeft, UserFilled, ZoomIn, ZoomOut } from "@element-plus/icons-vue";
import axios from "axios";
import { computed, nextTick, onBeforeUnmount, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { useI18n } from "vue-i18n";

import { updateProfile } from "../api/user";
import { apiUrl } from "../api/base";
import { useUserStore } from "../stores/user";

const { t } = useI18n();
const userStore = useUserStore();
const displayName = ref(userStore.user?.display_name || userStore.user?.username || "");
const careerStatus = ref(userStore.user?.career_status || "实习求职");
const careerStatusOptions = ["在校学生", "应届毕业生", "实习求职", "社招求职", "已就业（准备跳槽）"];
const selectedAvatar = ref<File | undefined>();
const previewUrl = ref("");
const saving = ref(false);
const cropDialogVisible = ref(false);
const cropSourceUrl = ref("");
const cropCanvas = ref<HTMLCanvasElement | null>(null);
const cropImage = ref<HTMLImageElement | null>(null);
const cropZoom = ref(1);
const cropOffsetX = ref(0);
const cropOffsetY = ref(0);
const cropDragging = ref(false);
const cropDragStart = reactive({ x: 0, y: 0, offsetX: 0, offsetY: 0 });

// Use a 1024px working canvas so the avatar stays sharp after it is displayed
// at different sizes in the header, profile page, and dashboard.
const CROP_SIZE = 1024;

const avatarSrc = computed(() => {
  if (previewUrl.value) return previewUrl.value;
  const avatarUrl = userStore.user?.avatar_url;
  return apiUrl(avatarUrl);
});

function chooseAvatar(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;
  const allowed = ["image/jpeg", "image/png", "image/webp"];
  if (!allowed.includes(file.type)) {
    ElMessage.warning("头像仅支持 JPG、PNG 或 WEBP 格式");
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning("头像大小不能超过 5 MB");
    return;
  }
  openCropper(file);
  (event.target as HTMLInputElement).value = "";
}

async function openCropper(file: File) {
  if (cropSourceUrl.value) URL.revokeObjectURL(cropSourceUrl.value);
  cropSourceUrl.value = URL.createObjectURL(file);
  cropZoom.value = 1;
  cropOffsetX.value = 0;
  cropOffsetY.value = 0;
  cropDialogVisible.value = true;

  const image = new Image();
  image.onload = async () => {
    cropImage.value = image;
    await nextTick();
    drawCropCanvas();
  };
  image.onerror = () => {
    closeCropper();
    ElMessage.error("头像读取失败，请重新选择图片");
  };
  image.src = cropSourceUrl.value;
}

function drawCropCanvas() {
  const canvas = cropCanvas.value;
  const image = cropImage.value;
  if (!canvas || !image) return;

  clampCropOffset();

  const context = canvas.getContext("2d");
  if (!context) return;
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";

  const scale = Math.max(CROP_SIZE / image.naturalWidth, CROP_SIZE / image.naturalHeight) * cropZoom.value;
  const width = image.naturalWidth * scale;
  const height = image.naturalHeight * scale;
  const x = (CROP_SIZE - width) / 2 + cropOffsetX.value;
  const y = (CROP_SIZE - height) / 2 + cropOffsetY.value;

  context.clearRect(0, 0, CROP_SIZE, CROP_SIZE);
  context.fillStyle = "#f3f4fb";
  context.fillRect(0, 0, CROP_SIZE, CROP_SIZE);
  context.drawImage(image, x, y, width, height);
}

function clampCropOffset() {
  const image = cropImage.value;
  if (!image) return;

  const scale = Math.max(CROP_SIZE / image.naturalWidth, CROP_SIZE / image.naturalHeight) * cropZoom.value;
  const width = image.naturalWidth * scale;
  const height = image.naturalHeight * scale;
  // Keep every edge of the canvas covered by the image, so the circular
  // avatar area can never reveal a white/empty region while dragging.
  const maxOffsetX = Math.max(0, (width - CROP_SIZE) / 2);
  const maxOffsetY = Math.max(0, (height - CROP_SIZE) / 2);
  cropOffsetX.value = Math.min(maxOffsetX, Math.max(-maxOffsetX, cropOffsetX.value));
  cropOffsetY.value = Math.min(maxOffsetY, Math.max(-maxOffsetY, cropOffsetY.value));
}

function changeCropZoom(value: number) {
  cropZoom.value = Math.min(3, Math.max(1, Number((cropZoom.value + value).toFixed(2))));
  drawCropCanvas();
}

function resetCrop() {
  cropZoom.value = 1;
  cropOffsetX.value = 0;
  cropOffsetY.value = 0;
  drawCropCanvas();
}

function handleCropWheel(event: WheelEvent) {
  changeCropZoom(event.deltaY > 0 ? -0.05 : 0.05);
}

function startCropDrag(event: PointerEvent) {
  cropDragging.value = true;
  cropDragStart.x = event.clientX;
  cropDragStart.y = event.clientY;
  cropDragStart.offsetX = cropOffsetX.value;
  cropDragStart.offsetY = cropOffsetY.value;
  (event.currentTarget as HTMLCanvasElement).setPointerCapture(event.pointerId);
}

function moveCropDrag(event: PointerEvent) {
  if (!cropDragging.value) return;
  const canvas = event.currentTarget as HTMLCanvasElement;
  const bounds = canvas.getBoundingClientRect();
  const canvasScaleX = CROP_SIZE / bounds.width;
  const canvasScaleY = CROP_SIZE / bounds.height;
  cropOffsetX.value = cropDragStart.offsetX + (event.clientX - cropDragStart.x) * canvasScaleX;
  cropOffsetY.value = cropDragStart.offsetY + (event.clientY - cropDragStart.y) * canvasScaleY;
  drawCropCanvas();
}

function stopCropDrag(event?: PointerEvent) {
  cropDragging.value = false;
  if (event?.currentTarget instanceof HTMLCanvasElement && event.currentTarget.hasPointerCapture(event.pointerId)) {
    event.currentTarget.releasePointerCapture(event.pointerId);
  }
}

function closeCropper() {
  cropDialogVisible.value = false;
  cropImage.value = null;
  if (cropSourceUrl.value) {
    URL.revokeObjectURL(cropSourceUrl.value);
    cropSourceUrl.value = "";
  }
}

function confirmCrop() {
  const canvas = cropCanvas.value;
  if (!canvas) return;

  canvas.toBlob((blob) => {
    if (!blob) {
      ElMessage.error("头像裁剪失败，请重试");
      return;
    }
    if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
    selectedAvatar.value = new File([blob], `avatar-${Date.now()}.jpg`, { type: "image/jpeg" });
    previewUrl.value = URL.createObjectURL(blob);
    closeCropper();
  }, "image/jpeg", 0.96);
}

async function saveProfile() {
  const name = displayName.value.trim();
  if (!name) {
    ElMessage.warning("请输入展示名称");
    return;
  }
  saving.value = true;
  try {
    const profile = await updateProfile(name, careerStatus.value, selectedAvatar.value);
    userStore.setUser(profile);
    selectedAvatar.value = undefined;
    ElMessage.success("个人资料已保存");
  } catch (error) {
    ElMessage.error(axios.isAxiosError(error) ? error.message : "个人资料保存失败，请稍后重试");
  } finally {
    saving.value = false;
  }
}

onBeforeUnmount(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  if (cropSourceUrl.value) URL.revokeObjectURL(cropSourceUrl.value);
});
</script>

<template>
  <div class="page-view profile-view">
    <section class="page-intro profile-intro">
      <div><span class="eyebrow">个人资料</span><h1>完善你的个人资料</h1><p>修改展示名称和头像，它们会显示在你的工作区中。</p></div>
    </section>

    <section class="profile-layout">
      <el-card class="surface-card profile-card" shadow="never">
        <div class="profile-card-heading"><div class="profile-heading-icon"><el-icon><UserFilled /></el-icon></div><div><span class="eyebrow">PROFILE SETTINGS</span><h2>基本资料</h2><p>你的登录账号不会因修改展示名称而改变。</p></div></div>
        <div class="profile-avatar-editor">
          <el-avatar :size="92" class="profile-large-avatar" :src="avatarSrc"><el-icon><UserFilled /></el-icon></el-avatar>
          <div><strong>头像</strong><p>建议使用清晰的 JPG、PNG 或 WEBP 图片，大小不超过 5 MB。</p><label class="profile-upload-button" for="avatar-input"><el-icon><Camera /></el-icon>更换头像</label><input id="avatar-input" class="profile-file-input" type="file" accept="image/jpeg,image/png,image/webp" @change="chooseAvatar" /></div>
        </div>
        <el-form label-position="top" class="profile-form" @submit.prevent="saveProfile">
          <el-form-item label="展示名称"><el-input v-model="displayName" size="large" maxlength="50" show-word-limit placeholder="请输入你的展示名称"><template #prefix><el-icon><UserFilled /></el-icon></template></el-input><small>这个名称会显示在首页欢迎语和顶部个人菜单中。</small></el-form-item>
          <el-form-item label="登录账号"><el-input :model-value="userStore.user?.username" size="large" disabled><template #prefix><el-icon><Lock /></el-icon></template></el-input><small>登录账号仅用于登录，不能在个人资料中修改。</small></el-form-item>
          <el-form-item label="求职状态"><el-select v-model="careerStatus" size="large" placeholder="请选择你的求职状态"><el-option v-for="option in careerStatusOptions" :key="option" :label="option" :value="option" /></el-select><small>这个状态会显示在你的个人资料和工作区顶部。</small></el-form-item>
          <el-button class="profile-save-button" type="primary" size="large" :loading="saving" @click="saveProfile"><el-icon><Check /></el-icon>保存个人资料</el-button>
        </el-form>
      </el-card>
      <el-card class="surface-card profile-preview-card" shadow="never">
        <span class="eyebrow">PREVIEW</span><h2>展示效果</h2>
        <div class="profile-preview"><el-avatar :size="48" :src="avatarSrc"><el-icon><UserFilled /></el-icon></el-avatar><div><strong>{{ displayName || "你的名字" }}</strong><small>{{ careerStatus }}</small></div><span class="profile-preview-dot"></span></div>
        <div class="profile-security-note"><el-icon><Lock /></el-icon><div><strong>账号安全</strong><p>头像和展示名称不会影响你的登录凭证。</p></div></div>
      </el-card>
    </section>

    <teleport to="body">
      <transition name="profile-crop-fade">
        <div v-if="cropDialogVisible" class="profile-crop-backdrop" @click.self="closeCropper">
          <section class="profile-crop-dialog" role="dialog" aria-modal="true" aria-label="裁剪头像">
            <button class="profile-crop-close" type="button" aria-label="关闭" @click="closeCropper">
              <el-icon><Close /></el-icon>
            </button>
            <div class="profile-crop-heading">
              <span class="eyebrow">EDIT AVATAR</span>
              <h2>调整头像</h2>
              <p>拖动图片调整位置，使用滚轮或滑块缩放。</p>
            </div>
            <div class="profile-crop-stage">
              <canvas
                ref="cropCanvas"
                class="profile-crop-canvas"
                width="1024"
                height="1024"
                @pointerdown="startCropDrag"
                @pointermove="moveCropDrag"
                @pointerup="stopCropDrag"
                @pointercancel="stopCropDrag"
                @wheel.prevent="handleCropWheel"
              ></canvas>
              <div class="profile-crop-guide" aria-hidden="true">
                <i></i><i></i><i></i><i></i>
              </div>
            </div>
            <div class="profile-crop-toolbar">
              <el-button circle @click="changeCropZoom(-0.1)"><el-icon><ZoomOut /></el-icon></el-button>
              <input v-model.number="cropZoom" class="profile-crop-range" type="range" min="1" max="3" step="0.01" @input="drawCropCanvas" />
              <el-button circle @click="changeCropZoom(0.1)"><el-icon><ZoomIn /></el-icon></el-button>
              <span class="profile-crop-zoom">{{ Math.round(cropZoom * 100) }}%</span>
              <el-button text @click="resetCrop"><el-icon><RefreshLeft /></el-icon>重置</el-button>
            </div>
            <div class="profile-crop-actions">
              <el-button size="large" @click="closeCropper">取消</el-button>
              <el-button type="primary" size="large" @click="confirmCrop">确认使用</el-button>
            </div>
          </section>
        </div>
      </transition>
    </teleport>
  </div>
</template>
