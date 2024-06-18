<script setup lang="ts">
import { computed, type ComputedRef } from "vue";
import type Token from "markdown-it/lib/token.mjs";

import { renderSanitize } from "@/markdown";

const props = defineProps<{
  content: string | Token[];
}>();

const innerHtml: ComputedRef<string> = computed(() => {
  return renderSanitize(props.content);
});
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div v-html="innerHtml"></div>
</template>
