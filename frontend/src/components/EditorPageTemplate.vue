<script setup lang="ts">
import { type Ref, type ComputedRef, ref, computed, watch } from "vue";
import { useRoute } from "vue-router";
import {
  useFileService,
  type FileOut,
  type FileContentOut,
  FileType,
} from "@/file";

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
</script>

<template>
  <h1>{{ path }}</h1>
  <h1>{{ workingFileId }}</h1>
  <button @click="readFile">Button</button>
  <div>
    <div v-if="file === null">Loading...</div>
    <div v-else>
      {{ file }}
    </div>
  </div>
  <div>
    <div>
      {{ content }}
    </div>
  </div>
</template>
