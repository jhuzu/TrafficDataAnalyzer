import { LatestRequest, isAbort, jsonOptions } from "./api.js";

export function createSlideGenerator({ getToken, getPeriod, status }) {
  const request = new LatestRequest();

  async function generate(variant, button) {
    if (!getToken()) {
      status.textContent = "請先載入 .xlsx 或 .xlsm 檔案。";
      return;
    }
    const label = variant === "traditional" ? "傳統版本" : "新式版本";
    button.disabled = true;
    status.textContent = `正在生成${label}投影片…`;
    try {
      const blob = await request.blob(
        "/generate-pptx",
        jsonOptions({ token: getToken(), period: getPeriod().trim(), variant }),
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `交通事故分析週報_${label}.pptx`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
      status.textContent = `已生成並下載${label}。`;
    } catch (error) {
      if (!isAbort(error)) status.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  return { generate, abort: () => request.abort() };
}
