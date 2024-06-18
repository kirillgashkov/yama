<script setup lang="ts">
import { Menu, MenuButton, MenuItem, MenuItems } from "@headlessui/vue";

const props = defineProps<{
  menuButtonSvg: string;
  menuItems: {
    a?: string;
    routerLink?: string;
    clickPrevent?: () => void;
    title: string;
  }[];
  menuItemsWidthClass: string;
}>();
</script>

<template>
  <Menu as="div" class="relative inline-block text-left">
    <MenuButton
      class="text-zinc-900 hover:text-zinc-700 dark:text-white dark:hover:text-zinc-300"
    >
      <!-- FIXME -->
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div class="w-8 lg:w-12" v-html="menuButtonSvg" />
    </MenuButton>

    <Transition
      enter-active-class="transition ease-out duration-100"
      enter-from-class="transform opacity-0 scale-95"
      enter-to-class="transform opacity-100 scale-100"
      leave-active-class="transition ease-in duration-75"
      leave-from-class="transform opacity-100 scale-100"
      leave-to-class="transform opacity-0 scale-95"
    >
      <MenuItems
        :class="[
          props.menuItemsWidthClass,
          'absolute right-0 z-10 origin-top-right overflow-clip rounded-md border border-zinc-100 bg-white shadow-lg shadow-zinc-800/10 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:shadow-white/5',
        ]"
      >
        <div>
          <MenuItem
            v-for="item in props.menuItems"
            :key="item.title"
            v-slot="{ active }"
            :keys="item.title"
          >
            <RouterLink
              v-if="item.routerLink"
              :to="item.routerLink"
              :class="[
                active
                  ? 'bg-zinc-100 text-zinc-900 dark:bg-zinc-700 dark:text-white'
                  : 'text-zinc-700 dark:text-zinc-300',
                'block p-2.5 text-sm lg:p-3 lg:text-base',
              ]"
            >
              {{ item.title }}
            </RouterLink>
            <a
              v-else-if="item.clickPrevent"
              href="#"
              @click.prevent="item.clickPrevent"
              :class="[
                active
                  ? 'bg-zinc-100 text-zinc-900 dark:bg-zinc-700 dark:text-white'
                  : 'text-zinc-700 dark:text-zinc-300',
                'block p-2.5 text-sm lg:p-3 lg:text-base',
              ]"
            >
              {{ item.title }}
            </a>
            <a
              v-else
              :href="item.a"
              :class="[
                active
                  ? 'bg-zinc-100 text-zinc-900 dark:bg-zinc-700 dark:text-white'
                  : 'text-zinc-700 dark:text-zinc-300',
                'block p-2.5 text-sm lg:p-3 lg:text-base',
              ]"
            >
              {{ item.title }}
            </a>
          </MenuItem>
        </div>
      </MenuItems>
    </Transition>
  </Menu>
</template>
