<script setup lang="ts">
import { type Ref, type ComputedRef, ref, computed, watch } from "vue";
import { useRoute } from "vue-router";
import { useFileService, type FileOut, FileType } from "@/file";
import eyeSvg from "@/assets/heroicons-eye-outline.svg?raw";
import ellipsisSvg from "@/assets/heroicons-ellipsis-horizontal.svg?raw";
import MarkdownDiv from "@/components/MarkdownDiv.vue";
import EditorMenu from "@/components/EditorMenu.vue";
import { shallowRef } from "vue";
import { Codemirror } from "vue-codemirror";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";

const route = useRoute();
const fileService = useFileService();

const path: Ref<string> = ref(<string>route.params.path);
const workingFileId: ComputedRef<string> = computed(() => {
  const idOrIds = route.query.working_file_id;

  if (Array.isArray(idOrIds)) {
    return idOrIds.pop() ?? "";
  }

  return idOrIds ?? "";
});

const file: Ref<FileOut | null> = ref(null);
const content: Ref<string> = ref("");

async function readFile() {
  file.value = null;
  content.value = "";
  file.value = await fileService.read(path.value, {
    workingFileId: workingFileId.value,
  });
  if (file.value.type === FileType.REGULAR) {
    content.value = await fileService.readContent(".", {
      workingFileId: file.value.id,
    });
  }
}

watch(
  [path, workingFileId],
  () => {
    readFile();
  },
  { immediate: true },
);

const extensions = [markdown({ base: markdownLanguage })];
const view = shallowRef();

function handleReady(payload: {
  view: import("@codemirror/view").EditorView;
}): boolean {
  view.value = payload.view;
  return true;
}
</script>

<template>
  <div class="border-t-4 border-[#F74C00]"></div>
  <article
    class="container prose prose-zinc mx-auto p-4 lg:prose-xl dark:prose-invert lg:p-8"
  >
    <div class="flex items-center justify-between">
      <div>
        <h1>
          <MarkdownDiv :content="path" />
        </h1>
      </div>
      <div class="not-prose flex touch-manipulation space-x-2 lg:space-x-3">
        <EditorMenu
          menuItemsWidthClass="w-24 lg:w-28"
          :menuButtonSvg="eyeSvg"
          :menuItems="[
            { routerLink: '/', title: 'English' },
            { routerLink: '/ru', title: 'Русский' },
          ]"
        />
        <EditorMenu
          menuItemsWidthClass="w-24 lg:w-28"
          :menuButtonSvg="ellipsisSvg"
          :menuItems="[
            { routerLink: '/', title: 'English' },
            { routerLink: '/ru', title: 'Русский' },
          ]"
        />
      </div>
    </div>
    <div class="border border-zinc-300">
      <codemirror
        v-model="content"
        :style="{ 'min-height': '150px' }"
        :autofocus="true"
        :indent-with-tab="true"
        :tab-size="2"
        :extensions="extensions"
        @ready="handleReady"
        @change="console.log('change', $event)"
        @focus="console.log('focus', $event)"
        @blur="console.log('blur', $event)"
      />
    </div>
  </article>
</template>
