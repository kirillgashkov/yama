<script setup lang="ts">
import { ref } from "vue";
import {
  Dialog,
  DialogOverlay,
  DialogTitle,
  DialogDescription,
} from "@headlessui/vue";
import { useApiService } from "@/api";

// Props
const props = defineProps<{
  isOpen: boolean;
}>();

// Emits
const emit = defineEmits(["close"]);

// State
const styleFilePath = ref("/@export/gost/export.toml");
const centerHeadings = ref(false);
const enableSectionBreaks = ref(false);
const isExporting = ref(false);

// Methods
const closePopup = () => {
  emit("close");
};

const handleExport = async () => {
  isExporting.value = true;
  try {
    const url = await exportFile(
      styleFilePath.value,
      centerHeadings.value,
      enableSectionBreaks.value,
    );
    window.open(url, "_blank");
  } finally {
    isExporting.value = false;
    closePopup();
  }
};

const exportFile = async (
  styleFilePath: string,
  centerHeadings: boolean,
  enableSectionBreaks: boolean,
) => {
  await new Promise((resolve) => setTimeout(resolve, 5424));
  return new URL(
    "http://localhost:5173/files/albert.pdf?raw=1&working_file_id=7860992e-0512-43e9-a041-27f355b1ddf5",
  );
};
</script>

<template>
  <Dialog
    :open="isOpen"
    @close="closePopup"
    class="fixed inset-0 z-50 overflow-y-auto"
  >
    <div class="flex min-h-screen items-center justify-center">
      <DialogOverlay class="fixed inset-0 bg-black opacity-30" />
      <div
        class="relative mx-auto w-full max-w-md rounded-lg bg-white p-6 shadow-lg dark:bg-gray-800"
      >
        <DialogTitle
          class="text-xl font-medium leading-6 text-gray-900 dark:text-white"
        >
          Экспорт документа
        </DialogTitle>
        <DialogDescription class="mt-2 text-gray-600 dark:text-gray-300">
          Выберите параметры экспорта.
        </DialogDescription>

        <div class="mt-4">
          <label
            class="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >Файл конфигурации экспорта</label
          >
          <input
            type="text"
            v-model="styleFilePath"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white dark:focus:ring-white"
          />
        </div>

        <div class="mt-4">
          <label
            class="inline-flex items-center text-gray-700 dark:text-gray-300"
          >
            <input
              type="checkbox"
              v-model="centerHeadings"
              class="form-checkbox text-indigo-600 focus:ring-indigo-500 dark:border-gray-700 dark:text-indigo-500"
            />
            <span class="ml-2">Заголовки по центру</span>
          </label>
        </div>

        <div class="mt-4">
          <label
            class="inline-flex items-center text-gray-700 dark:text-gray-300"
          >
            <input
              type="checkbox"
              v-model="enableSectionBreaks"
              class="form-checkbox text-indigo-600 focus:ring-indigo-500 dark:border-gray-700 dark:text-indigo-500"
            />
            <span class="ml-2">Новые страницы для разделов</span>
          </label>
        </div>

        <div class="mt-4 flex justify-end">
          <button
            @click="closePopup"
            class="mr-3 rounded-md bg-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
          >
            Отмена
          </button>
          <button
            v-if="!isExporting"
            @click="handleExport"
            class="rounded-md bg-[#F74C00] px-4 py-2 text-sm font-medium text-white hover:bg-[#b53904] focus:outline-none focus:ring-2 focus:ring-[#b53904] focus:ring-offset-2"
          >
            <span>Экспорт</span>
          </button>
          <button
            v-else
            :disabled="true"
            class="rounded-md bg-gray-200 px-4 py-2 text-sm font-medium text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:bg-gray-700 dark:text-gray-300"
          >
            <span>Экспорт...</span>
          </button>
        </div>
      </div>
    </div>
  </Dialog>
</template>
