import { createPinia } from "pinia";
import { createApp } from "vue";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import "element-plus/theme-chalk/dark/css-vars.css";

import App from "./App.vue";
import { i18n } from "./i18n";
import router from "./router";
import "./style.css";
import { initTheme } from "./theme";

initTheme();

createApp(App).use(createPinia()).use(router).use(ElementPlus).use(i18n).mount("#app");
