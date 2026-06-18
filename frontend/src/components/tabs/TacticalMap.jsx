import React, { useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import AlertTriangle from 'lucide-react/dist/esm/icons/alert-triangle';
import X from 'lucide-react/dist/esm/icons/x';
import Flame from 'lucide-react/dist/esm/icons/flame';
import CheckCircle from 'lucide-react/dist/esm/icons/check-circle';
import { API_BASE } from '../../config';

const DEFAULT_CENTER = [24.165566, 94.259984];
const DEFAULT_ZOOM   = 14;

// ── FitBoundsController ──────────────────────────────────────────────────────
// Zooms to fit ALL active threat nodes at once.
// When a threat is acknowledged and removed, re-fits to the remaining ones.
// When all clear, flies back to the default overview.
function FitBoundsController({ activeThreatNodes }) {
  const map = useMap();
  const prevLen = useRef(0);

  useEffect(() => {
    if (activeThreatNodes.length > 0) {
      if (activeThreatNodes.length === 1) {
        const n = activeThreatNodes[0];
        map.flyTo([n.lat, n.lng], 17, { duration: 1.4 });
      } else {
        const bounds = L.latLngBounds(activeThreatNodes.map(n => [n.lat, n.lng]));
        map.flyToBounds(bounds, { padding: [100, 100], maxZoom: 17, duration: 1.4 });
      }
    } else if (prevLen.current > 0) {
      // Just cleared — fly back to overview
      map.flyTo(DEFAULT_CENTER, DEFAULT_ZOOM, { duration: 1.6 });
    }
    prevLen.current = activeThreatNodes.length;
  }, [activeThreatNodes.length, map]); // eslint-disable-line react-hooks/exhaustive-deps

  return null;
}

// ── MapResizer ───────────────────────────────────────────────────────────────
// Fixes the "mostly black" map issue caused by Leaflet miscalculating its container size
// when the flexbox layout is first rendered.
function MapResizer() {
  const map = useMap();
  useEffect(() => {
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 250);
    return () => clearTimeout(timer);
  }, [map]);
  return null;
}

// ── Marker icon factories ────────────────────────────────────────────────────
const STANDBY_ICON = L.divIcon({
  html: `
    <div style="width:120px;height:120px;display:flex;align-items:center;justify-content:center;">
      <div style="position:relative;width:40px;height:40px;display:flex;align-items:center;justify-content:center;">
        <div style="position:absolute;inset:0;border-radius:50%;border:2px solid #00FF9C;opacity:0.5;"></div>
        <div style="width:12px;height:12px;border-radius:50%;background:#00FF9C;box-shadow:0 0 12px #00FF9C;"></div>
      </div>
    </div>`,
  className: 'tactical-marker',
  iconSize: [120, 120],
  iconAnchor: [60, 60],
});

function createThreatIcon(count) {
  const badge = count > 1
    ? `<div style="position:absolute;top:-10px;right:-10px;background:#FF3B3B;color:white;
         border-radius:50%;width:22px;height:22px;display:flex;align-items:center;
         justify-content:center;font-size:11px;font-weight:900;
         box-shadow:0 0 8px rgba(255,59,59,0.8);">${count}</div>`
    : '';
  return L.divIcon({
    html: `
      <div style="width:160px;height:160px;display:flex;align-items:center;justify-content:center;">
        <div style="position:relative;width:70px;height:70px;display:flex;align-items:center;justify-content:center;">
          <div class="animate-ping" style="position:absolute;inset:0;border-radius:50%;
               border:3px solid #FF3B3B;opacity:0.75;animation-duration:0.9s;"></div>
          <div class="animate-ping" style="position:absolute;inset:-14px;border-radius:50%;
               border:2px solid #FF3B3B;opacity:0.35;animation-duration:0.9s;animation-delay:0.35s;"></div>
          <div style="width:18px;height:18px;border-radius:50%;background:#FF3B3B;
               box-shadow:0 0 24px #FF3B3B,0 0 8px rgba(255,59,59,0.5);"></div>
          ${badge}
        </div>
      </div>`,
    className: 'tactical-marker',
    iconSize: [160, 160],
    iconAnchor: [80, 80],
  });
}

// ── TacticalMap ──────────────────────────────────────────────────────────────
const TacticalMap = ({
  nodes = [],
  entities = [],
  mode = 'STANDBY',
  activeThreatNodes = [],   // [{node_id, name, lat, lng, threat_count, replay_url}]
  onDismiss,                // onDismiss(nodeId)
}) => {
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [heatmapStats, setHeatmapStats] = useState({ stats: {}, maxIncidents: 1 });

  // Build a lookup: node_id → threat info
  const threatMap = Object.fromEntries(activeThreatNodes.map(t => [t.node_id, t]));

  useEffect(() => {
    if (showHeatmap) {
      fetch(`${API_BASE}/api/analytics/heatmap?days=30`)
        .then(res => res.json())
        .then(data => {
          const stats = {};
          let maxIncidents = 1;
          for (const [nodeId, incidents] of Object.entries(data)) {
            stats[nodeId] = incidents.length;
            if (incidents.length > maxIncidents) maxIncidents = incidents.length;
          }
          setHeatmapStats({ stats, maxIncidents });
        })
        .catch(console.error);
    }
  }, [showHeatmap]);

  return (
    <div className="w-full h-full relative bg-[#020617] group">

      {/* Heatmap Toggle */}
      <button
        onClick={() => setShowHeatmap(!showHeatmap)}
        className={`absolute top-4 right-4 z-[400] px-3 py-2 rounded-lg text-[10px] font-black tracking-widest uppercase flex items-center gap-2 border transition-all ${
          showHeatmap
            ? 'bg-orange-500/20 border-orange-500 text-orange-500 shadow-[0_0_15px_rgba(249,115,22,0.3)]'
            : 'bg-[#0B0F1A]/90 backdrop-blur-md border-[#00F5FF]/10 text-slate-400 hover:text-white'
        }`}
      >
        <Flame size={14} />
        {showHeatmap ? 'HEATMAP: 30 DAYS' : 'SHOW HEATMAP'}
      </button>

      {/* Active threat counter badge */}
      {activeThreatNodes.length > 0 && (
        <div className="absolute top-4 left-4 z-[400] flex items-center gap-2 bg-[#FF3B3B]/15 border border-[#FF3B3B]/50 backdrop-blur-md rounded-xl px-4 py-2 shadow-lg animate-pulse">
          <div className="w-2.5 h-2.5 rounded-full bg-[#FF3B3B]" />
          <span className="text-[#FF3B3B] text-[11px] font-black tracking-widest uppercase">
            {activeThreatNodes.length} ACTIVE THREAT{activeThreatNodes.length > 1 ? 'S' : ''}
          </span>
          <span className="text-red-400/60 text-[9px] font-bold">— CLICK MARKER TO ACK</span>
        </div>
      )}

      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        minZoom={12}
        style={{ width: '100%', height: '100%', background: '#020617' }}
        zoomControl={false}
        maxBounds={[[24.05, 94.10], [24.30, 94.40]]}
        maxBoundsViscosity={1.0}
      >
        <MapResizer />
        <FitBoundsController activeThreatNodes={activeThreatNodes} />

        <TileLayer
          url="/tiles/{z}/{x}/{y}.png"
          maxZoom={22}
          maxNativeZoom={15}
          minZoom={10}
          noWrap={true}
        />

        {nodes.map(node => {
          const threat = threatMap[node.id];
          const incidentCount = heatmapStats.stats[node.id] || 0;
          const relativeHeat = incidentCount / heatmapStats.maxIncidents;
          const accentuatedHeat = Math.pow(relativeHeat, 2);
          const size = incidentCount > 0 ? 80 + accentuatedHeat * 170 : 0;
          const opacity = incidentCount > 0 ? 0.3 + accentuatedHeat * 0.5 : 0;

          return (
            <React.Fragment key={node.id}>
              {/* Heatmap radial glow */}
              {showHeatmap && incidentCount > 0 && (
                <Marker
                  position={[node.lat, node.lng]}
                  icon={L.divIcon({
                    html: `<div style="width:${size}px;height:${size}px;background:radial-gradient(circle,rgba(255,59,59,${opacity}) 0%,rgba(255,59,59,0) 70%);border-radius:50%;transform:translate(-50%,-50%);"></div>`,
                    className: 'heatmap-marker',
                    iconSize: [0, 0],
                  })}
                  interactive={false}
                />
              )}

              <Marker
                position={[node.lat, node.lng]}
                icon={threat ? createThreatIcon(threat.threat_count) : STANDBY_ICON}
              >
                {threat ? (
                  <Popup
                    className="tactical-popup"
                    closeButton={false}
                    autoPan={true}
                    minWidth={520}
                  >
                    <div className="bg-[#030B17]/97 backdrop-blur-md border border-[#FF3B3B]/30 p-4 rounded-lg flex flex-col gap-3 shadow-2xl">

                      {/* Header */}
                      <div className="flex justify-between items-center border-b border-[#FF3B3B]/20 pb-2">
                        <div>
                          <div className="text-[14px] font-black text-[#FF3B3B] tracking-widest uppercase flex items-center gap-2">
                            <AlertTriangle size={14} className="animate-pulse" />
                            {node.name}
                          </div>
                          <div className="text-[9px] text-slate-500 uppercase mt-0.5 font-mono">
                            {node.id}  ·  {threat.threat_count > 1 ? `${threat.threat_count} unacknowledged threats` : '1 unacknowledged threat'}
                          </div>
                        </div>
                        <button onClick={e => e.stopPropagation()} className="text-slate-600 hover:text-slate-400">
                          <X size={16} />
                        </button>
                      </div>

                      {/* Live feed */}
                      <div className="relative w-full aspect-video bg-black rounded overflow-hidden border border-[#FF3B3B]/30 shadow-[0_0_20px_rgba(255,59,59,0.15)]">
                        <img
                          src={threat.replay_url}
                          className="w-full h-full object-contain"
                          alt="Live Feed"
                          onError={e => { e.target.src = `https://placehold.co/800x640/020617/1A2535?text=NO+SIGNAL`; }}
                        />
                        <div className="absolute top-2 left-2 bg-[#FF3B3B] text-white text-[8px] font-black px-2 py-0.5 rounded uppercase tracking-wider flex items-center gap-1">
                          <div className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
                          LIVE
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex gap-2 mt-1">
                        <button
                          onClick={e => {
                            e.stopPropagation();
                            onDismiss && onDismiss(node.id);
                          }}
                          className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-[#00FF9C]/10 hover:bg-[#00FF9C]/20 text-[#00FF9C] border border-[#00FF9C]/30 rounded text-[11px] font-black tracking-widest uppercase transition-all"
                        >
                          <CheckCircle size={13} />
                          ACKNOWLEDGE {threat.threat_count > 1 ? `(${threat.threat_count - 1} REMAIN)` : ''}
                        </button>
                        <button
                          onClick={e => {
                            e.stopPropagation();
                            fetch(`${API_BASE}/api/admin/false_positive/${node.id}`, { method: 'POST' }).catch(() => {});
                            onDismiss && onDismiss(node.id);
                          }}
                          className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-yellow-500/10 hover:bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 rounded text-[11px] font-black tracking-widest uppercase transition-all"
                        >
                          FALSE POSITIVE
                        </button>
                      </div>
                    </div>
                  </Popup>
                ) : (
                  <Popup
                    className="tactical-popup"
                    closeButton={true}
                    autoPan={true}
                    minWidth={400}
                  >
                     <div className="bg-[#030B17]/97 backdrop-blur-md border border-[#00FF9C]/30 p-4 rounded-lg flex flex-col gap-3 shadow-2xl">
                        <div className="text-[14px] font-black text-[#00FF9C] tracking-widest uppercase flex justify-between items-center">
                          {node.name}
                          <span className="text-[10px] text-[#00FF9C]/60">STANDBY FEED</span>
                        </div>
                        <div className="relative w-full aspect-video bg-black rounded overflow-hidden border border-[#00FF9C]/30 shadow-[0_0_20px_rgba(0,255,156,0.1)]">
                          <img
                            src={`${API_BASE}/video_feed/${node.id}`}
                            className="w-full h-full object-contain"
                            alt="Live Feed"
                            onError={e => { e.target.src = `https://placehold.co/800x640/020617/1A2535?text=NO+SIGNAL`; }}
                          />
                        </div>
                     </div>
                  </Popup>
                )}
              </Marker>
            </React.Fragment>
          );
        })}
      </MapContainer>

      <style>{`
        .leaflet-container { background: #020617; font-family: inherit; }
        .tactical-popup .leaflet-popup-content-wrapper {
          background: transparent; box-shadow: none; padding: 0; border-radius: 0;
        }
        .tactical-popup .leaflet-popup-content { margin: 0; }
        .tactical-popup .leaflet-popup-tip { background: #030B17; border: 1px solid rgba(255,59,59,0.2); }
        .leaflet-tile-pane { filter: grayscale(0.5) brightness(0.6) opacity(0.9); }
      `}</style>
    </div>
  );
};

export default TacticalMap;
