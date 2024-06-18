import { useApiStore } from "@/api/store";

if (typeof import.meta.env.VITE_API_BASE_URL !== "string") {
  throw new Error("VITE_API_BASE_URL is not a string.");
}
const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL;
if (import.meta.env.DEV) {
  console.log("API base URL:", API_BASE_URL);
}

type Resource = string | URL | ((url: URL) => URL);

interface ErrorOut {
  name?: string;
  detail: string;
}

export class ApiError extends Error {
  public name_: string | null;
  public detail: string;
  public status: number;

  constructor(name: string | null, detail: string, status: number) {
    super();
    this.name_ = name;
    this.detail = detail;
    this.status = status;
    this.message = `${status} ${detail}`;
  }
}

async function createApiError(response: Response): Promise<ApiError> {
  const e = (await response.json()) as ErrorOut;
  return new ApiError(e.name || null, e.detail, response.status);
}

async function fetchApi(
  resource: Resource,
  init?: RequestInit,
): Promise<Response> {
  let url: URL;

  if (typeof resource === "function") {
    url = resource(new URL(API_BASE_URL));
  } else if (typeof resource === "string") {
    url = new URL(resource, API_BASE_URL);
  } else if (resource instanceof URL) {
    url = resource;
  } else {
    throw new Error("Invalid resource.");
  }

  return await fetch(url, init);
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
    resource: Resource,
    body: unknown | FormData = null,
  ): Promise<Response> {
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

    let response = await fetchApi(resource, config);

    if (response.status === 401 && store.refreshToken) {
      await refreshToken();
      if (store.accessToken) {
        config.headers["Authorization"] = `Bearer ${store.accessToken}`;
      }
      response = await fetchApi(resource, config);
    }

    if (!response.ok) {
      // TODO: Improve handling of error responses.
      throw await createApiError(response);
    }

    return response;
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
    async get(resource: Resource): Promise<unknown> {
      return (await request("GET", resource)).json();
    },
    async getAsResponse(resource: Resource): Promise<Response> {
      return await request("GET", resource);
    },
    async post(
      resource: Resource,
      body: unknown | FormData | null = null,
    ): Promise<unknown> {
      return (await request("POST", resource, body)).json();
    },
    async put(
      resource: Resource,
      body: unknown | FormData | null = null,
    ): Promise<unknown> {
      return (await request("PUT", resource, body)).json();
    },
    async delete(resource: Resource): Promise<unknown> {
      return (await request("DELETE", resource)).json();
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
