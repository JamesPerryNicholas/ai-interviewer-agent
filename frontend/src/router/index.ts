import { createRouter, createWebHistory } from "vue-router";

import { useUserStore } from "../stores/user";
import { useAdminStore } from "../stores/admin";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("../views/LoginView.vue"),
      meta: { titleKey: "login.eyebrow" },
    },
    {
      path: "/login_Admin",
      name: "admin-login",
      component: () => import("../views/AdminLoginView.vue"),
    },
    {
      path: "/admin",
      component: () => import("../layouts/AdminLayout.vue"),
      meta: { requiresAdmin: true },
      children: [
        {
          path: "usage",
          name: "admin-usage",
          component: () => import("../views/AdminUsageView.vue"),
        },
        {
          path: "users",
          name: "admin-users",
          component: () => import("../views/AdminUsersView.vue"),
        },
        {
          path: "",
          redirect: "/admin/usage",
        },
      ],
    },
    {
      path: "/",
      redirect: "/dashboard",
    },
    {
      path: "/dashboard",
      component: () => import("../layouts/AppLayout.vue"),
      meta: { requiresAuth: true },
      children: [
        {
          path: "",
          name: "dashboard",
          component: () => import("../views/DashboardView.vue"),
          meta: { titleKey: "nav.overview" },
        },
        {
          path: "/resume",
          name: "resume",
          component: () => import("../views/ResumeView.vue"),
          meta: { titleKey: "nav.resume" },
        },
        {
          path: "/jobs",
          name: "jobs",
          component: () => import("../views/Job.vue"),
          meta: { titleKey: "nav.jobs" },
        },
        {
          path: "/profile",
          name: "profile",
          component: () => import("../views/ProfileView.vue"),
          meta: { title: "个人资料", titleKey: "nav.profile" },
        },
        {
          path: "/settings",
          name: "settings",
          component: () => import("../views/SettingsView.vue"),
          meta: { title: "设置", titleKey: "nav.settings" },
        },
        {
          path: "/interview/history",
          name: "interview-history",
          component: () => import("../views/InterviewHistoryView.vue"),
          meta: { title: "历史面试", titleKey: "nav.practice" },
        },
        {
          path: "/interview/:id",
          name: "interview",
          component: () => import("../views/InterviewView.vue"),
          meta: { titleKey: "nav.practice" },
        },
        {
          path: "/report/:id",
          name: "report",
          component: () => import("../views/ReportView.vue"),
          meta: { titleKey: "common.export" },
        },
      ],
    },
  ],
});

router.beforeEach(async (to) => {
  const userStore = useUserStore();
  const adminStore = useAdminStore();

  if (to.meta.requiresAdmin) {
    if (!adminStore.isAuthenticated) {
      return { name: "admin-login", query: { redirect: to.fullPath } };
    }
    if (!adminStore.admin) {
      try {
        await adminStore.loadAdmin();
      } catch {
        return { name: "admin-login", query: { redirect: to.fullPath } };
      }
    }
  }

  if (to.meta.requiresAuth) {
    if (!userStore.isAuthenticated) {
      return { name: "login", query: { redirect: to.fullPath } };
    }

    if (!userStore.user) {
      try {
        await userStore.loadUser();
      } catch {
        return { name: "login", query: { redirect: to.fullPath } };
      }
    }
  }

  if (to.name === "login" && userStore.isAuthenticated) {
    return { name: "dashboard" };
  }

  if (to.name === "admin-login" && adminStore.isAuthenticated) {
    return { name: "admin-usage" };
  }

  return true;
});

export default router;
