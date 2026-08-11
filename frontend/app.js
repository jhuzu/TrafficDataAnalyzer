import { LatestRequest, isAbort, jsonOptions } from "./api.js";
import { createAnalysisChart } from "./chart.js";
import { createAccidentMap } from "./map.js";
import { createSlideGenerator } from "./slides.js";

const state = { token: "", latest: null, majorToken: "", majorLatest: null };
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#39;");

const loadRequest = new LatestRequest();
const analysisRequest = new LatestRequest();
const majorLoadRequest = new LatestRequest();
const majorAnalysisRequest = new LatestRequest();
const chart = createAnalysisChart($("analysisChart"));
const majorChart = createAnalysisChart($("majorChart"));
const accidentMap = createAccidentMap({
  container: $("accidentMap"),
  info: $("mapInfo"),
  getToken: () => state.token,
  getOptions: () => ({
    pattern: $("pattern").value,
    startDate: $("accidentStartDate").value || undefined,
    endDate: $("accidentEndDate").value || undefined,
  }),
  escapeHtml: esc,
});
const slides = createSlideGenerator({
  getToken: () => state.token,
  getPeriod: () => $("slidePeriod").value,
  status: $("slideStatus"),
});

const names = {
  road: "易肇事路段",
  intersection: "易肇事路口",
  time: "易肇事時段",
  cause: "易肇事肇因",
  age: "易肇事年齡",
  vehicle: "易肇事車種",
};

function setStatus(message) {
  $("status").textContent = message;
}

function uploadForm() {
  const file = $("fileInput").files[0];
  if (!file) throw Error("請先選取 .xlsx 或 .xlsm 檔案。");
  const form = new FormData();
  form.append("file", file);
  return form;
}

function majorUploadForm() {
  const files = Array.from($("majorFileInput").files);
  if (!files.length) throw Error("請先選取至少一份 .xlsx 或 .xlsm 檔案。");
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  return form;
}

async function loadData() {
  const button = $("loadButton");
  button.disabled = true;
  try {
    setStatus("正在辨識 Excel 資料來源…");
    const data = await loadRequest.json("/load", { method: "POST", body: uploadForm() });
    state.token = data.token;
    const sourceName = data.sourceType === "pivot-cache"
      ? "Pivot Cache"
      : `工作表${data.sheetName ? `「${data.sheetName}」` : ""}`;
    const countRule = data.rowMode === "raw" ? "每列按 1 件計算" : "使用「件數」欄加總";
    const warning = (data.warnings || []).join(" ");
    setStatus(`已由${sourceName}載入 ${Number(data.rows).toLocaleString()} 筆資料；${countRule}。${warning ? ` ${warning}` : ""}`);
    await analyze();
  } catch (error) {
    if (!isAbort(error)) setStatus(error.message);
  } finally {
    button.disabled = false;
  }
}

async function analyze() {
  if (!state.token) return;
  const button = $("analyzeButton");
  button.disabled = true;
  try {
    const data = await analysisRequest.json("/analyze", jsonOptions({
      token: state.token,
      pattern: $("pattern").value,
      startDate: $("accidentStartDate").value || undefined,
      endDate: $("accidentEndDate").value || undefined,
      period: $("period").value,
      top: Number($("top").value),
    }));
    state.latest = data;
    renderMetrics(data.metrics);
    renderBasic(data);
    if (!$("panel-map").classList.contains("hidden")) await accidentMap.load();
  } catch (error) {
    if (!isAbort(error)) setStatus(error.message);
  } finally {
    button.disabled = false;
  }
}

function renderMetrics(metrics) {
  $("metrics").innerHTML = metrics.map((item) =>
    `<div class="metric"><small>${esc(item.label)}</small><strong>${Number(item.value).toLocaleString()}</strong></div>`,
  ).join("");
}

function trendTable(items = []) {
  return `<table><thead><tr><th>期間</th><th>數量</th><th>增減</th><th>增減率</th></tr></thead><tbody>${items.map((item) =>
    `<tr><td>${esc(item.value)}</td><td>${Number(item.count).toLocaleString()}</td><td>${item.delta === null ? "—" : Number(item.delta).toLocaleString()}</td><td>${item.rate === null ? "—" : `${(item.rate * 100).toFixed(1)}%`}</td></tr>`,
  ).join("")}</tbody></table>`;
}

function renderBasic(data) {
  const key = $("basicMetric").value;
  const items = data[key] || [];
  $("analysisTitle").textContent = names[key];
  $("analysisTable").innerHTML = items.length
    ? `<table><thead><tr><th>項目</th><th>數量</th></tr></thead><tbody>${items.map((item) => `<tr><td>${esc(item.value)}</td><td>${Number(item.count).toLocaleString()}</td></tr>`).join("")}</tbody></table>`
    : "<p>沒有符合資料</p>";
  chart.draw(items, names[key]);
  $("trendTable").innerHTML = trendTable(data.trend);
  $("narrative").textContent = data.narrative || "";
}

function showAnalysisPanel(kind) {
  document.querySelectorAll(".analysis-panel").forEach((item) => {
    item.classList.toggle("hidden", item.id !== `panel-${kind}`);
  });
  document.querySelectorAll(".analysis-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.analysis === kind);
  });
  if (kind === "chart" && state.latest) renderBasic(state.latest);
  if (kind === "map") setTimeout(async () => {
    accidentMap.invalidate();
    await accidentMap.load();
  }, 60);
}

function showView(id) {
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("hidden", view.id !== id));
  document.querySelectorAll(".nav-button[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === id);
  });
}

function setMajorStatus(message) {
  $("majorStatus").textContent = message;
}

function renderMajorSources(sources = []) {
  $("majorSources").innerHTML = sources.length
    ? `<table><thead><tr><th>來源檔案</th><th>狀態</th><th>工作表</th><th>資料列</th><th>警告</th></tr></thead><tbody>${sources.map((source) =>
      `<tr><td>${esc(source.fileName)}</td><td>${source.status === "loaded" ? "成功" : "失敗"}</td><td>${esc(source.sheetName || "—")}</td><td>${Number(source.rows || 0).toLocaleString()}</td><td>${esc((source.warnings || []).join(" ") || "—")}</td></tr>`,
    ).join("")}</tbody></table>`
    : "";
}

function majorOptions() {
  return {
    token: state.majorToken,
    startDate: $("majorStartDate").value || undefined,
    endDate: $("majorEndDate").value || undefined,
    period: $("majorPeriod").value,
    top: Number($("majorTop").value),
  };
}

function selectedMajorCategory(data = state.majorLatest) {
  const group = $("majorGroup").value;
  return (data?.[group] || []).find((item) => item.key === $("majorCategory").value) || null;
}

function syncMajorCategories() {
  const categories = state.majorLatest?.[$("majorGroup").value] || [];
  const select = $("majorCategory");
  const prior = select.value;
  select.innerHTML = categories.map((item) =>
    `<option value="${esc(item.key)}">${esc(item.label)}${item.available ? "" : "（缺少來源）"}</option>`,
  ).join("");
  select.value = categories.some((item) => item.key === prior) ? prior : (categories[0]?.key || "");
}

function majorMetricCards(metrics) {
  const items = [
    ["期間內件數", metrics.periodCount], ["期間內資料列", metrics.periodRows],
    ["可核對重大違規", metrics.majorTotal], ["行人路權", metrics.pedestrianTotal],
  ];
  $("majorMetrics").innerHTML = items.map(([label, value]) =>
    `<div class="metric"><small>${esc(label)}</small><strong>${Number(value).toLocaleString()}</strong></div>`,
  ).join("");
}

function renderMajorAnalysis() {
  const data = state.majorLatest;
  if (!data) return;
  syncMajorCategories();
  majorMetricCards(data.metrics);
  $("majorRule").textContent = data.rule;
  const group = $("majorGroup").value;
  const categories = data[group] || [];
  $("majorCategories").innerHTML = `<table><thead><tr><th>類別</th><th>資料狀態</th><th>件數</th><th>資料列</th><th>分類依據</th></tr></thead><tbody>${categories.map((item) =>
    `<tr><td>${esc(item.label)}</td><td>${item.available ? "可核對" : "缺少來源"}</td><td>${item.available ? Number(item.count).toLocaleString() : "—"}</td><td>${item.available ? Number(item.rowCount).toLocaleString() : "—"}</td><td>${esc(item.basis)}</td></tr>`,
  ).join("")}</tbody></table>`;
  const category = selectedMajorCategory(data);
  if (!category) return;
  const metric = $("majorMetric").value;
  const metricNames = { road: "違規路段", district: "行政區", hour: "違規時段" };
  const ranking = category[metric] || [];
  $("majorRankingTitle").textContent = `${category.label}：${metricNames[metric]}排行`;
  $("majorRankingTable").innerHTML = ranking.length
    ? `<table><thead><tr><th>項目</th><th>件數</th></tr></thead><tbody>${ranking.map((item) => `<tr><td>${esc(item.value)}</td><td>${Number(item.count).toLocaleString()}</td></tr>`).join("")}</tbody></table>`
    : "<p>沒有可排行資料</p>";
  majorChart.draw(ranking, `${category.label}：${metricNames[metric]}`);
  $("majorTrendTitle").textContent = `${category.label}：${$("majorPeriod").value === "quarter" ? "季" : "月"}趨勢`;
  $("majorTrendTable").innerHTML = trendTable(category.trend);
}

async function loadMajorData() {
  const button = $("majorLoadButton");
  button.disabled = true;
  try {
    setMajorStatus("正在載入並標準化多份 Excel…");
    const data = await majorLoadRequest.json("/major-violation/load", { method: "POST", body: majorUploadForm() });
    state.majorToken = data.token;
    renderMajorSources(data.sources);
    $("majorStartDate").value = data.dateRange?.start || "";
    $("majorEndDate").value = data.dateRange?.end || "";
    const warning = (data.warnings || []).join(" ");
    setMajorStatus(`已載入 ${Number(data.rows).toLocaleString()} 列、${Number(data.totalCount).toLocaleString()} 件，來源 ${data.sources.length} 份。${warning ? ` ${warning}` : ""}`);
    await analyzeMajor();
  } catch (error) {
    if (!isAbort(error)) setMajorStatus(error.message);
  } finally {
    button.disabled = false;
  }
}

async function analyzeMajor() {
  if (!state.majorToken) return;
  const button = $("majorAnalyzeButton");
  button.disabled = true;
  try {
    const data = await majorAnalysisRequest.json("/major-violation/analyze", jsonOptions(majorOptions()));
    state.majorLatest = data;
    renderMajorAnalysis();
  } catch (error) {
    if (!isAbort(error)) setMajorStatus(error.message);
  } finally {
    button.disabled = false;
  }
}

async function clearMajorData() {
  majorLoadRequest.abort();
  majorAnalysisRequest.abort();
  if (state.majorToken) {
    try { await fetch("/clear", jsonOptions({ token: state.majorToken })); } catch (_) { /* local reset */ }
  }
  state.majorToken = "";
  state.majorLatest = null;
  $("majorFileInput").value = "";
  $("majorStartDate").value = "";
  $("majorEndDate").value = "";
  $("majorSources").innerHTML = "";
  $("majorMetrics").innerHTML = "";
  $("majorRule").textContent = "";
  $("majorCategories").innerHTML = "<p>尚未載入資料</p>";
  $("majorRankingTable").innerHTML = "<p>尚未載入資料</p>";
  $("majorTrendTable").innerHTML = "<p>尚未載入資料</p>";
  $("majorCategory").innerHTML = "";
  majorChart.clear();
  setMajorStatus("已清除重大違規資料。");
}

function showMajorPanel(kind) {
  document.querySelectorAll(".major-panel").forEach((item) => {
    item.classList.toggle("hidden", item.id !== `major-panel-${kind}`);
  });
  document.querySelectorAll("[data-major-panel]").forEach((button) => {
    button.classList.toggle("active", button.dataset.majorPanel === kind);
  });
  if (kind === "ranking" && state.majorLatest) renderMajorAnalysis();
}

function renderModuleNav() {
  const nav = $("moduleNav");
  if (!nav) return;
  nav.innerHTML = (window.TRAFFIC_ANALYZER_MODULES || []).map((module) =>
    `<button class="nav-button${module.view === "basicView" ? " active" : ""}" data-module="${esc(module.id)}" data-view="${esc(module.view)}">${esc(module.label)}</button>`,
  ).join("");
  nav.querySelectorAll(".nav-button[data-view]").forEach((button) => {
    button.onclick = () => showView(button.dataset.view);
  });
}

async function clearData() {
  loadRequest.abort();
  analysisRequest.abort();
  slides.abort();
  if (state.token) {
    try {
      await fetch("/clear", jsonOptions({ token: state.token }));
    } catch (_) {
      // Local reset remains available even if the server session already expired.
    }
  }
  state.token = "";
  state.latest = null;
  $("fileInput").value = "";
  setStatus("已清除資料，請重新載入 Excel。");
  $("slideStatus").textContent = "";
  $("metrics").innerHTML = "";
  $("analysisTable").innerHTML = "<p>尚未載入資料</p>";
  $("trendTable").innerHTML = "<p>尚未載入資料</p>";
  $("narrative").textContent = "";
  $("pattern").value = "all";
  $("accidentStartDate").value = "";
  $("accidentEndDate").value = "";
  $("basicMetric").value = "road";
  $("period").value = "month";
  $("top").value = "20";
  $("slidePeriod").value = "115年1月1日至8月31日";
  chart.clear();
  accidentMap.clear();
  showAnalysisPanel("table");
}

renderModuleNav();
$("loadButton").onclick = loadData;
$("clearButton").onclick = clearData;
$("generateModernSlidesButton").onclick = () => slides.generate("modern", $("generateModernSlidesButton"));
$("generateTraditionalSlidesButton").onclick = () => slides.generate("traditional", $("generateTraditionalSlidesButton"));
$("analyzeButton").onclick = analyze;
$("pattern").onchange = analyze;
$("accidentStartDate").onchange = analyze;
$("accidentEndDate").onchange = analyze;
$("period").onchange = analyze;
$("top").onchange = analyze;
$("basicMetric").onchange = () => state.latest && renderBasic(state.latest);
document.querySelectorAll(".analysis-tab").forEach((button) => {
  button.onclick = () => showAnalysisPanel(button.dataset.analysis);
});
$("menuButton").onclick = () => document.querySelector(".sidebar").classList.toggle("open");
$("copyButton").onclick = () => navigator.clipboard?.writeText($("narrative").textContent)
  .then(() => setStatus("摘要已複製。"));
$("majorLoadButton").onclick = loadMajorData;
$("majorClearButton").onclick = clearMajorData;
$("majorAnalyzeButton").onclick = analyzeMajor;
$("majorGroup").onchange = () => {
  if (!state.majorLatest) return;
  renderMajorAnalysis();
};
$("majorCategory").onchange = () => {
  if (!state.majorLatest) return;
  renderMajorAnalysis();
};
$("majorMetric").onchange = () => state.majorLatest && renderMajorAnalysis();
$("majorPeriod").onchange = analyzeMajor;
$("majorTop").onchange = analyzeMajor;
document.querySelectorAll("[data-major-panel]").forEach((button) => {
  button.onclick = () => showMajorPanel(button.dataset.majorPanel);
});
