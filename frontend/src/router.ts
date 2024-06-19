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
    path: "/files-draft",
    component: () => import("./components/EditorPageTemplateDraft.vue"),
  },
  {
    path: "/:path(.*)",
    component: () => import("./components/NotFoundPageTemplate.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

function pathToName(path: string): string {
  return path.split("/").pop() ?? "";
}

router.beforeEach((to) => {
  if (to.params.path) {
    document.title = pathToName(to.params.path) + " | Yama" || "Yama";
  }
});

export default router;
