import { createWebHistory, createRouter } from "vue-router";

const routes = [
  { path: "/auth", component: () => import("./components/AuthPage.vue") },
  {
    path: "/:pathMatch(.*)",
    component: () => import("./components/NotFoundPage.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
