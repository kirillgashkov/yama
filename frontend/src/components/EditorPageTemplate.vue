<script setup lang="ts">
import { ref } from "vue";
import { useApiService } from "@/api/service";

const api = useApiService();

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const file: any = ref(null);

async function getFile() {
  try {
    file.value = await api.get("/files/etc/passwd");
  } catch (error) {
    file.value = null;
  }
}
</script>

<template>
  <p><button @click="getFile">Get file</button></p>
  <p>file: {{ file || "null" }}</p>
</template>
