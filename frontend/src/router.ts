import { createWebHistory, createRouter } from "vue-router";

const routes = [
  { path: "/auth", component: () => import("./components/AuthPage.vue") },
  {
    path: "/files",
    redirect: "/files/",
  },
  {
    path: "/files/:path(.*)",
    component: () => import("./components/EditorPageTemplate.vue"),
  },
  {
    path: "/:pathMatch(.*)",
    component: () => import("./components/NotFoundPageTemplate.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
