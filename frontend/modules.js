// Central registry for top-level analysis modules.
// Add future data-analysis modules here instead of hard-coding sidebar buttons.
window.TRAFFIC_ANALYZER_MODULES = [
  { id: "accident", label: "事故資料分析", view: "basicView" },
  { id: "major-violation", label: "重大違規分析", view: "majorViolationView" },
];
