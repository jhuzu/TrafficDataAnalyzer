import { LatestRequest, isAbort, jsonOptions } from "./api.js";

export function createAccidentMap({ container, info, getToken, getOptions, escapeHtml }) {
  const request = new LatestRequest();
  let map = null;
  let markerLayer = null;

  function initialize() {
    if (map || !container) return;
    map = L.map(container, { center: [25.0118, 121.459], zoom: 14, zoomControl: true });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
    }).addTo(map);
    markerLayer = L.layerGroup().addTo(map);
  }

  async function load() {
    if (!getToken() || !container || container.clientWidth === 0 || container.clientHeight === 0) return;
    initialize();
    try {
      const data = await request.json(
        "/map-points",
        jsonOptions({ token: getToken(), ...getOptions() }),
      );
      info.textContent = `${Number(data.total).toLocaleString()} 筆座標（${data.coordField}）`;
      markerLayer.clearLayers();
      if (!data.markers.length) {
        info.textContent = "沒有可用的座標資料";
        return;
      }
      data.markers.forEach((marker) => {
        const radius = Math.max(5, Math.min(18, Math.sqrt(marker.count) * 2));
        L.circleMarker([marker.lat, marker.lng], {
          radius,
          fillColor: "#d73027",
          color: "#fff",
          weight: 1.5,
          fillOpacity: 0.75,
        })
          .bindPopup(`<div class="marker-popup"><strong>${escapeHtml(marker.label)}</strong><br>事故件數：<span class="count">${Number(marker.count).toLocaleString()}</span></div>`)
          .addTo(markerLayer);
      });
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
    clear() {
      request.abort();
      markerLayer?.clearLayers();
      if (info) info.textContent = "";
    },
  };
}
