import { $, esc } from "./common.js";
import { initAccident } from "./accident.js";
import { initMajorViolation } from "./major-violation.js";

function showView(id) {
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("hidden", view.id !== id));
  document.querySelectorAll(".nav-button[data-view]").forEach((button) => button.classList.toggle("active", button.dataset.view === id));
}

function renderModuleNav() {
  const nav = $("moduleNav");
  nav.innerHTML = (window.TRAFFIC_ANALYZER_MODULES || []).map((module) =>
    `<button class="nav-button${module.view === "basicView" ? " active" : ""}" data-view="${esc(module.view)}">${esc(module.label)}</button>`,
  ).join("");
  nav.querySelectorAll(".nav-button").forEach((button) => { button.onclick = () => showView(button.dataset.view); });
}

renderModuleNav();
initAccident();
initMajorViolation();
