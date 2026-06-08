import React, { useState, useEffect, useMemo } from 'react';
/* 
  Imports:
  React: The main library used to build the user interface.
  useState: Used to remember things like which button you clicked.
  useEffect: Used to perform tasks when the component first opens.
  useMemo: Used to speed up the dashboard by remembering calculated values.
*/

import { API_BASE } from '../../config';
/* The network address where the Python Backend is running */

import { Monitor, Activity, Shield, AlertTriangle, Cpu, Layers, Maximize2, Grid } from 'lucide-react';
/* These are the tactical icons (symbols) used in the buttons and labels */

// Definitions for Priority Levels (High, Medium, Low, Offline)
const PRIORITY = {
  HIGH: 3,
  MED: 2,
  LOW: 1,
  OFFLINE: 0
};

// CSS Styling for the Borders and Glow effects based on threat level
const THREAT_COLORS = {
  4: 'border-[#FF3B3B] shadow-[0_0_20px_rgba(255,59,59,0.4)]', // Red Glow for HIGH (4)
  2: 'border-[#FFD60A] shadow-[0_0_15px_rgba(255,214,10,0.3)]', // Orange Glow for MED (2)
  3: 'border-[#00F5FF] shadow-[0_0_15px_rgba(0,245,255,0.3)]',   // Blue Glow for STEALTH (3)
  1: 'border-[#00F5FF]/20',                                     // Subtle border for LOW (1)
  0: 'border-slate-800 opacity-50'                              // Faded border for OFFLINE (0)
};

const LiveFeed = ({ sensors, entities = [] }) => {
  /* 
    State variables: 
    viewMode: Remembers if you are in 'SMART', 'ALL HIGH', etc.
    manualId: Remembers if you clicked a specific camera number (1-4).
  */
  const [viewMode, setViewMode] = useState('SMART'); 
  const [manualId, setManualId] = useState(null);
  const [lockedSensors, setLockedSensors] = useState([]); // Array of sensor IDs that are manually pinned

  // Toggle locking a specific sensor so the SMART mode doesn't hide it
  const toggleLock = (id) => {
    setLockedSensors(prev => prev.includes(id) ? prev.filter(sid => sid !== id) : [...prev, id]);
  };

  // This part processes the data coming from Python and prepares it for the screen
  const processedSensors = useMemo(() => {
    return (sensors || []).map((s, i) => {
      const nodeEnts = entities.filter(e => e.sensor === `CAM-${i}`);
      const hasHighThreat = nodeEnts.some(e => e.type === 'high');
      
      return {
        ...s,
        id: i, // Camera number (0, 1, 2, 3)
        name: i === 3 ? 'VISUAL-IR FUSION' : `ESP32-CAM ${i + 1}`, // Label for the camera
        url: `${API_BASE}/video_feed/${i}`, // Where the video picture is fetched from
        threat: hasHighThreat ? 4 : (s.threat || 0), // REDUNDANT SYNC: Force threat 4 if entity exists
        label: hasHighThreat ? 'INTRUSION' : (s.label || 'SCANNING'),
        isLocked: lockedSensors.includes(i),
        // FOCAL INTERLOCK: Map backend threat (0-4) to UI Priority (0-3)
        priority: !s.online ? PRIORITY.OFFLINE : (hasHighThreat || s.threat >= 4 ? PRIORITY.HIGH : s.threat >= 2 ? PRIORITY.MED : PRIORITY.LOW)
      };
    });
  }, [sensors, lockedSensors, entities]);

  // List of cameras that are currently connected
  const onlineSensors = processedSensors.filter(s => s.online);
  // The highest threat number currently seen across ANY camera
  const highestPriority = Math.max(...processedSensors.map(s => s.priority), 0);

  // decide which camera pictures to actually show on the screen right now
  const visibleSensors = useMemo(() => {
    // 0. If FORCE GRID is active, show ALL online sensors no matter what
    if (viewMode === 'FORCE_GRID') return onlineSensors;

    // If you clicked a specific button (1, 2, 3, or 4), only show that one camera
    if (viewMode === 'MANUAL' && manualId !== null) {
      return processedSensors.filter(s => s.id === manualId);
    }
    
    // Filter modes: only show cameras with specific threat levels
    if (viewMode === 'ALL_HIGH') return processedSensors.filter(s => s.priority === PRIORITY.HIGH);
    if (viewMode === 'ALL_MED') return processedSensors.filter(s => s.priority === PRIORITY.MED);
    if (viewMode === 'ALL_LOW') return processedSensors.filter(s => s.priority === PRIORITY.LOW);

    // --- SMART MODE (The AI Control Logic) ---
    if (viewMode === 'SMART') {
      if (highestPriority === PRIORITY.OFFLINE) return [];
      
      // AI Pilot: Focus strictly on cameras with the MAXIMUM current threat level
      // If there are multiple at the same max level, show all of them.
      // If everything is LOW, show all online cameras for general area scanning.
      if (highestPriority > PRIORITY.LOW) {
        return processedSensors.filter(s => s.priority === highestPriority || s.isLocked);
      }
      
      return onlineSensors;
    }

    return onlineSensors;
  }, [viewMode, manualId, processedSensors, highestPriority, onlineSensors]);

  // Decides how many columns to use (1 for big view, 2 for grid view)
  const getGridClass = (count) => {
    if (count <= 1) return 'grid-cols-1';
    return 'grid-cols-2';
  };

  return (
    <div className="w-full h-full p-4 flex flex-col gap-4 bg-[#020617] overflow-hidden lg:overflow-visible font-sans text-white">
      
      {/* --- TOP CONTROL DASHBOARD --- */}
      <div className="flex flex-wrap items-center justify-between gap-4 shrink-0 bg-[#0B0F1A]/80 backdrop-blur-md p-3 rounded-xl border border-[#00F5FF]/10 shadow-xl">
        <div className="flex items-center gap-3">
          {/* Status Icon (Pulses when in smart mode) */}
          <div className={`p-2 rounded-lg bg-[#00F5FF]/10 text-[#00F5FF]`}>
             {viewMode === 'SMART' ? <Activity size={18} className="animate-pulse" /> : <Monitor size={18} />}
          </div>
          <div>
            <h2 className="text-[10px] font-black tracking-widest text-[#00F5FF] uppercase">Operation Matrix</h2>
            <p className="text-[8px] text-slate-500 font-bold uppercase">{viewMode.replace('_', ' ')} MODE // {onlineSensors.length} ACTIVE</p>
          </div>
        </div>

        {/* The Action Buttons (Smart, High, Med, Low, Force All) */}
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-1 lg:pb-0">
          {[
            { id: 'SMART', label: 'AI PILOT', icon: Activity },
            { id: 'FORCE_GRID', label: 'SEE ALL FEEDS', icon: Grid, color: 'text-white' },
            { id: 'ALL_HIGH', label: 'HIGH THREATS', icon: Shield, color: 'text-red-500' },
            { id: 'ALL_MED', label: 'MEDIUM THREATS', icon: AlertTriangle, color: 'text-amber-500' },
          ].map(opt => (
            <button
              key={opt.id}
              onClick={() => { setViewMode(opt.id); setManualId(null); }}
              className={`px-3 py-1.5 rounded-lg text-[9px] font-black tracking-tighter transition-all flex items-center gap-2 border ${
                viewMode === opt.id 
                ? 'bg-[#00F5FF]/20 border-[#00F5FF] text-[#00F5FF] shadow-[0_0_10px_rgba(0,245,255,0.2)]' 
                : 'bg-slate-900/50 border-slate-800 text-slate-500 hover:border-slate-700'
              }`}
            >
              <opt.icon size={12} className={viewMode === opt.id ? opt.color : ''} />
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* --- THE MAIN VIDEO DISPLAY AREA --- */}
      <div className="grow relative min-h-0 bg-black/40 rounded-2xl border border-slate-900 overflow-hidden shadow-inner group">
        {visibleSensors.length === 0 ? (
          /* Empty state if all cameras are gone */
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-slate-700">
            <Monitor size={48} className="opacity-20 animate-pulse" />
            <span className="text-[10px] font-black tracking-[0.3em] uppercase">No Signal Detected</span>
          </div>
        ) : (
          /* The Tactical Grid: Optimized for Full Field of View (FOV) */
          <div className="h-full w-full flex flex-wrap content-center justify-center gap-2 p-1 transition-all duration-500 overflow-hidden relative">
            {visibleSensors.map((sensor, idx) => {
              // Dynamic scaling to ensure the 16:9 feeds are as large as possible without being cut
              const containerStyles = visibleSensors.length === 1 ? 'w-full h-full' : 
                                      visibleSensors.length === 2 ? 'w-[49%] h-full max-h-full' : 
                                      'w-[49%] h-[48%]';
              
              return (
                <div 
                  key={sensor.id} 
                  className={`relative overflow-hidden border-2 transition-all duration-700 group/feed ${THREAT_COLORS[sensor.threat]} ${containerStyles} rounded-xl bg-[#020617] shadow-inner`}
                >
                  {/* TACTICAL AMBIENT BLUR: This fills 'Black Space' with a professional blurred version of the same feed */}
                  <div className="absolute inset-0 opacity-30 scale-110 blur-2xl pointer-events-none overflow-hidden">
                     <img src={sensor.url} className="w-full h-full object-cover" alt="" />
                  </div>

                  {/* MAIN FEED: Set to object-contain so NOTHING is ever cut off. High quality is preserved. */}
                  <img 
                    src={sensor.url} 
                    className="w-full h-full object-contain relative z-10" 
                    alt={sensor.name} 
                    onError={(e) => { e.target.src = 'https://placehold.co/640x480/020617/5A7090?text=NO+SIGNAL'; }}
                  />
                  
                  {/* Tactical Overlays (Appears when you hover your mouse over a camera) */}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover/feed:opacity-100 transition-opacity p-4 flex flex-col justify-between pointer-events-none">
                    <div className="flex justify-between items-start pointer-events-auto">
                       <span className="bg-black/60 backdrop-blur-md px-2 py-1 rounded text-[8px] font-black tracking-widest text-[#00F5FF]">CH-{sensor.id + 1}</span>
                       <div className="flex items-center gap-2">
                          <button 
                            onClick={(e) => { e.stopPropagation(); toggleLock(sensor.id); }}
                            className={`p-1.5 rounded-lg border transition-all ${sensor.isLocked ? 'bg-[#00F5FF] border-[#00F5FF] text-black shadow-[0_0_15px_#00F5FF]' : 'bg-black/60 border-white/10 text-white hover:border-[#00F5FF]'}`}
                            title={sensor.isLocked ? "Unlock Feed" : "Lock Feed"}
                          >
                             <Shield size={12} fill={sensor.isLocked ? "currentColor" : "none"} />
                          </button>
                          <Maximize2 size={14} className="text-white/60" />
                       </div>
                    </div>
                  </div>

                  {/* BOTTOM STATUS LABEL (Name and Danger Level) */}
                  <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between pointer-events-none">
                    <div className="bg-black/80 backdrop-blur-md px-2 py-1 rounded-md border border-[#00F5FF]/20 flex items-center gap-2">
                       {/* Blinking Dot for Danger */}
                       <div className={`w-1.5 h-1.5 rounded-full ${sensor.threat >= 3 ? 'bg-red-500 animate-ping' : sensor.threat >= 2 ? 'bg-amber-500' : 'bg-cyan-500'}`} />
                       <span className="text-[10px] font-black text-white/90 tracking-tighter uppercase whitespace-nowrap">{sensor.name}</span>
                    </div>
                    <div className="bg-black/80 backdrop-blur-md px-2 py-1 rounded-md border border-slate-800 text-[8px] font-black text-slate-400 uppercase tracking-widest">
                       {sensor.label}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* 
           SIDEBAR SELECTOR (Tactical Manual Override):
           Allows the operator to manually pin a specific sensor.
           Added z-50 to ensure it is always on top of the video feeds.
        */}
        <div className="absolute right-4 top-1/2 -translate-y-1/2 flex flex-col gap-2 p-2 bg-black/60 backdrop-blur-xl border border-white/10 rounded-2xl opacity-0 group-hover:opacity-100 transition-all duration-300 translate-x-10 group-hover:translate-x-0 z-50 shadow-2xl">
           {processedSensors.map(s => (
             <button
                key={s.id}
                onClick={(e) => { 
                  e.stopPropagation(); // Prevent the click from triggering other things
                  setViewMode('MANUAL'); 
                  setManualId(s.id); 
                }}
                className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all border-2 cursor-pointer ${
                  manualId === s.id && viewMode === 'MANUAL'
                  ? 'bg-[#00F5FF] border-[#00F5FF] text-black shadow-[0_0_20px_#00F5FF]'
                  : s.online ? 'bg-slate-900 border-slate-700 text-slate-300 hover:border-[#00F5FF] hover:text-[#00F5FF]' : 'bg-slate-950 border-slate-900 text-slate-800 cursor-not-allowed opacity-30'
                }`}
                disabled={!s.online}
                title={s.online ? `Switch to ${s.name}` : `${s.name} Offline`}
             >
                <span className="text-[11px] font-black">{s.id + 1}</span>
             </button>
           ))}
        </div>
      </div>

      {/* --- BOTTOM SYSTEM INFORMATION BAR --- */}
      <div className="flex items-center gap-6 shrink-0 px-4 py-2 border-t border-slate-900/50">
          <div className="flex items-center gap-2">
             <Layers size={12} className="text-[#00F5FF]/60" />
             <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">NODES ONLINE: {onlineSensors.length} / 4</span>
          </div>
          <div className="flex items-center gap-2">
             <Cpu size={12} className="text-[#00F5FF]/60" />
             <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">SMART GRID MAPPING: {viewMode}</span>
          </div>
      </div>

    </div>
  );
};

export default LiveFeed;
