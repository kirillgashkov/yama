<script setup lang="ts">
import { type Ref, ref, shallowRef } from "vue";
import { ApiError, useApiService } from "@/api/service";
import { Codemirror } from "vue-codemirror";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";

const api = useApiService();

const filePath: Ref<string> = ref("/@alice/example.md");
const file: Ref<unknown> = ref(null);
const fileError: Ref<string | null> = ref(null);

async function getFile() {
  try {
    fileError.value = null;
    // FIXME: Build URL properly.
    file.value = await api.get("/files/" + filePath.value);
  } catch (error) {
    file.value = null;
    if (error instanceof ApiError && error.name_) {
      fileError.value = error.name_;
    } else {
      fileError.value = "unknown";
    }
  }
}

const content: Ref<string> = ref("");

async function getContent() {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const r = await api.getAsResponse((file.value as any).content.url);
    content.value = await r.text();
  } catch (error) {
    content.value = "";
  }
}

const savedAt: Ref<Date | null> = ref(null);
const saveError: Ref<string | null> = ref(null);

async function save() {
  try {
    saveError.value = null;

    const formData = new FormData();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    formData.append("type", (file.value as any).type);
    formData.append(
      "content",
      new Blob([content.value], { type: "text/plain" }),
    );
    // FIXME: Build URL properly.
    await api.put("/files/" + filePath.value, formData);

    savedAt.value = new Date();
  } catch (error) {
    if (error instanceof Error) {
      saveError.value = error.message;
    } else {
      saveError.value = "Unknown error";
    }
  }
}

const extensions = [markdown({ base: markdownLanguage })];
const view = shallowRef();

function handleReady(payload: {
  view: import("@codemirror/view").EditorView;
}): boolean {
  view.value = payload.view;
  return true;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function getCodemirrorStates() {
  const state = view.value.state;
  const ranges = state.selection.ranges;

  // const selected = ranges.reduce((r, range) => r + range.to - range.from, 0);
  const cursor = ranges[0].anchor;
  const length = state.doc.length;
  const lines = state.doc.lines;

  return { cursor, length, lines };
}

const exportResult: Ref<unknown> = ref(null);
const exportStatus: Ref<string | null> = ref(null);

async function exportFile() {
  try {
    // FIXME: Build URL properly.
    exportStatus.value = "Running.";
    exportResult.value = await api.post(
      "/functions/export?file=" + filePath.value,
    );
    exportStatus.value = "Ok or error.";
  } catch (error) {
    exportResult.value = null;
    exportStatus.value = "Error.";
  }
}
</script>

<template>
  <div>
    <p>File path: <input v-model="filePath" /></p>
  </div>
  <p><button @click="getFile">Get file</button></p>
  <p>file: {{ file || "null" }}</p>
  <p>file error: {{ fileError || "null" }}</p>
  <p><button @click="getContent">Get content</button></p>
  <div>
    <codemirror
      v-model="content"
      placeholder="Code goes here..."
      :style="{ height: '400px' }"
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
  <div>
    <p><button @click="save">Save</button></p>
    <p>Saved at: {{ (savedAt && savedAt.toISOString()) || "null" }}</p>
    <p>Save error: {{ saveError || "null" }}</p>
  </div>
  <div>
    <p><button @click="exportFile">Export file</button></p>
    <p>Export status: {{ exportStatus || "null" }}</p>
    <p>Export result: {{ exportResult || "null" }}</p>
  </div>
</template>
