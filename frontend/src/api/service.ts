import { useApiStore } from "@/api/store";

if (typeof import.meta.env.VITE_API_BASE_URL !== "string") {
  throw new Error("VITE_API_BASE_URL is not a string.");
}
const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL;
if (import.meta.env.DEV) {
  console.log("API base URL:", API_BASE_URL);
}

interface ErrorOut {
  detail: string;
}

export class ApiError extends Error {
  public detail: string;
  public status: number;

  constructor(detail: string, status: number) {
    super();
    this.detail = detail;
    this.status = status;
    this.message = `${status} ${detail}`;
  }
}

async function createApiError(response: Response): Promise<ApiError> {
  const e = (await response.json()) as ErrorOut;
  return new ApiError(e.detail, response.status);
}

async function fetchApi(path: string, init?: RequestInit): Promise<Response> {
  return await fetch(API_BASE_URL + path, init);
}

interface TokenOut {
  access_token: string;
  expires_in: number; // TODO: Utilize.
  refresh_token: string | null;
}

export function useApiService() {
  const store = useApiStore();

  async function request(
    method: string,
    path: string,
    body: unknown = null,
  ): Promise<unknown> {
    const config: RequestInit = {};
    config.method = method;
    config.headers = {};

    if (store.accessToken) {
      config.headers["Authorization"] = `Bearer ${store.accessToken}`;
    }

    if (body !== null) {
      if (body instanceof FormData) {
        // Content-Type is set automatically for FormData. It is chosen to be
        // multipart/form-data or application/x-www-form-urlencoded.
        config.body = body;
      } else {
        config.headers["Content-Type"] = "application/json";
        config.body = JSON.stringify(body);
      }
    }

    let response = await fetchApi(path, config);

    if (response.status === 401 && store.refreshToken) {
      await refreshToken();
      if (store.accessToken) {
        config.headers["Authorization"] = `Bearer ${store.accessToken}`;
      }
      response = await fetchApi(path, config);
    }

    if (!response.ok) {
      // TODO: Improve handling of error responses.
      throw await createApiError(response);
    }

    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      return (await response.json()) as unknown;
    } else {
      return await response.blob();
    }
  }

  async function refreshToken() {
    if (!store.refreshToken) throw new Error("No refresh token available.");

    const formData = new FormData();
    formData.append("grant_type", "refresh_token");
    formData.append("refresh_token", store.refreshToken);

    const response = await fetchApi("/auth", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      store.clearTokens();
      throw await createApiError(response);
    }

    const token = (await response.json()) as TokenOut;
    store.setTokens(token.access_token, token.refresh_token);
  }

  return {
    async get(path: string): Promise<unknown> {
      return await request("GET", path);
    },
    async post(path: string, body: unknown): Promise<unknown> {
      return await request("POST", path, body);
    },
    async put(path: string, body: unknown): Promise<unknown> {
      return await request("PUT", path, body);
    },
    async delete(path: string): Promise<unknown> {
      return await request("DELETE", path);
    },
    async auth(username: string, password: string): Promise<void> {
      const formData = new FormData();
      formData.append("grant_type", "password");
      formData.append("username", username);
      formData.append("password", password);

      const response = await fetchApi("/auth", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw await createApiError(response);
      }

      const token = (await response.json()) as TokenOut;
      store.setTokens(token.access_token, token.refresh_token);
    },
    async unauth(): Promise<void> {
      if (!store.refreshToken) return;

      const formData = new FormData();
      formData.append("refresh_token", store.refreshToken);

      const response = await fetchApi("/unauth", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw await createApiError(response);
      }

      store.clearTokens();
    },
  };
}
