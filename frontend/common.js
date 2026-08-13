export const state = {
  token: "", latest: null, majorToken: "", majorLatest: null,
  performanceToken: "", majorPerformance: null, majorStatisticKeys: [],
};

export const $ = (id) => document.getElementById(id);

export const esc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#39;");

export function trendTable(items = []) {
  return `<table><thead><tr><th>期間</th><th>數量</th><th>增減</th><th>增減率</th></tr></thead><tbody>${items.map((item) =>
    `<tr><td>${esc(item.value)}</td><td>${Number(item.count).toLocaleString()}</td><td>${item.delta === null ? "—" : Number(item.delta).toLocaleString()}</td><td>${item.rate === null ? "—" : `${(item.rate * 100).toFixed(1)}%`}</td></tr>`,
  ).join("")}</tbody></table>`;
}
