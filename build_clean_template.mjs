import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const args = {};
for (let i = 2; i < process.argv.length; i += 1) {
  if (process.argv[i].startsWith("--")) args[process.argv[i].slice(2)] = process.argv[i + 1] ?? "";
}
const sourcePath = path.resolve(args.source || "");
const outputPath = path.resolve(args.output || "");
if (!sourcePath || !outputPath) throw new Error("需要 --source 與 --output。");

const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const snapshot = await presentation.inspect({
  kind: "textbox,shape,table,chart",
  include: "id,slide,name,text,textPreview,bbox,rows,cols,chartType,title",
  maxChars: 200000,
});
const objects = (snapshot.ndjson || "").split("\n").filter(Boolean).map(line => JSON.parse(line));
const find = (kind, slide, name) => {
  const hit = objects.find(item => item.kind === kind && item.slide === slide && item.name === name);
  return hit ? presentation.resolve(hit.id) : null;
};
const text = (slide, name, value) => {
  const box = find("textbox", slide, name);
  if (box) box.text = value;
};
const table = (slide, name, values) => {
  const target = find("table", slide, name);
  if (!target) return;
  for (let r = 0; r < values.length; r += 1) {
    for (let c = 0; c < values[r].length; c += 1) target.cells.set(r, c, values[r][c] ?? "");
  }
};
const chartByTitle = (slide, title, chartType) => {
  const hit = objects.find(item => item.kind === "chart" && item.slide === slide && (title === undefined || item.title === title) && (chartType === undefined || item.chartType === chartType));
  return hit ? presentation.resolve(hit.id) : null;
};
const blankSeries = (chart, categories, name = "{{count_label}}") => {
  if (!chart?.series?.items?.length) return;
  const target = chart.series.getItemAt(0);
  target.name = name;
  target.categories = categories;
  target.values = categories.map(() => 0);
};

// Slide 1: overall overview
text(1, "矩形 14", "{{PERIOD}}\nA1+A2：{{TOTAL}}件（{{TD}}）\nA1：{{A1}}件（{{A1D}}）\nA2：{{A2}}件（{{A2D}}）\n\n{{SUMMARY}}");
text(1, "矩形 2", "{{A1}}");
const overall = chartByTitle(1, "115年及114年交通事故分析");
if (overall) {
  overall.title = "{{OVERVIEW_CHART}}";
  if (overall.series?.items?.length >= 2) {
    overall.series.getItemAt(0).name = "{{PREV}}";
    overall.series.getItemAt(0).values = [0, 0, 0];
    overall.series.getItemAt(1).name = "{{CURRENT}}";
    overall.series.getItemAt(1).values = [0, 0, 0];
  }
}

// Slide 2: road ranking and map placeholder
text(2, "矩形 38", "路段：{{R1}} {{N1}}件；{{R2}} {{N2}}件；{{R3}} {{N3}}件。共{{RCOUNT}}處。");
for (const [name, i] of [["圖說文字: 折線 37", 1], ["圖說文字: 折線 31", 2], ["圖說文字: 折線 32", 3], ["圖說文字: 折線 33", 4], ["圖說文字: 折線 34", 5], ["圖說文字: 折線 35", 6], ["圖說文字: 折線 36", 7], ["圖說文字: 折線 39", 8], ["圖說文字: 折線 42", 9]]) text(2, name, `{{R${i}}}`);
table(2, "表格 7", [["排名", ...Array.from({ length: 10 }, (_, i) => `{{R${i + 1}}}`)], ["件數", ...Array.from({ length: 10 }, (_, i) => `{{N${i + 1}}}`)], ["排名", ...Array.from({ length: 10 }, (_, i) => String(i + 1))]]);
const roads = chartByTitle(2, "十大易肇事路段");
if (roads) { roads.title = "{{ROAD_CHART}}"; blankSeries(roads, Array.from({ length: 10 }, (_, i) => `{{R${i + 1}}}`)); }

// Slide 3: intersection ranking and map placeholder
text(3, "矩形 24", "路口：{{I1}} {{IN1}}件；{{I2}} {{IN2}}件；{{I3}} {{IN3}}件。");
for (const [name, i] of [["圖說文字: 折線 37", 1], ["圖說文字: 折線 39", 2], ["圖說文字: 折線 40", 3], ["圖說文字: 折線 41", 4], ["圖說文字: 折線 42", 5], ["圖說文字: 折線 44", 6], ["圖說文字: 折線 36", 7], ["圖說文字: 折線 7", 8], ["圖說文字: 折線 8", 9], ["圖說文字: 折線 9", 10]]) text(3, name, `{{I${i}}}`);
table(3, "表格 23", [["排名", ...Array.from({ length: 10 }, (_, i) => `{{I${i + 1}}}`)], ["件數", ...Array.from({ length: 10 }, (_, i) => `{{IN${i + 1}}}`)], ["排名", ...Array.from({ length: 10 }, (_, i) => String(i + 1))]]);
const intersections = chartByTitle(3, "十大易肇事路口");
if (intersections) { intersections.title = "{{INTERSECTION_CHART}}"; for (let i = 0; i < intersections.series.items.length; i += 1) { const s = intersections.series.getItemAt(i); s.name = `{{I${i + 1}}}`; s.values = [0]; } }

// Slide 4: time and cause
text(4, "矩形 27", "肇因：{{C1}} {{CN1}}件（{{CP1}}）；{{C2}} {{CN2}}件（{{CP2}}）；{{C3}} {{CN3}}件（{{CP3}}）。");
text(4, "矩形 21", "時段：{{T1}} {{TN1}}件（{{TP1}}）；{{T2}} {{TN2}}件（{{TP2}}）；{{T3}} {{TN3}}件（{{TP3}}）。");
table(4, "表格 26", [["時間", ...Array.from({ length: 12 }, (_, i) => `{{T${i + 1}}}`)], ["件數", ...Array.from({ length: 12 }, (_, i) => `{{TN${i + 1}}}`)]]);
table(4, "表格 29", [["排名", ...Array.from({ length: 12 }, (_, i) => String(i + 1))], ["肇因", ...Array.from({ length: 12 }, (_, i) => `{{C${i + 1}}}`)], ["件數", ...Array.from({ length: 12 }, (_, i) => `{{CN${i + 1}}}`)]]);

// Slide 5: age and vehicle
text(5, "矩形 19", "年齡：{{AAG1}} {{AN1}}件（{{AP1}}）；{{AAG2}} {{AN2}}件（{{AP2}}）；{{AAG3}} {{AN3}}件（{{AP3}}）。");
text(5, "矩形 26", "車種：{{V1}} {{VN1}}件（{{VP1}}）；{{V2}} {{VN2}}件（{{VP2}}）；{{V3}} {{VN3}}件（{{VP3}}）。");
for (const [name, i] of [["文字方塊 1", 1], ["文字方塊 2", 2], ["文字方塊 3", 3], ["文字方塊 4", 4], ["文字方塊 13", 5], ["文字方塊 15", 6], ["文字方塊 16", 7]]) text(5, name, `{{AN${i}}}`);
table(5, "表格 18", [["年齡", ...Array.from({ length: 7 }, (_, i) => `{{AAG${i + 1}}}`)], ["件數", ...Array.from({ length: 7 }, (_, i) => `{{AN${i + 1}}}`)]]);
table(5, "表格 25", [["車種", ...Array.from({ length: 7 }, (_, i) => `{{V${i + 1}}}`)], ["件數", ...Array.from({ length: 7 }, (_, i) => `{{VN${i + 1}}}`)]]);
const ageChart = chartByTitle(5, "件數", "funnel");
if (ageChart) ageChart.title = "{{AGE_CHART}}";
// artifact-tool cannot export the source funnel chart reliably; add a native bar
// replacement in the same frame so the clean template keeps an editable chart.
const slide5 = presentation.slides.items?.[4];
if (slide5?.charts) {
  slide5.charts.add("bar", {
    position: { left: 13.47, top: 228.5, width: 419.63, height: 257.25 },
    title: "{{AGE_CHART}}",
    categories: Array.from({ length: 7 }, (_, i) => `{{AAG${i + 1}}}`),
    series: [{ name: "{{AGE_COUNT}}", values: Array(7).fill(0) }],
    barOptions: { direction: "bar", grouping: "clustered", varyColors: true },
    hasLegend: false,
  });
}

// Slide 6: A1 map and detail table
text(6, "矩形: 圓角 31", "{{a1_map_title}}");
table(6, "表格 12", [["板橋分局轄內{{YEAR}}年度A1事故明細", "", "", "", "", "", ""], ["編號", "時間", "地點", "肇因", "車種", "死亡", "備註"], ...Array.from({ length: 7 }, (_, i) => [String(i + 1), `{{A${i + 1}T}}`, `{{A${i + 1}L}}`, `{{A${i + 1}C}}`, `{{A${i + 1}V}}`, `{{A${i + 1}F}}`, `{{A${i + 1}N}}`])]);
for (const [name, i] of [["語音泡泡: 矩形 23", 6], ["語音泡泡: 矩形 24", 2], ["語音泡泡: 矩形 25", 4], ["語音泡泡: 矩形 26", 3], ["語音泡泡: 矩形 27", 1], ["語音泡泡: 矩形 28", 7], ["語音泡泡: 矩形 29", 5]]) text(6, name, `{{A${i}L}}`);

// Slide 7: enforcement plan
text(7, "文字方塊 3", "八、交通大執法專案\n一、日程：{{EPERIOD}}\n\n二、勤務方式：\n　（一）各所、隊於{{HOTSPOT}}編排勤務，加強取締超速。\n\n　（二）加強取締A1事故路段：{{FOCUS1}}、{{FOCUS2}}。\n\n四、獎勵規定：每執行超速取締勤務達{{AHOURS}}小時，且總取締件數不低於{{ACOUNT}}件者，核予嘉獎一次，以嘉獎{{ALIMIT}}次為上限。");
text(7, "文字方塊 11", "{{FOCUS1}}");
text(7, "文字方塊 13", "{{FOCUS2}}");

const notes = `[AutoFill]\nThis deck is a clean data-entry template. Replace short {{tokens}} only.\nUse Excel 件數 as the aggregation measure.\nField groups: A/A1-A2 KPI; R/N road name/count; I/IN intersection name/count; T/TN time/count; C/CN cause/count; AAG/AN age label/count; V/VN vehicle label/count; A1T/A1L/A1C/A1V/A1F/A1N fatal detail; E/F enforcement.\nLong labels must be shortened before insertion; do not change frame geometry.\n[/AutoFill]`;
for (const slide of presentation.slides.items || []) { slide.speakerNotes.textFrame.setText(notes); slide.speakerNotes.setVisible(true); }

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const out = await PresentationFile.exportPptx(presentation);
await out.save(outputPath);
console.log(JSON.stringify({ output: outputPath, slides: presentation.slides.items?.length || 0 }));
