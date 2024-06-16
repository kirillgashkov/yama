<script setup lang="ts">
import { type Ref, ref, shallowRef } from "vue";
import { useApiService } from "@/api/service";
import { Codemirror } from "vue-codemirror";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";

const api = useApiService();

const file: Ref<unknown> = ref(null);

async function getFile() {
  try {
    file.value = await api.get("/files/etc/passwd");
  } catch (error) {
    file.value = null;
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
</script>

<template>
  <p><button @click="getFile">Get file</button></p>
  <p>file: {{ file || "null" }}</p>
  <p><button @click="getContent">Get content</button></p>
  <p>content: {{ content || "null" }}</p>
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
</template>
