export class LatestRequest {
  constructor() {
    this.controller = null;
  }

  abort() {
    this.controller?.abort();
    this.controller = null;
  }

  async json(url, options = {}) {
    this.abort();
    const controller = new AbortController();
    this.controller = controller;
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw Error(data.error || `請求失敗（${response.status}）`);
      return data;
    } finally {
      if (this.controller === controller) this.controller = null;
    }
  }

  async blob(url, options = {}) {
    this.abort();
    const controller = new AbortController();
    this.controller = controller;
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw Error(data.error || `請求失敗（${response.status}）`);
      }
      return await response.blob();
    } finally {
      if (this.controller === controller) this.controller = null;
    }
  }
}

export function jsonOptions(body) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function isAbort(error) {
  return error?.name === "AbortError";
}
