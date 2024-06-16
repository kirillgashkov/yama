<script setup lang="ts">
import { ref } from "vue";
import { useApiService } from "@/api/service";

const api = useApiService();

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const user: any = ref(null);

async function signIn() {
  await api.auth("alice", "alice");
}

async function signOut() {
  await api.unauth();
}

async function getCurrentUser() {
  try {
    user.value = await api.get("/users/current");
  } catch (error) {
    user.value = null;
  }
}
</script>

<template>
  <p><button @click="signIn">Sign in</button></p>
  <p><button @click="signOut">Sign out</button></p>
  <p><button @click="getCurrentUser">Get current user</button></p>
  <p>user: {{ user || "null" }}</p>
</template>
