import { defineStore } from "pinia";
import { ref } from "vue";

export const useApiStore = defineStore("api", () => {
  const accessToken = ref<string | null>(localStorage.getItem("accessToken"));
  const refreshToken = ref<string | null>(localStorage.getItem("refreshToken"));

  function setTokens(newAccessToken: string, newRefreshToken: string | null) {
    accessToken.value = newAccessToken;
    localStorage.setItem("accessToken", newAccessToken);

    if (newRefreshToken !== null) {
      refreshToken.value = newRefreshToken;
      localStorage.setItem("refreshToken", newRefreshToken);
    }
  }

  function clearTokens() {
    accessToken.value = null;
    refreshToken.value = null;
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
  }

  return { accessToken, refreshToken, setTokens, clearTokens };
});
