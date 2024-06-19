<script setup lang="ts">
import { type Ref, type ComputedRef, ref, computed, watch } from "vue";
import { useRoute } from "vue-router";
import { useFileService, type FileOut, FileType } from "@/file";
import eyeSvg from "@/assets/heroicons-eye-outline.svg?raw";
import pencilSvg from "@/assets/heroicons-pencil-outline.svg?raw";
import ellipsisSvg from "@/assets/heroicons-ellipsis-horizontal.svg?raw";
import MarkdownDiv from "@/components/MarkdownDiv.vue";
import EditorMenu from "@/components/EditorMenu.vue";
import { shallowRef } from "vue";
import { Codemirror } from "vue-codemirror";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import {
  Dialog,
  DialogDescription,
  DialogOverlay,
  DialogPanel,
  DialogTitle,
} from "@headlessui/vue";
import EditorExportDialog from "@/components/EditorExportDialog.vue";

const route = useRoute();
const fileService = useFileService();

const path: Ref<string> = ref(<string>route.params.path);
const name: ComputedRef<string> = computed(() => {
  return path.value.split("/").pop() ?? ".";
});
const workingFileId: ComputedRef<string> = computed(() => {
  const idOrIds = route.query.working_file_id;

  if (Array.isArray(idOrIds)) {
    return idOrIds.pop() ?? "";
  }

  return idOrIds ?? "";
});
const isRaw: ComputedRef<string> = computed(() => {
  return route.query.raw !== undefined;
});

const file: Ref<FileOut | null> = ref(null);
const content: Ref<string> = ref("");
const rawContent: Ref<Blob> = ref(new Blob());
const objectUrl: ComputedRef<string> = computed(() => {
  return URL.createObjectURL(rawContent.value);
});

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
    rawContent.value = await fileService.readContentBlob(".", {
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

const isViewMode: Ref<boolean> = ref(false);

function toggleViewMode() {
  isViewMode.value = !isViewMode.value;
}

async function exportFile() {
  openPopup();
}

async function importFile() {
  console.log("importFile");
}

async function uploadFile() {
  console.log("uploadFile");
}

const isOpen = ref(false);

function openPopup() {
  isOpen.value = true;
}

function closePopup() {
  isOpen.value = false;
}
</script>

<template>
  <EditorExportDialog :is-open="isOpen" @close="closePopup" />
  <div class="border-t-4 border-[#F74C00]"></div>
  <article
    class="container prose prose-zinc mx-auto p-4 lg:prose-xl dark:prose-invert lg:p-8"
  >
    <div class="flex items-center justify-between">
      <div>
        <h1>
          <MarkdownDiv :content="name" />
        </h1>
      </div>
      <div
        class="not-prose flex touch-manipulation space-x-2 pt-2 lg:space-x-3"
      >
        <a
          v-if="!isRaw"
          href="#"
          @click.prevent="toggleViewMode"
          class="text-zinc-900 hover:text-zinc-700 dark:text-white dark:hover:text-zinc-300"
        >
          <!-- FIXME -->
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div v-if="isViewMode" class="w-8 lg:w-12" v-html="pencilSvg" />
          <div v-else class="w-8 lg:w-12" v-html="eyeSvg" />
        </a>
        <EditorMenu
          menuItemsWidthClass="w-36 lg:w-28"
          :menuButtonSvg="ellipsisSvg"
          :menuItems="[
            { clickPrevent: importFile, title: 'Назад' },
            { clickPrevent: importFile, title: 'Импортировать из DOCX...' },
            { clickPrevent: exportFile, title: 'Экспортировать в PDF...' },
            { clickPrevent: uploadFile, title: 'Загрузить файл...' },
            {
              downloadUrl: objectUrl,
              downloadName: name,
              title: 'Скачать файл',
            },
          ]"
        />
      </div>
    </div>
    <MarkdownDiv v-if="isViewMode" :content="content" />
    <div v-else-if="!isRaw" class="border border-zinc-300">
      <codemirror
        v-model="content"
        class="no-prose"
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
    <iframe v-else :src="objectUrl" class="h-[500px] w-full" />
  </article>
</template>
