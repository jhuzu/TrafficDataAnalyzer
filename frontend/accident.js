import { LatestRequest, isAbort, jsonOptions } from "./api.js";
import { createAnalysisChart } from "./chart.js";
import { createAccidentMap } from "./map.js";
import { createSlideGenerator } from "./slides.js";
import { $, esc, state, trendTable } from "./common.js";

const names = { road: "易肇事路段", intersection: "易肇事路口", time: "易肇事時段", cause: "易肇事肇因", age: "易肇事年齡", vehicle: "易肇事車種" };

export function initAccident() {
  const loadRequest = new LatestRequest();
  const analysisRequest = new LatestRequest();
  const chart = createAnalysisChart($("analysisChart"));
  const accidentMap = createAccidentMap({
    container: $("accidentMap"), info: $("mapInfo"), unlocated: $("mapUnlocated"), baseLayerSelect: $("mapBasemap"), getToken: () => state.token,
    getOptions: () => ({ pattern: $("pattern").value, startDate: $("accidentStartDate").value || undefined, endDate: $("accidentEndDate").value || undefined }),
    getDensityEnabled: () => $("mapDensityToggle").checked,
    getDensityThreshold: () => Math.max(1, Number($("mapDensityThreshold").value) || 5), escapeHtml: esc,
  });
  const slides = createSlideGenerator({ getToken: () => state.token, status: $("slideStatus") });
  const setStatus = (message) => { $("status").textContent = message; };

  function uploadForm() {
    const file = $("fileInput").files[0];
    if (!file) throw Error("請先選取 .xlsx 或 .xlsm 檔案。");
    const form = new FormData(); form.append("file", file); return form;
  }

  async function loadData() {
    const button = $("loadButton"); button.disabled = true;
    try {
      setStatus("正在辨識 Excel 資料來源…");
      const data = await loadRequest.json("/load", { method: "POST", body: uploadForm() });
      state.token = data.token;
      const sourceName = data.sourceType === "pivot-cache" ? "Pivot Cache" : `工作表${data.sheetName ? `「${data.sheetName}」` : ""}`;
      const countRule = data.rowMode === "raw" ? "每列按 1 件計算" : "使用「件數」欄加總";
      setStatus(`已由${sourceName}載入 ${Number(data.rows).toLocaleString()} 筆資料；${countRule}。${(data.warnings || []).join(" ")}`);
      await analyze();
    } catch (error) { if (!isAbort(error)) setStatus(error.message); } finally { button.disabled = false; }
  }

  async function analyze() {
    if (!state.token) return;
    const button = $("analyzeButton"); button.disabled = true;
    try {
      const data = await analysisRequest.json("/analyze", jsonOptions({ token: state.token, pattern: $("pattern").value, startDate: $("accidentStartDate").value || undefined, endDate: $("accidentEndDate").value || undefined, period: $("period").value, top: Number($("top").value) }));
      state.latest = data; render(data);
      if (!$("panel-map").classList.contains("hidden")) await accidentMap.load();
    } catch (error) { if (!isAbort(error)) setStatus(error.message); } finally { button.disabled = false; }
  }

  function renderComparison(comparison) {
    if (!comparison) { $("yearComparison").innerHTML = '<span class="muted">選擇完整起訖日後，顯示去年同期比較。</span>'; return; }
    const rate = comparison.rate === null ? "前期無資料" : `${comparison.rate >= 0 ? "+" : ""}${(comparison.rate * 100).toFixed(1)}%`;
    const direction = comparison.difference > 0 ? "增加" : comparison.difference < 0 ? "減少" : "持平";
    $("yearComparison").textContent = `去年同期（${comparison.previousPeriod}）${Number(comparison.previousTotal).toLocaleString()} 件；本期${direction} ${Math.abs(Number(comparison.difference)).toLocaleString()} 件（${rate}）。`;
  }

  function render(data) {
    $("metrics").innerHTML = data.metrics.map((item) => `<div class="metric"><small>${esc(item.label)}</small><strong>${Number(item.value).toLocaleString()}</strong></div>`).join("");
    const key = $("basicMetric").value, items = data[key] || [];
    $("analysisTitle").textContent = names[key];
    $("analysisTable").innerHTML = items.length ? `<table><thead><tr><th>項目</th><th>數量</th></tr></thead><tbody>${items.map((item) => `<tr><td>${esc(item.value)}</td><td>${Number(item.count).toLocaleString()}</td></tr>`).join("")}</tbody></table>` : "<p>沒有符合資料</p>";
    chart.draw(items, names[key]); $("trendTable").innerHTML = trendTable(data.trend); renderComparison(data.yearComparison); $("narrative").textContent = data.narrative || "";
  }

  function showPanel(kind) {
    document.querySelectorAll(".analysis-panel").forEach((item) => item.classList.toggle("hidden", item.id !== `panel-${kind}`));
    document.querySelectorAll(".analysis-tab").forEach((button) => button.classList.toggle("active", button.dataset.analysis === kind));
    if (kind === "chart" && state.latest) render(state.latest);
    if (kind === "map") setTimeout(async () => { accidentMap.invalidate(); await accidentMap.load(); }, 60);
  }

  function exportTable() {
    const items = state.latest?.[$("basicMetric").value] || [];
    if (!items.length) return setStatus("沒有可匯出的分析資料。");
    const csv = ["項目,數量", ...items.map((item) => `${JSON.stringify(String(item.value))},${item.count}`)].join("\n");
    const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" })); link.download = `${names[$("basicMetric").value]}_分析.csv`; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 0);
  }

  async function clearData() {
    loadRequest.abort(); analysisRequest.abort(); slides.abort();
    if (state.token) { try { await fetch("/clear", jsonOptions({ token: state.token })); } catch (_) { /* local reset */ } }
    state.token = ""; state.latest = null; $("fileInput").value = ""; setStatus("已清除資料，請重新載入 Excel。"); $("slideStatus").textContent = ""; $("metrics").innerHTML = ""; $("analysisTable").innerHTML = "<p>尚未載入資料</p>"; $("trendTable").innerHTML = "<p>尚未載入資料</p>"; $("yearComparison").innerHTML = '<span class="muted">選擇完整起訖日後，顯示去年同期比較。</span>'; $("narrative").textContent = ""; chart.clear(); accidentMap.clear(); showPanel("table");
  }

  $("loadButton").onclick = loadData; $("clearButton").onclick = clearData; $("analyzeButton").onclick = analyze; $("pattern").onchange = analyze; $("accidentStartDate").onchange = analyze; $("accidentEndDate").onchange = analyze; $("period").onchange = analyze; $("top").onchange = analyze; $("basicMetric").onchange = () => state.latest && render(state.latest); $("analysisExportButton").onclick = exportTable; $("mapBasemap").onchange = () => accidentMap.setBaseLayer($("mapBasemap").value); $("mapDensityToggle").onchange = () => accidentMap.load(); $("mapDensityThreshold").onchange = () => accidentMap.render();
  $("generateModernSlidesButton").onclick = () => slides.generate("modern", $("generateModernSlidesButton")); $("generateTraditionalSlidesButton").onclick = () => slides.generate("traditional", $("generateTraditionalSlidesButton")); $("copyButton").onclick = () => navigator.clipboard?.writeText($("narrative").textContent).then(() => setStatus("摘要已複製。"));
  document.querySelectorAll(".analysis-tab").forEach((button) => { button.onclick = () => showPanel(button.dataset.analysis); });
}
