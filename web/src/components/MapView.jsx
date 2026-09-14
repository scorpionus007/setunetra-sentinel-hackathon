import React, { useEffect } from "react";
import { CircleMarker, MapContainer, TileLayer, Popup, useMap } from "react-leaflet";
import { DEPT_COLORS } from "../ui";

function MapRecenter({ target }) {
  const map = useMap();
  useEffect(() => {
    if (target && Number.isFinite(target.lat) && Number.isFinite(target.lon)) {
      map.flyTo([target.lat, target.lon], 12, { duration: 1.1 });
    }
  }, [target, map]);
  return null;
}

function MapInvalidator() {
  const map = useMap();
  useEffect(() => {
    map.invalidateSize();
    const t1 = setTimeout(() => map.invalidateSize(), 120);
    const t2 = setTimeout(() => map.invalidateSize(), 500);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [map]);
  return null;
}

const STATUS_RING = { live: "#15803d", down: "#dc2626", degraded: "#d97706", unknown: "#94a3b8" };

export default function MapView({ cameras = [], selectedCamera = null, onSelectCamera = () => {}, focusTarget = null }) {
  const mappable = cameras.filter((c) => Number.isFinite(c.lat) && Number.isFinite(c.lon));

  return (
    <div className="map-wrap">
      <MapContainer center={[22.6, 71.6]} zoom={7} scrollWheelZoom={true} style={{ height: "100%", width: "100%" }}>
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />
        <MapRecenter target={focusTarget || selectedCamera} />
        <MapInvalidator />

        {mappable.map((cam) => {
          const isSel = selectedCamera && String(selectedCamera.external_id) === String(cam.external_id);
          const deptColor = DEPT_COLORS[cam.department] || "#64748b";
          const ring = STATUS_RING[cam.status] || "#94a3b8";
          return (
            <CircleMarker
              key={cam.id || cam.external_id}
              center={[cam.lat, cam.lon]}
              radius={isSel ? 11 : 7}
              pathOptions={{ fillColor: deptColor, fillOpacity: 0.92, color: ring, weight: isSel ? 4 : 2.5 }}
              eventHandlers={{ click: () => onSelectCamera(cam) }}
            >
              <Popup>
                <div className="popup-card">
                  <div className="popup-title">{cam.location_name || `Camera ${cam.external_id}`}</div>
                  <div className="popup-location">{cam.district || "—"} · {cam.department || "Unclassified"}</div>
                  <div className="popup-row"><span>Status</span><strong style={{ color: ring, textTransform: "capitalize" }}>{cam.status}</strong></div>
                  <div className="popup-row"><span>Type</span><strong style={{ textTransform: "uppercase" }}>{cam.camera_type}</strong></div>
                  <div className="popup-row"><span>Device ID</span><strong>#{cam.external_id}</strong></div>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

      <div className="map-legend-overlay">
        <div className="legend-title">Departments</div>
        <div className="legend-items">
          {Object.entries(DEPT_COLORS).map(([name, color]) => (
            <span key={name} className="legend-item">
              <span className="legend-dot" style={{ background: color }} />{name}
            </span>
          ))}
        </div>
      </div>
      <div className="map-footer-overlay">{mappable.length} of {cameras.length} feeds pinned</div>
    </div>
  );
}
