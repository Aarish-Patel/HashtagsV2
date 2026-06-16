import React, { useState, useEffect, useRef } from 'react';
import { API_BASE } from '../../config';
import Activity from 'lucide-react/dist/esm/icons/activity';
import AlertTriangle from 'lucide-react/dist/esm/icons/alert-triangle';
import CheckCircle from 'lucide-react/dist/esm/icons/check-circle';
import XCircle from 'lucide-react/dist/esm/icons/x-circle';
import Clock from 'lucide-react/dist/esm/icons/clock';
import Cpu from 'lucide-react/dist/esm/icons/cpu';
import Radio from 'lucide-react/dist/esm/icons/radio';
import Layers from 'lucide-react/dist/esm/icons/layers';
import Bug from 'lucide-react/dist/esm/icons/bug';
import BarChart2 from 'lucide-react/dist/esm/icons/bar-chart-2';
import Search from 'lucide-react/dist/esm/icons/search';
import RefreshCw from 'lucide-react/dist/esm/icons/refresh-cw';
import ChevronDown from 'lucide-react/dist/esm/icons/chevron-down';
import ChevronUp from 'lucide-react/dist/esm/icons/chevron-up';

// ─── Mini sparkline ──────────────────────────────────────────────────────────
function Sparkline({ data, color = '#00F5FF', height = 32, maxVal }) {
  const w = 120, h = height;
  if (!data || data.length < 2) return <div className="w-[120px]" style={{ height: h }} />;
  const mx = maxVal || Math.max(...data, 1);
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - (v / mx) * h}`).join(' ');
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx={(w)} cy={h - (data[data.length - 1] / mx) * h} r="2.5" fill={color} />
    </svg>
  );
}

// ─── Status Badge ─────────────────────────────────────────────────────────────
function Badge({ ok, label, sub }) {
  const color = ok === true ? 'text-[#00FF9C] border-[#00FF9C]/30 bg-[#00FF9C]/5'
              : ok === 'warn' ? 'text-yellow-400 border-yellow-500/30 bg-yellow-500/5'
              : 'text-[#FF3B3B] border-[#FF3B3B]/30 bg-[#FF3B3B]/5';
  const Icon = ok === true ? CheckCircle : ok === 'warn' ? AlertTriangle : XCircle;
  return (
    <div className={`flex items-center gap-2 border rounded-lg px-3 py-2 ${color}`}>
      <Icon size={14} />
      <div>
        <div className="text-xs font-bold">{label}</div>
        {sub && <div className="text-[9px] opacity-70 font-mono">{sub}</div>}
      </div>
    </div>
  );
}

// ─── Exception Card ───────────────────────────────────────────────────────────
function ExceptionCard({ exc }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border border-[#FF3B3B]/20 bg-[#FF3B3B]/5 rounded-lg p-3 text-[10px] font-mono">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-slate-400">{exc.ts_str}</span>
            <span className="text-slate-600">|</span>
            <span className="text-[#00F5FF] font-bold">{exc.node_id}</span>
            <span className="text-slate-600">|</span>
            <span className="text-slate-500">{exc.context}</span>
          </div>
          <div className="text-[#FF3B3B] font-bold">{exc.type}: <span className="text-slate-300 font-normal">{exc.message}</span></div>
          {exc.source_hint && (
            <div className="mt-1 text-yellow-500 text-[9px] truncate" title={exc.source_hint}>
              📍 {exc.source_hint}
            </div>
          )}
        </div>
        <button onClick={() => setExpanded(v => !v)} className="text-slate-600 hover:text-slate-400 shrink-0">
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>
      {expanded && exc.traceback && (
        <pre className="mt-2 text-[8px] text-slate-400 bg-black/40 p-2 rounded overflow-x-auto whitespace-pre-wrap border border-slate-800">
          {exc.traceback}
        </pre>
      )}
    </div>
  );
}

// ─── Pipeline Metric Row ──────────────────────────────────────────────────────
function MetricRow({ label, value, unit = '', color = 'text-white', warn, danger, barMax, barVal }) {
  const isWarn = warn !== undefined && value >= warn;
  const isDanger = danger !== undefined && value >= danger;
  const textColor = isDanger ? 'text-[#FF3B3B]' : isWarn ? 'text-yellow-400' : color;
  return (
    <div className="flex items-center justify-between py-1 border-b border-slate-900">
      <span className="text-[10px] text-slate-500 font-mono">{label}</span>
      <div className="flex items-center gap-2">
        {barMax !== undefined && (
          <div className="w-16 h-1 bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full rounded-full transition-all"
              style={{ width: `${Math.min(100, (barVal ?? value) / barMax * 100)}%`, backgroundColor: isDanger ? '#FF3B3B' : isWarn ? '#FFD60A' : '#00F5FF' }} />
          </div>
        )}
        <span className={`text-[10px] font-bold font-mono ${textColor}`}>{value}{unit}</span>
      </div>
    </div>
  );
}

// ─── Detection History Mini-Table ─────────────────────────────────────────────
function DetectionHistory({ history }) {
  if (!history || history.length === 0)
    return <div className="text-slate-700 text-[10px] font-mono text-center py-4">No detection history yet</div>;
  const recent = [...history].reverse().slice(0, 15);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[9px] font-mono">
        <thead>
          <tr className="text-slate-600 border-b border-slate-800">
            <th className="text-left py-1 pr-2">Time</th>
            <th className="text-right pr-2">A blobs</th>
            <th className="text-right pr-2">A area</th>
            <th className="text-right pr-2">B raw</th>
            <th className="text-right pr-2">B conf</th>
            <th className="text-right pr-2">→ pass</th>
            <th className="text-right">mode</th>
          </tr>
        </thead>
        <tbody>
          {recent.map((r, i) => (
            <tr key={i} className={`border-b border-slate-900 ${r.intersection_pass > 0 ? 'bg-[#FF3B3B]/5' : ''}`}>
              <td className="py-0.5 pr-2 text-slate-500">{new Date(r.ts * 1000).toLocaleTimeString('en-GB')}</td>
              <td className="text-right pr-2 text-slate-300">{r.prong_a_blobs}</td>
              <td className="text-right pr-2 text-slate-400">{r.prong_a_area}</td>
              <td className="text-right pr-2 text-slate-300">{r.prong_b_dets}</td>
              <td className={`text-right pr-2 ${r.prong_b_conf > 0.1 ? 'text-yellow-400' : 'text-slate-400'}`}>{r.prong_b_conf.toFixed(3)}</td>
              <td className={`text-right pr-2 font-bold ${r.intersection_pass > 0 ? 'text-[#FF3B3B]' : 'text-slate-600'}`}>{r.intersection_pass}</td>
              <td className="text-right text-slate-600">{r.mode ? 'CANNY' : 'MOG2'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Main DebugPanel ──────────────────────────────────────────────────────────
export default function DebugPanel({ nodeId, nodes }) {
  const [snap, setSnap] = useState(null);
  const [exceptions, setExceptions] = useState([]);
  const [pipelineAll, setPipelineAll] = useState([]);
  const [excFilter, setExcFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [inferenceHistory, setInferenceHistory] = useState([]);
  const intervalRef = useRef(null);

  const fetchSnap = async () => {
    if (!nodeId) return;
    try {
      const [s, e, p] = await Promise.all([
        fetch(`${API_BASE}/api/debug/${nodeId}`).then(r => r.json()),
        fetch(`${API_BASE}/api/debug/exceptions?limit=40`).then(r => r.json()),
        fetch(`${API_BASE}/api/debug/pipeline`).then(r => r.json()),
      ]);
      setSnap(s);
      setExceptions(Array.isArray(e) ? e : []);
      setPipelineAll(Array.isArray(p) ? p : []);
      // Rolling inference-ms sparkline
      if (s?.pipeline?.inference_ms) {
        setInferenceHistory(h => [...h.slice(-59), s.pipeline.inference_ms]);
      }
    } catch (err) {}
  };

  useEffect(() => {
    fetchSnap();
  }, [nodeId]);

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (autoRefresh) {
      intervalRef.current = setInterval(fetchSnap, 1500);
    }
    return () => clearInterval(intervalRef.current);
  }, [autoRefresh, nodeId]);

  const filteredExc = exceptions.filter(e => {
    if (!excFilter) return true;
    const q = excFilter.toLowerCase();
    return (e.node_id || '').toLowerCase().includes(q)
      || (e.type || '').toLowerCase().includes(q)
      || (e.message || '').toLowerCase().includes(q)
      || (e.source_hint || '').toLowerCase().includes(q)
      || (e.context || '').toLowerCase().includes(q);
  });

  const t = snap?.threads || {};
  const p = snap?.pipeline || {};

  const captureOk   = t.capture_health  === 'OK';
  const inferenceOk = t.inference_health === 'OK';

  return (
    <div className="flex flex-col gap-5">

      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-white uppercase tracking-widest flex items-center gap-2">
          <Bug size={15} className="text-[#FF3B3B]" />
          Live Diagnostics
          {nodeId ? <span className="text-[#00F5FF] font-mono">— {nodeId}</span> : <span className="text-slate-600">— no node selected</span>}
        </h2>
        <div className="flex items-center gap-2">
          <button onClick={() => setAutoRefresh(v => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-[9px] font-bold rounded border transition-all ${autoRefresh ? 'border-[#00FF9C]/40 text-[#00FF9C] bg-[#00FF9C]/10' : 'border-slate-700 text-slate-500 bg-slate-900'}`}>
            <Radio size={10} /> {autoRefresh ? 'LIVE' : 'PAUSED'}
          </button>
          <button onClick={fetchSnap} className="p-1.5 rounded border border-slate-700 text-slate-400 hover:text-white hover:border-slate-500 transition-all">
            <RefreshCw size={12} />
          </button>
        </div>
      </div>

      {/* ── Pipeline-wide health row ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Badge
          ok={t.capture_alive && captureOk}
          label="Capture Thread"
          sub={t.capture_alive ? (captureOk ? `${t.capture_last_frame_age_s}s ago` : `STALE ${t.capture_last_frame_age_s}s`) : 'DEAD'}
        />
        <Badge
          ok={t.inference_alive && inferenceOk}
          label="Inference Thread"
          sub={t.inference_alive ? (inferenceOk ? `${t.inference_last_cycle_age_s}s ago` : `STALE ${t.inference_last_cycle_age_s}s`) : 'DEAD'}
        />
        <Badge
          ok={p.prong_mode === 'CANNY_BG' ? true : 'warn'}
          label="BG Mode"
          sub={p.prong_mode || '—'}
        />
        <Badge
          ok={!snap?.last_exception}
          label="Last Exception"
          sub={snap?.last_exception ? `${snap.last_exception.type} @ ${snap.last_exception.ts_str}` : 'None'}
        />
      </div>

      {/* ── Main diagnostic grid ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

        {/* Pipeline Metrics */}
        <div className="bg-[#030B17] border border-slate-800 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3 border-b border-slate-800 pb-2">
            <BarChart2 size={13} className="text-[#00F5FF]" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">Pipeline Metrics</h3>
          </div>
          <MetricRow label="FPS" value={p.fps || 0} unit="" warn={1} danger={0.1} color="text-[#00FF9C]" />
          <MetricRow label="Inference time" value={p.inference_ms || 0} unit=" ms" warn={500} danger={2000} barMax={1000} />
          <MetricRow label="Inference cycles" value={p.inference_cycles_total || 0} />
          <MetricRow label="Buffer depth" value={p.buffer_depth || 0} unit={` / ${p.buffer_capacity || 75}`} barMax={p.buffer_capacity || 75} barVal={p.buffer_depth || 0} />
          <MetricRow label="Prong A blobs" value={p.prong_a_blobs || 0} warn={5} danger={20} />
          <MetricRow label="Prong A avg area" value={p.prong_a_avg_blob_area || 0} unit=" px²" />
          <MetricRow label="Prong B raw YOLO" value={p.prong_b_yolo_raw || 0} warn={3} />
          <MetricRow label="Prong B max conf" value={p.prong_b_max_conf || 0} barMax={1} barVal={p.prong_b_max_conf || 0} />
          <MetricRow label="Intersection pass" value={p.intersection_passed || 0} color="text-[#FF3B3B]" />
          <MetricRow label="Brightness Δ" value={`${p.brightness_delta_pct || 0}%`} />

          <div className="mt-4 border-t border-slate-800 pt-3">
            <div className="text-[9px] text-slate-600 mb-1 font-mono">Inference ms (last 60 cycles)</div>
            <Sparkline data={inferenceHistory} color="#00F5FF" />
          </div>
        </div>

        {/* Prong A/B Breakdown */}
        <div className="bg-[#030B17] border border-slate-800 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3 border-b border-slate-800 pb-2">
            <Layers size={13} className="text-[#94A3B8]" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">Detection Breakdown</h3>
          </div>

          {/* Prong A */}
          <div className="mb-4">
            <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-2">Prong A — Structural</div>
            <div className="flex items-end justify-between mb-1">
              <span className="text-[10px] text-slate-400">Blobs detected</span>
              <span className={`font-mono font-bold text-sm ${(p.prong_a_blobs || 0) > 0 ? 'text-yellow-400' : 'text-slate-600'}`}>
                {p.prong_a_blobs || 0}
              </span>
            </div>
            <div className="flex items-end justify-between mb-1">
              <span className="text-[10px] text-slate-400">Avg blob area</span>
              <span className="font-mono text-xs text-slate-300">{p.prong_a_avg_blob_area || 0} px²</span>
            </div>
            <div className="flex items-end justify-between">
              <span className="text-[10px] text-slate-400">Background mode</span>
              <span className={`font-mono text-xs font-bold ${p.prong_mode === 'CANNY_BG' ? 'text-[#00F5FF]' : 'text-slate-500'}`}>
                {p.prong_mode || '—'}
              </span>
            </div>
            {p.bg_capture_brightness && (
              <div className="flex items-end justify-between mt-1">
                <span className="text-[10px] text-slate-400">BG brightness</span>
                <span className="font-mono text-xs text-slate-400">{p.bg_capture_brightness} ({p.brightness_delta_pct}% Δ)</span>
              </div>
            )}
          </div>

          {/* Prong B */}
          <div className="mb-4">
            <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-2">Prong B — YOLO</div>
            <div className="flex items-end justify-between mb-1">
              <span className="text-[10px] text-slate-400">Raw YOLO dets</span>
              <span className={`font-mono font-bold text-sm ${(p.prong_b_yolo_raw || 0) > 0 ? 'text-orange-400' : 'text-slate-600'}`}>
                {p.prong_b_yolo_raw || 0}
              </span>
            </div>
            <div className="flex items-end justify-between mb-1">
              <span className="text-[10px] text-slate-400">Max confidence</span>
              <div className="flex items-center gap-2">
                <div className="w-20 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-orange-400 rounded-full" style={{ width: `${(p.prong_b_max_conf || 0) * 100}%` }} />
                </div>
                <span className="font-mono text-xs text-orange-400">{((p.prong_b_max_conf || 0) * 100).toFixed(1)}%</span>
              </div>
            </div>
          </div>

          {/* Intersection gate */}
          <div className="border-t border-slate-800 pt-3">
            <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-2">Intersection Gate</div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-400">Final detections</span>
              <span className={`font-mono font-bold text-lg ${(p.intersection_passed || 0) > 0 ? 'text-[#FF3B3B]' : 'text-slate-600'}`}>
                {p.intersection_passed || 0}
              </span>
            </div>
            {(p.intersection_passed || 0) > 0 && (
              <div className="text-[9px] text-[#FF3B3B]/70 mt-1 animate-pulse">⚠ DETECTION ACTIVE THIS CYCLE</div>
            )}
          </div>

          {/* Config in effect */}
          {snap?.active_config && (
            <details className="mt-4 border-t border-slate-800 pt-3">
              <summary className="text-[9px] font-bold text-slate-600 cursor-pointer hover:text-slate-400 uppercase tracking-wider">
                Active Config (click to expand)
              </summary>
              <pre className="mt-2 text-[8px] text-slate-500 font-mono bg-black/30 p-2 rounded overflow-auto max-h-40">
                {JSON.stringify(snap.active_config, null, 2)}
              </pre>
            </details>
          )}
        </div>

        {/* Detection History */}
        <div className="bg-[#030B17] border border-slate-800 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3 border-b border-slate-800 pb-2">
            <Clock size={13} className="text-slate-400" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">Detection History</h3>
            <span className="text-[9px] text-slate-600 font-mono">(last 30 cycles)</span>
          </div>
          <DetectionHistory history={snap?.detection_history} />
        </div>
      </div>

      {/* ── All-nodes pipeline overview ── */}
      {pipelineAll.length > 0 && (
        <div className="bg-[#030B17] border border-slate-800 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3 border-b border-slate-800 pb-2">
            <Activity size={13} className="text-[#00FF9C]" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">All Nodes Health</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px] font-mono">
              <thead>
                <tr className="text-slate-600 border-b border-slate-800">
                  <th className="text-left py-1.5 pr-4">Node</th>
                  <th className="text-right pr-3">Capture</th>
                  <th className="text-right pr-3">Inference</th>
                  <th className="text-right pr-3">FPS</th>
                  <th className="text-right pr-3">Inf ms</th>
                  <th className="text-right pr-3">A blobs</th>
                  <th className="text-right pr-3">B YOLO</th>
                  <th className="text-right pr-3">→ pass</th>
                  <th className="text-right pr-3">Buffer</th>
                  <th className="text-right">Last err</th>
                </tr>
              </thead>
              <tbody>
                {pipelineAll.map(row => {
                  const thr = row.threads || {};
                  const pip = row.pipeline || {};
                  return (
                    <tr key={row.node_id} className="border-b border-slate-900 hover:bg-slate-900/30">
                      <td className="py-1.5 pr-4">
                        <span className={`font-bold ${nodeId === row.node_id ? 'text-[#00F5FF]' : 'text-white'}`}>{row.node_id}</span>
                        <span className="text-slate-600 ml-2">{row.name}</span>
                      </td>
                      <td className={`text-right pr-3 ${thr.capture_health === 'OK' ? 'text-[#00FF9C]' : 'text-[#FF3B3B]'}`}>
                        {thr.capture_health || '—'}
                      </td>
                      <td className={`text-right pr-3 ${thr.inference_health === 'OK' ? 'text-[#00FF9C]' : 'text-[#FF3B3B]'}`}>
                        {thr.inference_health || '—'}
                      </td>
                      <td className="text-right pr-3 text-slate-300">{pip.fps}</td>
                      <td className={`text-right pr-3 ${(pip.inference_ms || 0) > 500 ? 'text-yellow-400' : 'text-slate-400'}`}>
                        {pip.inference_ms?.toFixed(0)}
                      </td>
                      <td className={`text-right pr-3 ${(pip.prong_a_blobs || 0) > 0 ? 'text-yellow-400' : 'text-slate-600'}`}>
                        {pip.prong_a_blobs}
                      </td>
                      <td className={`text-right pr-3 ${(pip.prong_b_yolo_raw || 0) > 0 ? 'text-orange-400' : 'text-slate-600'}`}>
                        {pip.prong_b_yolo_raw}
                      </td>
                      <td className={`text-right pr-3 font-bold ${(pip.intersection_passed || 0) > 0 ? 'text-[#FF3B3B]' : 'text-slate-700'}`}>
                        {pip.intersection_passed}
                      </td>
                      <td className="text-right pr-3 text-slate-500">{pip.buffer_depth}/{pip.buffer_capacity}</td>
                      <td className={`text-right text-[9px] ${row.last_exception ? 'text-[#FF3B3B]' : 'text-slate-700'}`}>
                        {row.last_exception ? `${row.last_exception.type}` : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Exception Log ── */}
      <div className="bg-[#030B17] border border-slate-800 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <Bug size={13} className="text-[#FF3B3B]" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">Exception Log</h3>
            <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${exceptions.length > 0 ? 'bg-[#FF3B3B]/10 text-[#FF3B3B]' : 'bg-slate-800 text-slate-600'}`}>
              {filteredExc.length}
            </span>
          </div>
          <div className="relative">
            <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-600" />
            <input value={excFilter} onChange={e => setExcFilter(e.target.value)}
              placeholder="Filter by node, type, message..."
              className="pl-7 pr-3 py-1.5 bg-[#0F172A] border border-slate-700 rounded text-[10px] text-slate-300 placeholder:text-slate-700 focus:border-[#00F5FF] focus:outline-none w-64 font-mono"
            />
          </div>
        </div>

        {filteredExc.length === 0 ? (
          <div className="text-center text-slate-700 text-xs font-mono py-6 flex flex-col items-center gap-2">
            <CheckCircle size={20} className="text-[#00FF9C]/30" />
            No exceptions logged — pipeline running clean
          </div>
        ) : (
          <div className="flex flex-col gap-2 max-h-80 overflow-y-auto">
            {filteredExc.map((exc, i) => <ExceptionCard key={i} exc={exc} />)}
          </div>
        )}
      </div>

    </div>
  );
}
