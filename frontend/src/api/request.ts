import axios from "axios";
import { API_BASE_URL } from "./base";

export const TOKEN_KEY = "ai-interviewer-token";
export const USER_KEY = "ai-interviewer-user";

/** Shared Axios client for all frontend-to-backend requests. */
const request = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10_000,
  headers: {
    "Content-Type": "application/json",
  },
});

const messageTranslations: Array<[string, string]> = [
  ["No resume has been uploaded", "暂未上传简历，请先上传简历"],
  ["Resume or job position not found", "未找到简历或岗位"],
  ["Interview not found", "未找到面试记录"],
  ["Message not found", "未找到消息"],
  ["Incorrect account or password", "账号或密码错误"],
  ["Could not validate credentials", "登录凭证无效，请重新登录"],
  ["DeepSeek API is not configured", "DeepSeek API 尚未配置"],
  ["AI interviewer is temporarily unavailable", "AI 面试官暂时不可用，请稍后重试"],
  ["Analyze the resume before generating questions", "请先完成简历分析，再生成面试题"],
  ["Interview question generation failed", "面试题生成失败，请稍后重试"],
  ["Resume analysis failed", "简历分析失败，请稍后重试"],
  ["timeout of", "请求超时，请稍后重试"],
  ["timeout", "AI 正在生成内容，请稍候重试"],
];

function toChineseMessage(value: string) {
  const match = messageTranslations.find(([source]) => value.includes(source));
  return match ? match[1] : value;
}

request.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  // Let the browser add the multipart boundary for FormData uploads.
  if (typeof FormData !== "undefined" && config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }

  return config;
});

request.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail;
    if (detail) {
      const message = Array.isArray(detail)
        ? detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join("; ")
        : String(detail);
      error.message = toChineseMessage(message);
    } else if (typeof error.message === "string") {
      error.message = toChineseMessage(error.message);
    }

    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      if (window.location.pathname !== "/login") {
        const redirect = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.replace(`/login?redirect=${redirect}`);
      }
    }

    return Promise.reject(error);
  },
);

export default request;
