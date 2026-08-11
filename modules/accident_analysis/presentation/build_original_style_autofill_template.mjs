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
  kind: "textbox,shape,image,table,chart",
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
const remove = (kind, slide, name) => {
  const target = find(kind, slide, name);
  if (target?.delete) target.delete();
};
const addMapPlaceholder = (slideNumber, imageName, label) => {
  const imageRecord = objects.find(item => item.kind === "image" && item.slide === slideNumber && item.name === imageName);
  if (!imageRecord?.bbox) return;
  remove("image", slideNumber, imageName);
  const [left, top, width, height] = imageRecord.bbox;
  const slide = presentation.slides.items?.[slideNumber - 1];
  if (!slide) return;
  const placeholder = slide.shapes.add({
    geometry: "rect",
    name: `人工地圖預留區-${slideNumber}`,
    position: { left, top, width, height },
    fill: "#F4F6F8",
    line: { style: "dash", fill: "#AAB4C0", width: 1.5 },
  });
  placeholder.text = `${label}\n（請由人工置入地圖圖片）`;
  placeholder.text.style = { fontSize: 20, bold: true, color: "#7A8795", alignment: "center", verticalAlignment: "middle" };
};
const addChartPlaceholder = (slideNumber, chartName, token) => {
  const chartRecord = objects.find(item => item.kind === "chart" && item.slide === slideNumber && item.name === chartName);
  if (!chartRecord?.bbox) return;
  remove("chart", slideNumber, chartName);
  const [left, top, width, height] = chartRecord.bbox;
  const slide = presentation.slides.items?.[slideNumber - 1];
  if (!slide) return;
  const placeholder = slide.shapes.add({
    geometry: "rect",
    name: `程式圖表預留區-${slideNumber}-${chartName}`,
    position: { left, top, width, height },
    fill: "#FFFFFF",
    line: { style: "dash", fill: "#8FB4D8", width: 1.5 },
  });
  placeholder.text = token;
  placeholder.text.style = { fontSize: 20, bold: true, color: "#3178B8", alignment: "center", verticalAlignment: "middle" };
};
const table = (slide, name, values) => {
  const target = find("table", slide, name);
  if (!target) return;
  for (let r = 0; r < values.length; r += 1) {
    for (let c = 0; c < values[r].length; c += 1) target.cells.set(r, c, values[r][c] ?? "");
  }
};
// Slide 1: overall overview
text(1, "矩形 14", "{{PERIOD}}\nA1+A2：{{TOTAL}}件（{{TD}}）\nA1：{{A1}}件（{{A1D}}）\nA2：{{A2}}件（{{A2D}}）\n\n{{SUMMARY}}");
const overviewText = find("textbox", 1, "矩形 14");
if (overviewText?.text) overviewText.text.style = { fontSize: 18, bold: true, color: "#0000FF" };
remove("textbox", 1, "矩形 2");
addChartPlaceholder(1, "圖表 26", "{{OVERVIEW_CHART}}");

// Slide 2: road ranking and map placeholder
text(2, "矩形 38", "路段：{{R1}} {{N1}}件；{{R2}} {{N2}}件；{{R3}} {{N3}}件。共{{RCOUNT}}處。");
for (const [name, i] of [["圖說文字: 折線 37", 1], ["圖說文字: 折線 31", 2], ["圖說文字: 折線 32", 3], ["圖說文字: 折線 33", 4], ["圖說文字: 折線 34", 5], ["圖說文字: 折線 35", 6], ["圖說文字: 折線 36", 7], ["圖說文字: 折線 39", 8], ["圖說文字: 折線 42", 9]]) text(2, name, `{{R${i}}}`);
table(2, "表格 7", [["排名", ...Array.from({ length: 10 }, (_, i) => `{{R${i + 1}}}`)], ["件數", ...Array.from({ length: 10 }, (_, i) => `{{N${i + 1}}}`)], ["排名", ...Array.from({ length: 10 }, (_, i) => String(i + 1))]]);
addChartPlaceholder(2, "圖表 19", "{{ROAD_CHART}}");
for (const name of ["圖說文字: 折線 37", "圖說文字: 折線 31", "圖說文字: 折線 32", "圖說文字: 折線 33", "圖說文字: 折線 34", "圖說文字: 折線 35", "圖說文字: 折線 36", "圖說文字: 折線 39", "圖說文字: 折線 42"]) remove("textbox", 2, name);
for (const name of ["橢圓 17", "橢圓 18", "橢圓 20", "橢圓 22", "橢圓 23", "橢圓 24", "橢圓 25", "橢圓 26", "橢圓 27", "橢圓 28", "橢圓 40", "橢圓 41"]) remove("shape", 2, name);
addMapPlaceholder(2, "圖片 8", "易肇事路段地圖");

// Slide 3: intersection ranking and map placeholder
text(3, "矩形 24", "路口：{{I1}} {{IN1}}件；{{I2}} {{IN2}}件；{{I3}} {{IN3}}件。");
for (const [name, i] of [["圖說文字: 折線 37", 1], ["圖說文字: 折線 39", 2], ["圖說文字: 折線 40", 3], ["圖說文字: 折線 41", 4], ["圖說文字: 折線 42", 5], ["圖說文字: 折線 44", 6], ["圖說文字: 折線 36", 7], ["圖說文字: 折線 7", 8], ["圖說文字: 折線 8", 9], ["圖說文字: 折線 9", 10]]) text(3, name, `{{I${i}}}`);
table(3, "表格 23", [["排名", ...Array.from({ length: 10 }, (_, i) => `{{I${i + 1}}}`)], ["件數", ...Array.from({ length: 10 }, (_, i) => `{{IN${i + 1}}}`)], ["排名", ...Array.from({ length: 10 }, (_, i) => String(i + 1))]]);
addChartPlaceholder(3, "圖表 20", "{{INTERSECTION_CHART}}");
for (const name of ["圖說文字: 折線 37", "圖說文字: 折線 39", "圖說文字: 折線 40", "圖說文字: 折線 41", "圖說文字: 折線 42", "圖說文字: 折線 44", "圖說文字: 折線 36", "圖說文字: 折線 7", "圖說文字: 折線 8", "圖說文字: 折線 9", "星形: 八角 5", "星形: 八角 19", "星形: 八角 25", "星形: 八角 26", "星形: 八角 27", "星形: 八角 30", "星形: 八角 31", "星形: 八角 32", "星形: 八角 33", "星形: 八角 34"]) remove("textbox", 3, name);
addMapPlaceholder(3, "圖片 2", "易肇事路口地圖");

// Slide 4: time and cause
text(4, "矩形 21", "肇因：{{C1}} {{CN1}}件（{{CP1}}）；{{C2}} {{CN2}}件（{{CP2}}）；{{C3}} {{CN3}}件（{{CP3}}）。");
text(4, "矩形 27", "時段：{{T1}} {{TN1}}件（{{TP1}}）；{{T2}} {{TN2}}件（{{TP2}}）；{{T3}} {{TN3}}件（{{TP3}}）。");
table(4, "表格 26", [["時間", ...Array.from({ length: 12 }, (_, i) => `{{T${i + 1}}}`)], ["件數", ...Array.from({ length: 12 }, (_, i) => `{{TN${i + 1}}}`)]]);
table(4, "表格 29", [["排名", ...Array.from({ length: 12 }, (_, i) => String(i + 1))], ["肇因", ...Array.from({ length: 12 }, (_, i) => `{{C${i + 1}}}`)], ["件數", ...Array.from({ length: 12 }, (_, i) => `{{CN${i + 1}}}`)]]);
addChartPlaceholder(4, "圖表 28", "{{CAUSE_CHART}}");
addChartPlaceholder(4, "圖表 25", "{{TIME_CHART}}");

// Slide 5: age and vehicle
text(5, "矩形 19", "年齡：{{AAG1}} {{AN1}}件（{{AP1}}）；{{AAG2}} {{AN2}}件（{{AP2}}）；{{AAG3}} {{AN3}}件（{{AP3}}）。");
text(5, "矩形 26", "車種：{{V1}} {{VN1}}件（{{VP1}}）；{{V2}} {{VN2}}件（{{VP2}}）；{{V3}} {{VN3}}件（{{VP3}}）。");
for (const name of ["文字方塊 1", "文字方塊 2", "文字方塊 3", "文字方塊 4", "文字方塊 13", "文字方塊 15", "文字方塊 16"]) remove("textbox", 5, name);
table(5, "表格 18", [["年齡", ...Array.from({ length: 7 }, (_, i) => `{{AAG${i + 1}}}`)], ["件數", ...Array.from({ length: 7 }, (_, i) => `{{AN${i + 1}}}`)]]);
table(5, "表格 25", [["車種", ...Array.from({ length: 7 }, (_, i) => `{{V${i + 1}}}`)], ["件數", ...Array.from({ length: 7 }, (_, i) => `{{VN${i + 1}}}`)]]);
addChartPlaceholder(5, "圖表 17", "{{AGE_CHART}}");
addChartPlaceholder(5, "圖表 24", "{{VEHICLE_CHART}}");

// Slide 6: A1 map and detail table
remove("textbox", 6, "矩形: 圓角 31");
table(6, "表格 12", [["板橋分局轄內{{YEAR}}年度A1事故明細", "", "", "", "", "", ""], ["編號", "時間", "地點", "肇因", "車種", "死亡", "備註"], ...Array.from({ length: 7 }, (_, i) => [String(i + 1), `{{A${i + 1}T}}`, `{{A${i + 1}L}}`, `{{A${i + 1}C}}`, `{{A${i + 1}V}}`, `{{A${i + 1}F}}`, `{{A${i + 1}N}}`])]);
for (const name of ["語音泡泡: 矩形 23", "語音泡泡: 矩形 24", "語音泡泡: 矩形 25", "語音泡泡: 矩形 26", "語音泡泡: 矩形 27", "語音泡泡: 矩形 28", "語音泡泡: 矩形 29"]) remove("textbox", 6, name);
for (const name of ["橢圓 11", "橢圓 13", "橢圓 16", "橢圓 17", "橢圓 18", "橢圓 21", "橢圓 22"]) remove("shape", 6, name);
for (const name of ["圖片 38", "圖片 39", "圖片 1", "圖片 2"]) remove("image", 6, name);
addMapPlaceholder(6, "圖片 20", "A1事故斑點圖");

// Slide 7: enforcement plan
text(7, "文字方塊 3", "八、交通大執法專案\n一、日程：{{EPERIOD}}\n\n二、勤務方式：\n　（一）各所、隊於{{HOTSPOT}}編排勤務，加強取締超速。\n\n　（二）加強取締A1事故路段：{{FOCUS1}}、{{FOCUS2}}。\n\n四、獎勵規定：每執行超速取締勤務達{{AHOURS}}小時，且總取締件數不低於{{ACOUNT}}件者，核予嘉獎一次，以嘉獎{{ALIMIT}}次為上限。");
text(7, "文字方塊 11", "{{FOCUS1}}");
text(7, "文字方塊 13", "{{FOCUS2}}");
for (const name of ["橢圓 7", "橢圓 8", "橢圓 16", "橢圓 17", "橢圓 19", "橢圓 20", "橢圓 23", "橢圓 24", "橢圓 25", "橢圓 27", "橢圓 28", "橢圓 29", "語音泡泡: 圓角矩形 9", "文字方塊 11", "文字方塊 13", "語音泡泡: 圓角矩形 31"]) remove("textbox", 7, name);
for (const name of ["橢圓 6", "矩形 32", "箭號: 向右 33"]) remove("shape", 7, name);
for (const name of ["表格 15", "表格 22", "表格 26", "表格 30", "表格 12"]) remove("table", 7, name);
addMapPlaceholder(7, "圖片 5", "交通大執法勤務地圖");

const notes = `[AutoFill]\nThis deck preserves the original report style and replaces approved fields with {{TOKEN}} values.\nUse Excel 件數 as the aggregation measure.\nField groups: A/A1-A2 KPI; R/N road name/count; I/IN intersection name/count; T/TN time/count; C/CN cause/count; AAG/AN age label/count; V/VN vehicle label/count; A1T/A1L/A1C/A1V/A1F/A1N fatal detail; E/F enforcement.\nCharts are redrawn by the generator from the corresponding token groups. Map frames are manual placeholders and are not filled by the generator.\nLong labels must be shortened before insertion; do not change frame geometry.\n[/AutoFill]`;
for (const slide of presentation.slides.items || []) { slide.speakerNotes.textFrame.setText(notes); slide.speakerNotes.setVisible(true); }

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const out = await PresentationFile.exportPptx(presentation);
await out.save(outputPath);
console.log(JSON.stringify({ output: outputPath, slides: presentation.slides.items?.length || 0 }));
