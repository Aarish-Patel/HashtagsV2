import React, { useState, useMemo } from 'react';
import Monitor from 'lucide-react/dist/esm/icons/monitor';
import Activity from 'lucide-react/dist/esm/icons/activity';
import Shield from 'lucide-react/dist/esm/icons/shield';
import AlertTriangle from 'lucide-react/dist/esm/icons/alert-triangle';
import Grid from 'lucide-react/dist/esm/icons/grid';
import Layers from 'lucide-react/dist/esm/icons/layers';
import Cpu from 'lucide-react/dist/esm/icons/cpu';
import { API_BASE } from '../../config';

const PRIORITY = { HIGH: 3, MED: 2, LOW: 1, OFFLINE: 0 };
const THREAT_COLORS = {
  4: 'border-[#FF3B3B] shadow-[0_0_25px_rgba(255,59,59,0.5)]',
  3: 'border-[#FF3B3B] shadow-[0_0_20px_rgba(255,59,59,0.3)]',
  2: 'border-[#FFD60A] shadow-[0_0_15px_rgba(255,214,10,0.3)]',
  1: 'border-[#00F5FF]/30',
  0: 'border-slate-800/60 opacity-50',
};

// Determine grid layout based on sensor count
function getGridStyle(count) {
  if (count <= 1) return { cols: 1, rows: 1 };
  if (count <= 2) return { cols: 2, rows: 1 };
  if (count <= 4) return { cols: 2, rows: 2 };
  if (count <= 6) return { cols: 3, rows: 2 };
  if (count <= 9) return { cols: 3, rows: 3 };
  return { cols: Math.ceil(Math.sqrt(count)), rows: Math.ceil(count / Math.ceil(Math.sqrt(count))) };
}

const LiveFeed = ({
  sensors = [],
  entities = [],
  mode = 'STANDBY',
  replayUrls = {},    // node_id → replay MJPEG URL (shown when mode=THREAT)
  analysisJobs = [],  // array of analysis jobs
  onAnalyze,
  onDismiss,
}) => {
  const [viewMode, setViewMode] = useState('FORCE_GRID');
  const [manualId, setManualId] = useState(null);
  const [lockedSensors, setLockedSensors] = useState([]);

  const isThreat = mode === 'THREAT';
  const isAnalyzing = mode === 'ANALYZING';

  // Automatically switch to REPLAY_ONLY mode when a threat is detected
  React.useEffect(() => {
    if (isThreat) {
      setViewMode('REPLAY_ONLY');
    } else {
      setViewMode('FORCE_GRID');
      setManualId(null);
    }
  }, [isThreat]);

  const toggleLock = (id) => {
    setLockedSensors(prev => prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]);
  };

  // Build processed sensor list with URLs
  const processedSensors = useMemo(() => {
    return (sensors || []).map((s, i) => {
      const sensorId = s.id || `HASH-${i + 1}`;
      const isReplaying = isThreat && replayUrls[sensorId];
      const analysisJob = analysisJobs.find(job => job.node_id === sensorId);
      const isStreamingAnalysis = isAnalyzing && analysisJob && analysisJob.job_id;

      const feedUrl = isReplaying
        ? replayUrls[sensorId]            // Show annotated replay
        : `${API_BASE}/video_feed/${sensorId}`; // Normal live feed

      const threatLevel = isThreat
        ? Math.max(...entities.filter(e => e.node_id === sensorId).map(e => e.threat_level || 0), 0)
        : 0;

      return {
        ...s,
        id: i,
        rawId: sensorId,
        name: sensorId,
        url: feedUrl,
        threat: isThreat && replayUrls[sensorId] ? (threatLevel || 2) : 0,
        label: isThreat && replayUrls[sensorId] ? `THREAT — REPLAY`
             : isStreamingAnalysis ? `ANALYZING... ${Math.round(analysisJob.progress || 0)}%`
             : isAnalyzing ? 'ANALYZING...'
             : 'STANDBY',
        isLocked: lockedSensors.includes(i),
        priority: !s.online ? PRIORITY.OFFLINE
                : (isThreat && replayUrls[sensorId]) ? PRIORITY.HIGH
                : PRIORITY.LOW,
        hasReplay: isThreat && !!replayUrls[sensorId],
      };
    });
  }, [sensors, entities, replayUrls, analysisJobs, isThreat, isAnalyzing, lockedSensors]);

  const onlineSensors = processedSensors.filter(s => s.online !== false);
  const visibleSensors = useMemo(() => {
    if (viewMode === 'MANUAL' && manualId !== null) {
      return processedSensors.filter(s => s.id === manualId);
    }
    if (viewMode === 'REPLAY_ONLY' && isThreat) {
      return processedSensors.filter(s => s.hasReplay);
    }
    return onlineSensors;
  }, [viewMode, manualId, processedSensors, onlineSensors, isThreat]);

  const { cols } = getGridStyle(visibleSensors.length);

  return (
    <div className="w-full h-full p-3 flex flex-col gap-3 bg-[#020617] overflow-hidden font-sans text-white">

      {/* ── CONTROL BAR ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 shrink-0 bg-[#0B0F1A]/90 backdrop-blur-md px-4 py-2.5 rounded-xl border border-[#00F5FF]/10">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${isThreat ? 'bg-[#FF3B3B]/20 text-[#FF3B3B]' : 'bg-[#00F5FF]/10 text-[#00F5FF]'}`}>
            {isAnalyzing ? <Activity size={16} className="animate-spin" /> : <Monitor size={16} />}
          </div>
          <div>
            <div className="text-[10px] font-black tracking-widest uppercase text-[#00F5FF]">
              {isThreat ? '⚠ THREAT REPLAY' : isAnalyzing ? 'ANALYZING BUFFER' : 'STANDBY SURVEILLANCE'}
            </div>
            <div className="text-[8px] text-slate-500 font-bold uppercase tracking-wider">
              {onlineSensors.length} NODES ACTIVE  //  {viewMode.replace('_', ' ')} MODE
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* View toggles */}
          {[
            { id: 'FORCE_GRID', label: 'ALL FEEDS', icon: Grid },
            ...(isThreat ? [{ id: 'REPLAY_ONLY', label: 'THREATS ONLY', icon: AlertTriangle, color: 'text-red-500' }] : []),
          ].map(opt => (
            <button
              key={opt.id}
              onClick={() => { setViewMode(opt.id); setManualId(null); }}
              className={`px-3 py-1.5 rounded-lg text-[9px] font-black tracking-tighter transition-all flex items-center gap-1.5 border ${
                viewMode === opt.id
                  ? 'bg-[#00F5FF]/20 border-[#00F5FF] text-[#00F5FF] shadow-[0_0_10px_rgba(0,245,255,0.15)]'
                  : 'bg-slate-900/60 border-slate-800 text-slate-500 hover:border-slate-600'
              }`}
            >
              <opt.icon size={11} />
              {opt.label}
            </button>
          ))}

          {/* SPACE trigger button */}
          {!isThreat && !isAnalyzing && (
            <button
              onClick={onAnalyze}
              className="px-4 py-1.5 rounded-lg text-[9px] font-black tracking-widest border border-[#00F5FF]/40 bg-[#00F5FF]/10 text-[#00F5FF] hover:bg-[#00F5FF]/20 transition-all uppercase flex items-center gap-1.5"
            >
              <Shield size={11} />
              ANALYZE  [SPACE]
            </button>
          )}
          {isThreat && (
            <button
              onClick={onDismiss}
              className="px-4 py-1.5 rounded-lg text-[9px] font-black tracking-widest border border-red-500/40 bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-all uppercase"
            >
              DISMISS  [SPACE]
            </button>
          )}
        </div>
      </div>

      {/* ── VIDEO GRID ── */}
      <div
        className="grow relative min-h-0 bg-black/30 rounded-xl border border-slate-900/80 overflow-hidden group"
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${Math.min(cols, visibleSensors.length || 1)}, minmax(0, 1fr))`,
          gridAutoRows: '1fr',
          gap: '6px',
          padding: '6px',
        }}
      >
        {visibleSensors.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-slate-700 col-span-full">
            <Monitor size={48} className="opacity-20 animate-pulse" />
            <span className="text-[10px] font-black tracking-[0.3em] uppercase">No Feeds Online</span>
          </div>
        ) : (
          visibleSensors.map((sensor) => (
            <FeedCell
              key={sensor.rawId}
              sensor={sensor}
              isThreat={isThreat}
              isAnalyzing={isAnalyzing}
              onLock={() => toggleLock(sensor.id)}
              onSelect={() => { setViewMode('MANUAL'); setManualId(sensor.id); }}
              isSelected={viewMode === 'MANUAL' && manualId === sensor.id}
            />
          ))
        )}
      </div>

      {/* ── BOTTOM INFO BAR ── */}
      <div className="flex items-center gap-6 shrink-0 px-3 py-1.5 border-t border-slate-900/40">
        <div className="flex items-center gap-2">
          <Layers size={11} className="text-[#00F5FF]/50" />
          <span className="text-[8px] font-bold text-slate-600 uppercase tracking-widest">
            NODES: {onlineSensors.length} / {processedSensors.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Cpu size={11} className="text-[#00F5FF]/50" />
          <span className="text-[8px] font-bold text-slate-600 uppercase tracking-widest">
            {isThreat
              ? `REPLAYING ANNOTATED CLIP — ${Object.keys(replayUrls).length} FEEDS`
              : `STANDBY — ML OFFLINE UNTIL SPACE PRESSED`}
          </span>
        </div>
        {isThreat && (
          <div className="ml-auto flex items-center gap-2 animate-pulse">
            <div className="w-2 h-2 rounded-full bg-[#FF3B3B]" />
            <span className="text-[8px] font-black text-[#FF3B3B] uppercase tracking-widest">
              THREAT CONFIRMED
            </span>
          </div>
        )}
      </div>
    </div>
  );
};


// ── Individual Feed Cell ────────────────────────────────────────────────────
function FeedCell({ sensor, isThreat, isAnalyzing, onLock, onSelect, isSelected }) {
  const threatStyle = THREAT_COLORS[sensor.threat] || THREAT_COLORS[0];

  return (
    <div
      className={`relative overflow-hidden rounded-xl border-2 transition-all duration-500 cursor-pointer group/cell bg-[#020617]
        ${threatStyle}
        ${sensor.hasReplay ? 'ring-2 ring-[#FF3B3B]/40' : ''}
        ${isSelected ? 'ring-2 ring-[#00F5FF]' : ''}
      `}
      onClick={onSelect}
    >
      {/* Ambient blur background */}
      <div className="absolute inset-0 opacity-20 scale-110 blur-xl pointer-events-none">
        <img src={sensor.url} alt="" className="w-full h-full object-cover" />
      </div>

      {/* Main feed image (MJPEG stream as img) */}
      <img
        src={sensor.url}
        alt={sensor.name}
        className="w-full h-full object-contain relative z-10"
        onError={e => { e.target.src = `https://placehold.co/800x640/020617/1A2535?text=NO+SIGNAL`; }}
      />

      {/* Hover overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-transparent to-transparent opacity-0 group-hover/cell:opacity-100 transition-opacity duration-200 z-20 pointer-events-none">
        <div className="absolute top-2 right-2 flex items-center gap-1 pointer-events-auto">
          <button
            onClick={e => { e.stopPropagation(); onLock(); }}
            className={`p-1.5 rounded-lg border transition-all ${
              sensor.isLocked
                ? 'bg-[#00F5FF] border-[#00F5FF] text-black'
                : 'bg-black/70 border-white/20 text-white hover:border-[#00F5FF]'
            }`}
          >
            <Shield size={10} fill={sensor.isLocked ? 'currentColor' : 'none'} />
          </button>
        </div>
      </div>

      {/* Bottom status label */}
      <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between z-20 pointer-events-none">
        <div className="bg-black/80 backdrop-blur-md px-2 py-0.5 rounded-md border border-[#00F5FF]/20 flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full ${
            sensor.hasReplay ? 'bg-red-500 animate-ping'
            : isAnalyzing   ? 'bg-yellow-500 animate-pulse'
            : 'bg-slate-500'
          }`} />
          <span className="text-[9px] font-black text-white/90 tracking-tighter uppercase">
            {sensor.name}
          </span>
        </div>
        <div className={`bg-black/80 backdrop-blur-md px-2 py-0.5 rounded-md border text-[8px] font-black uppercase tracking-widest ${
          sensor.hasReplay ? 'border-red-500/30 text-red-400'
          : isAnalyzing   ? 'border-yellow-500/30 text-yellow-400'
          : 'border-slate-800 text-slate-500'
        }`}>
          {sensor.label}
        </div>
      </div>

      {/* REPLAY badge top-left */}
      {sensor.hasReplay && (
        <div className="absolute top-2 left-2 z-20 bg-[#FF3B3B] text-white text-[8px] font-black px-2 py-0.5 rounded uppercase tracking-wider flex items-center gap-1">
          <div className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
          REPLAY
        </div>
      )}

      {/* STANDBY watermark */}
      {!sensor.hasReplay && !isAnalyzing && (
        <div className="absolute inset-0 flex items-center justify-center z-30 pointer-events-none opacity-0 group-hover/cell:opacity-100 transition-opacity">
          <span className="text-[10px] font-black tracking-[0.3em] text-slate-600 uppercase">STANDBY</span>
        </div>
      )}
    </div>
  );
}

export default LiveFeed;
