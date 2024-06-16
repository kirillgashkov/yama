<script setup lang="ts">
import { type Ref, ref } from "vue";
import { useApiService } from "@/api/service";

const api = useApiService();

const file: Ref<unknown> = ref(null);

const content: Ref<unknown> = ref(null);

async function getFile() {
  try {
    file.value = await api.get("/files/etc/passwd");
  } catch (error) {
    file.value = null;
  }
}

async function getContent() {
  try {
    const r = await api.getAsResponse((file.value as any).content.url);
    content.value = await r.text();
  } catch (error) {
    content.value = null;
  }
}
</script>

<template>
  <p><button @click="getFile">Get file</button></p>
  <p>file: {{ file || "null" }}</p>
  <p><button @click="getContent">Get content</button></p>
  <p>content: {{ content || "null" }}</p>
</template>
