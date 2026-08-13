import { LatestRequest, isAbort, jsonOptions } from "./api.js";

export function createAccidentMap({ container, info, unlocated, getToken, getOptions, getDensityEnabled, getDensityThreshold, escapeHtml }) {
  const request = new LatestRequest();
  let map = null;
  let markerLayer = null;
  let densityLayer = null;
  let currentMarkers = [];

  function initialize() {
    if (map || !container) return;
    map = L.map(container, { center: [25.0118, 121.459], zoom: 14, zoomControl: true });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
    }).addTo(map);
    markerLayer = L.layerGroup().addTo(map);
    densityLayer = L.layerGroup().addTo(map);
    map.on("zoomend moveend", renderMarkers);
  }

  function clusteredMarkers() {
    const cells = new Map();
    const cellSize = 28;
    currentMarkers.forEach((marker) => {
      const point = map.project([marker.lat, marker.lng], map.getZoom());
      const key = `${Math.floor(point.x / cellSize)}:${Math.floor(point.y / cellSize)}`;
      const group = cells.get(key) || { count: 0, lats: [], lngs: [], labels: [], sources: [] };
      group.count += Number(marker.count) || 0;
      group.lats.push(marker.lat); group.lngs.push(marker.lng);
      if (!group.labels.includes(marker.label)) group.labels.push(marker.label);
      if (!group.sources.includes(marker.source)) group.sources.push(marker.source);
      cells.set(key, group);
    });
    return Array.from(cells.values()).map((group) => ({
      lat: group.lats.reduce((sum, value) => sum + value, 0) / group.lats.length,
      lng: group.lngs.reduce((sum, value) => sum + value, 0) / group.lngs.length,
      count: group.count, label: group.labels.slice(0, 3).join("、"), source: group.sources.join("、"),
    }));
  }

  function renderMarkers() {
    if (!map) return;
    markerLayer.clearLayers(); densityLayer.clearLayers();
    const markers = clusteredMarkers();
    const maximum = Math.max(...markers.map((marker) => Number(marker.count) || 0), 1);
    const threshold = getDensityThreshold?.() || 5;
    markers.forEach((marker) => {
      const radius = Math.max(5, Math.min(14, Math.sqrt(marker.count) * 1.5));
      const point = [marker.lat, marker.lng];
      const popup = `<div class="marker-popup"><strong>${escapeHtml(marker.label)}</strong><br>事故件數：<span class="count">${Number(marker.count).toLocaleString()}</span><br><small>定位：${escapeHtml(marker.source || "Excel X/Y")}</small></div>`;
      const intensity = (Number(marker.count) || 0) / maximum;
      const color = Number(marker.count) > threshold ? "#dc2626" : "#2563eb";
      if (getDensityEnabled?.()) {
        L.circle(point, { radius: 12 + intensity * 35, color, weight: 1, fillColor: color, fillOpacity: 0.32 + intensity * 0.28 }).bindPopup(popup).addTo(densityLayer);
      } else {
        L.circleMarker(point, { radius, fillColor: color, color: "#fff", weight: 1.5, fillOpacity: 0.82 }).bindPopup(popup).addTo(markerLayer);
      }
    });
  }

  async function load() {
    if (!getToken() || !container || container.clientWidth === 0 || container.clientHeight === 0) return;
    initialize();
    try {
      const data = await request.json(
        "/map-points",
        jsonOptions({ token: getToken(), ...getOptions() }),
      );
      const repairInfo = data.repaired
        ? `；依路段／路口修復 ${Number(data.repaired).toLocaleString()} 筆`
        : "";
      const referenceInfo = data.referenced
        ? `；離線道路對照 ${Number(data.referenced).toLocaleString()} 筆`
        : "";
      const unlocatedInfo = data.unlocated
        ? `；無可用參照 ${Number(data.unlocated).toLocaleString()} 筆未繪製`
        : "";
      const suspiciousInfo = data.suspicious
        ? `；偵測 ${Number(data.suspicious).toLocaleString()} 筆路名不一致座標`
        : "";
      info.textContent = `${Number(data.total).toLocaleString()} 筆座標（${data.coordField}）${referenceInfo}${suspiciousInfo}${repairInfo}${unlocatedInfo}`;
      if (unlocated) {
        const records = data.unlocatedRecords || [];
        unlocated.classList.toggle("hidden", !records.length);
        unlocated.innerHTML = records.length
          ? `<small>以下座標無可用路段／路口參照，請承辦人以「受理案號」進行人工確認：</small><ul>${records.map((record) => `<li>受理案號：${escapeHtml(record.caseNumber)}｜肇事路段：${escapeHtml(record.road)}｜路口：${escapeHtml(record.intersection)}</li>`).join("")}</ul>`
          : "";
      }
      currentMarkers = data.markers;
      if (!data.markers.length) {
        info.textContent = "沒有可用的座標資料";
        return;
      }
      renderMarkers();
      const bounds = L.latLngBounds(data.markers.map((point) => [point.lat, point.lng]));
      if (data.markers.length === 1) map.setView([data.markers[0].lat, data.markers[0].lng], 16);
      else map.fitBounds(bounds, { padding: [30, 30] });
    } catch (error) {
      if (!isAbort(error)) info.textContent = `地圖載入失敗：${error.message}`;
    }
  }

  return {
    load,
    invalidate() {
      map?.invalidateSize();
    },
    render: renderMarkers,
    clear() {
      request.abort();
      markerLayer?.clearLayers();
      densityLayer?.clearLayers();
      currentMarkers = [];
      if (info) info.textContent = "";
      if (unlocated) { unlocated.innerHTML = ""; unlocated.classList.add("hidden"); }
    },
  };
}
