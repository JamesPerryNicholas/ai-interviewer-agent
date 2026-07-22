<script setup lang="ts">
import { computed } from "vue";
import { RouterView } from "vue-router";
import { useI18n } from "vue-i18n";

import { elementLocales, type SupportedLocale } from "./i18n";

const { locale } = useI18n();
const elementLocale = computed(() => elementLocales[locale.value as SupportedLocale] ?? elementLocales.en);
</script>

<template>
  <el-config-provider :locale="elementLocale">
    <RouterView />
  </el-config-provider>
</template>
