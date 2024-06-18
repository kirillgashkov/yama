<script setup lang="ts">
import { type Ref, type ComputedRef, ref, computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();

const path: Ref<string> = ref(<string>route.params.path);
const workingFileId: ComputedRef<string> = computed(() => {
  const idOrIds = route.query.working_file_id;

  if (Array.isArray(idOrIds)) {
    return idOrIds.pop() ?? "";
  }

  return idOrIds ?? "";
});
</script>

<template>
  <h1>{{ path }}</h1>
  <h1>{{ workingFileId }}</h1>
  <button @click="console.log(workingFileId)">Button</button>
</template>
