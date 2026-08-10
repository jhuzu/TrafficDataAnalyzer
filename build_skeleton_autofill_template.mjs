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
  kind: "textbox,table",
  include: "id,slide,name,text,textPreview,bbox,rows,cols",
  maxChars: 240000,
});
const objects = (snapshot.ndjson || "").split("\n").filter(Boolean).map(line => JSON.parse(line));
const resolve = (kind, slideNumber, name) => {
  const hit = objects.find(item => item.kind === kind && item.slide === slideNumber && item.name === name);
  return hit ? presentation.resolve(hit.id) : null;
};
const setText = (slide, name, value) => {
  const box = resolve("textbox", slide, name);
  if (box) box.text = value;
};
const setTable = (slide, name, matrix) => {
  const target = resolve("table", slide, name);
  if (!target) return;
  for (let r = 0; r < matrix.length; r += 1) {
    for (let c = 0; c < matrix[r].length; c += 1) target.cells.set(r, c, matrix[r][c] ?? "");
  }
};

// Only edit native text boxes and tables. Raster images and map placeholders remain untouched.
setText(1, "TextBox 13", "{{PERIOD}}");

setText(2, "TextBox 13", "{{PERIOD_SHORT}}");
setText(2, "TextBox 17", "A1+A2事故總件數\n{{TOTAL}}件");
setText(2, "TextBox 18", "同期變化：{{TD}}件（{{TR}}）");
setText(2, "TextBox 20", "{{A1}}件");
setText(2, "TextBox 21", "同期變化：{{A1D}}件（{{A1R}}）");
setText(2, "TextBox 23", "{{A2}}件");
setText(2, "TextBox 24", "同期變化：{{A2D}}件（{{A2R}}）");
setText(2, "TextBox 27", "整體狀況：{{SUMMARY}}");
setText(2, "TextBox 29", "核心防制重點：{{FOCUS}}");
setText(2, "TextBox 31", "防制方向：{{DIRECTION}}");

const rankingTable = (label, countLabel) => [
  ["排名", label, countLabel],
  ...Array.from({ length: 10 }, (_, i) => [String(i + 1), `{{${label === "路段名稱" ? "R" : "I"}${i + 1}}}`, `{{${label === "路段名稱" ? "RN" : "IN"}${i + 1}}}`]),
];
setTable(3, "Table 15", rankingTable("路段名稱", "發生件數"));
setTable(4, "Table 15", rankingTable("路口名稱", "件數"));

setText(5, "TextBox 37", "{{T1}}");
setText(5, "TextBox 38", "{{T2}}");
setText(5, "TextBox 39", "{{T3}}");
setText(5, "TextBox 40", "{{T4}}");
setText(5, "TextBox 41", "{{T5}}");
setText(5, "TextBox 42", "{{T6}}");
setText(5, "TextBox 43", "{{T7}}");
setText(5, "TextBox 62", "{{T1N}}（{{T1R}}）");
setText(5, "TextBox 63", "{{T2N}}（{{T2R}}）");
setText(5, "TextBox 64", "{{T3N}}（{{T3R}}）");
setTable(5, "Table 33", [
  ["排名", "肇事原因", "件數（占比）"],
  ...Array.from({ length: 6 }, (_, i) => [String(i + 1), `{{C${i + 1}}}`, `{{CN${i + 1}}}（{{CR${i + 1}}}）`]),
]);

setText(6, "TextBox 47", "{{V1N}}件");
setText(6, "TextBox 48", "占比{{V1R}}");
setText(6, "TextBox 51", "{{V2N}}件");
setText(6, "TextBox 52", "占比{{V2R}}");
setTable(6, "Table 17", [
  ["年齡區間", "件數", "占比", "風險等級"],
  ...Array.from({ length: 5 }, (_, i) => [`{{AGE${i + 1}}}`, `{{AGEN${i + 1}}}件`, `{{AGER${i + 1}}}`, `{{AGERISK${i + 1}}}`]),
]);
setTable(6, "Table 21", [["其他車種", "慢車(含微電車)", "小貨車", "大貨車/客車"], ["{{V3N}}", "{{V4N}}", "{{V5N}}", "{{V6N}}"]]);

setTable(7, "Table 11", [
  ["編號", "發生時間", "發生地點", "肇因研判", "車種別", "死亡類別 / 備註"],
  ...Array.from({ length: 7 }, (_, i) => {
    const n = i + 1;
    return [String(n), `{{A1T${n}}}`, `{{A1L${n}}}`, `{{A1C${n}}}`, `{{A1V${n}}}`, `{{A1F${n}}} / {{A1N${n}}}`];
  }),
]);
setText(7, "TextBox 12", "A1案件防制結論：{{A1SUMMARY}}");

setText(8, "TextBox 20", "專案日程：{{EPERIOD}}");
setText(8, "TextBox 27", "熱點編排：{{HOTSPOT_PLAN}}");
setText(8, "TextBox 29", "A1路段重點執法：{{A1_PLAN}}");
setText(8, "TextBox 30", "嘉獎核予標準：\n專案期間每執行超速取締勤務達{{AHOURS}}小時，且總取締件數不低於{{ACOUNT}}件者，核予嘉獎一次。");

const notes = `[AutoFill]\n本簡報以骨架模板為版型；只替換 {{TOKEN}} 欄位。\n圖片、地圖與圖資框保留人工更新，不由自動填值程式修改。\n數字以 Excel 件數欄彙總；長文字請先縮短後填入，以避免版面溢出。\n[/AutoFill]`;
for (const slide of presentation.slides.items || []) {
  slide.speakerNotes.textFrame.setText(notes);
  slide.speakerNotes.setVisible(true);
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const out = await PresentationFile.exportPptx(presentation);
await out.save(outputPath);
console.log(JSON.stringify({ output: outputPath, slides: presentation.slides.items?.length || 0 }));
