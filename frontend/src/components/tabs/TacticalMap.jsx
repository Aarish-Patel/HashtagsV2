import React, { useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import AlertTriangle from 'lucide-react/dist/esm/icons/alert-triangle';
import X from 'lucide-react/dist/esm/icons/x';

// Auto-Pan Component
function MapController({ center, zoom }) {
  const map = useMap();
  
  // Convert array to string for stable dependency
  const centerStr = center ? center.join(',') : '';
  
  useEffect(() => {
    if (centerStr) {
      const [lat, lng] = centerStr.split(',').map(Number);
      map.flyTo([lat, lng], zoom, { duration: 1.5 });
    }
  }, [centerStr, zoom, map]);
  return null;
}

const createTacticalIcon = (isThreat) => {
  const color = isThreat ? '#FF3B3B' : '#00FF9C';
  const pulseClass = isThreat ? 'animate-ping' : '';
  
  const html = `
    <div style="width: 120px; height: 120px; display: flex; align-items: center; justify-content: center; cursor: pointer;">
      <div style="position: relative; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center;">
        <!-- Outer ring -->
        <div class="${pulseClass}" style="position: absolute; inset: 0; border-radius: 50%; border: 2px solid ${color}; opacity: 0.5;"></div>
        <!-- Inner dot -->
        <div style="width: 12px; height: 12px; border-radius: 50%; background-color: ${color}; box-shadow: 0 0 12px ${color};"></div>
      </div>
    </div>
  `;

  return L.divIcon({
    html,
    className: 'tactical-marker',
    iconSize: [120, 120],
    iconAnchor: [60, 60],
  });
};

const STANDBY_ICON = createTacticalIcon(false);
const THREAT_ICON = createTacticalIcon(true);

const TacticalMap = ({
  nodes = [],
  entities = [],
  mode = 'STANDBY',
  replayUrls = {},
  onDismiss
}) => {
  const isThreat = mode === 'THREAT';
  
  // Find active threat node
  const activeThreatNode = isThreat ? nodes.find(n => replayUrls[n.id]) : null;
  const centerPos = activeThreatNode ? [activeThreatNode.lat, activeThreatNode.lng] : [24.165566, 94.259984];
  const zoomLevel = activeThreatNode ? 18 : 13;

  return (
    <div className="w-full h-full relative bg-[#020617]">
      <MapContainer 
        center={[24.165566, 94.259984]} 
        zoom={13} 
        style={{ width: '100%', height: '100%', background: '#020617' }}
        zoomControl={false}
        maxBounds={[ [24.10, 94.15], [24.25, 94.35] ]}
        maxBoundsViscosity={1.0}
      >
        <MapController center={centerPos} zoom={zoomLevel} />
        
        {/* Offline local tiles */}
        <TileLayer
          url="/tiles/{z}/{x}/{y}.png"
          maxZoom={22}
          maxNativeZoom={18}
          minZoom={10}
          noWrap={true}
          bounds={[ [24.10, 94.15], [24.25, 94.35] ]}
        />

        {/* Map Darkening Filter for Tactical UI */}
        <div className="leaflet-pane leaflet-tile-pane" style={{ filter: 'brightness(0.4) contrast(1.3) grayscale(0.6)' }}></div>

        {nodes.map(node => {
          const nodeHasThreat = isThreat && !!replayUrls[node.id];
          return (
            <Marker 
              key={node.id} 
              position={[node.lat, node.lng]} 
              icon={nodeHasThreat ? THREAT_ICON : STANDBY_ICON}
            >
              {nodeHasThreat && (
                <Popup className="tactical-popup" closeButton={false} autoPan={true}>
                  <div className="bg-[#030B17]/95 backdrop-blur-md border border-[#00F5FF]/30 p-4 rounded-lg flex flex-col gap-3 shadow-2xl min-w-[500px]">
                    <div className="flex justify-between items-center border-b border-[#00F5FF]/10 pb-2 relative">
                      <div className="flex flex-col">
                        <span className="text-[14px] font-black text-[#00F5FF] tracking-widest uppercase">{node.name}</span>
                        <span className="text-[10px] text-slate-500 uppercase">{node.ip}</span>
                      </div>
                      <button 
                        onClick={(e) => { e.stopPropagation(); onDismiss(); }}
                        className="text-slate-400 hover:text-white transition-colors"
                      >
                        <X size={18} />
                      </button>
                    </div>
                    
                    <div className="flex flex-col gap-3">
                      <div className="flex items-center gap-2 text-[#FF3B3B] animate-pulse bg-[#FF3B3B]/10 px-3 py-2 rounded">
                        <AlertTriangle size={18} />
                        <span className="text-[12px] font-black uppercase tracking-wider">Threat Detected</span>
                      </div>
                      
                      <div className="relative w-full aspect-video bg-black rounded overflow-hidden border border-[#FF3B3B]/30 shadow-[0_0_15px_rgba(255,59,59,0.2)]">
                        {replayUrls[node.id] && replayUrls[node.id].endsWith('.mp4') ? (
                          <video 
                            src={replayUrls[node.id]} 
                            autoPlay 
                            loop 
                            muted 
                            className="w-full h-full object-contain"
                          />
                        ) : (
                          <img 
                            src={replayUrls[node.id]} 
                            className="w-full h-full object-contain"
                            alt="Live Feed"
                          />
                        )}
                      </div>
                      
                      <div className="flex gap-2 mt-2">
                        <button 
                          onClick={(e) => { e.stopPropagation(); onDismiss(); }}
                          className="flex-1 py-3 bg-[#00F5FF]/10 hover:bg-[#00F5FF]/20 text-[#00F5FF] border border-[#00F5FF]/30 rounded text-[11px] font-black tracking-widest uppercase transition-colors shadow-lg"
                        >
                          ACKNOWLEDGE
                        </button>
                        <button 
                          onClick={(e) => { 
                            e.stopPropagation(); 
                            // TODO: Add API call to flag as false positive to improve model
                            console.log("Logged false positive for node:", node.id);
                            onDismiss(); 
                          }}
                          className="flex-1 py-3 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 rounded text-[11px] font-black tracking-widest uppercase transition-colors shadow-lg"
                        >
                          FALSE POSITIVE
                        </button>
                      </div>
                    </div>
                  </div>
                </Popup>
              )}
            </Marker>
          );
        })}
      </MapContainer>
      
      {/* Global CSS Overrides for Leaflet to fit the dark UI */}
      <style>{`
        .leaflet-container {
          background: #020617;
          font-family: inherit;
        }
        .tactical-popup .leaflet-popup-content-wrapper {
          background: transparent;
          box-shadow: none;
          padding: 0;
          border-radius: 0;
        }
        .tactical-popup .leaflet-popup-tip {
          background: #030B17;
          border: 1px solid rgba(0, 245, 255, 0.2);
        }
        .leaflet-tile-pane {
          filter: grayscale(0.5) brightness(0.6) opacity(0.9);
        }
      `}</style>
    </div>
  );
};

export default TacticalMap;
