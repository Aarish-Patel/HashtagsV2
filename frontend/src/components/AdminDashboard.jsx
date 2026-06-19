import React, { useState, useEffect } from 'react';
import { API_BASE } from '../config';
import DebugPanel from './tabs/DebugPanel';
import AlertTriangle from 'lucide-react/dist/esm/icons/alert-triangle';
import Camera from 'lucide-react/dist/esm/icons/camera';
import Activity from 'lucide-react/dist/esm/icons/activity';
import Settings from 'lucide-react/dist/esm/icons/settings';
import ShieldX from 'lucide-react/dist/esm/icons/shield-x';
import Cpu from 'lucide-react/dist/esm/icons/cpu';
import Server from 'lucide-react/dist/esm/icons/server';
import HardDrive from 'lucide-react/dist/esm/icons/hard-drive';
import Eye from 'lucide-react/dist/esm/icons/eye';
import BellOff from 'lucide-react/dist/esm/icons/bell-off';
import Plus from 'lucide-react/dist/esm/icons/plus';
import Trash2 from 'lucide-react/dist/esm/icons/trash-2';
import Edit3 from 'lucide-react/dist/esm/icons/edit-3';
import Check from 'lucide-react/dist/esm/icons/check';
import X from 'lucide-react/dist/esm/icons/x';
import MapPin from 'lucide-react/dist/esm/icons/map-pin';
import Wifi from 'lucide-react/dist/esm/icons/wifi';
import WifiOff from 'lucide-react/dist/esm/icons/wifi-off';
import Bug from 'lucide-react/dist/esm/icons/bug';

// ─── Field Editors ────────────────────────────────────────────────────────────
function InlineEdit({ value, onSave, type = 'text', placeholder = '', small = false }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const commit = () => {
    if (draft !== value) onSave(draft);
    setEditing(false);
  };

  if (!editing) {
    return (
      <button onClick={() => { setDraft(value); setEditing(true); }}
        className={`flex items-center gap-1 text-left hover:text-white transition-colors group ${small ? 'text-[10px]' : 'text-xs'} text-slate-300`}>
        <span className="truncate max-w-[160px]">{value || <span className="text-slate-600 italic">not set</span>}</span>
        <Edit3 size={9} className="opacity-0 group-hover:opacity-60 shrink-0" />
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <input autoFocus type={type} value={draft}
        onChange={e => setDraft(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') setEditing(false); }}
        placeholder={placeholder}
        className={`bg-[#0F172A] border border-[#00F5FF] rounded px-2 py-0.5 text-white focus:outline-none ${small ? 'text-[10px] w-28' : 'text-xs w-40'}`}
      />
      <button onClick={commit} className="p-0.5 text-[#00FF9C] hover:text-white"><Check size={12} /></button>
      <button onClick={() => setEditing(false)} className="p-0.5 text-slate-500 hover:text-white"><X size={12} /></button>
    </div>
  );
}

// ─── Node Card ────────────────────────────────────────────────────────────────
function NodeCard({ node, onUpdate, onDelete, onSelect, isSelected }) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  const field = (key, val, label, type = 'text') => (
    <div className="flex items-center gap-2">
      <span className="text-[9px] font-bold text-slate-600 uppercase tracking-wider w-10 shrink-0">{label}</span>
      <InlineEdit value={String(val)} onSave={v => onUpdate(key, v)} type={type} small />
    </div>
  );

  return (
    <div onClick={() => onSelect(node.id)}
      className={`border rounded-xl p-3 cursor-pointer transition-all ${
        isSelected
          ? 'border-[#00F5FF] bg-[#00F5FF]/5'
          : 'border-slate-800 bg-black/20 hover:border-slate-600'
      }`}>
      {/* Header row */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full shrink-0 ${node.online ? 'bg-[#00FF9C] shadow-[0_0_6px_#00FF9C]' : 'bg-slate-700'}`} />
          <div>
            <InlineEdit value={node.name} onSave={v => onUpdate('name', v)} placeholder="Node name" />
            <div className="text-[9px] font-mono text-slate-600 mt-0.5">{node.id} · {node.fps?.toFixed(1) ?? 0} fps</div>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {node.online
            ? <Wifi size={12} className="text-[#00FF9C]" />
            : <WifiOff size={12} className="text-slate-600" />}
          {!confirmDelete ? (
            <button onClick={e => { e.stopPropagation(); setConfirmDelete(true); }}
              className="p-1 rounded text-slate-600 hover:text-[#FF3B3B] hover:bg-[#FF3B3B]/10 transition-all">
              <Trash2 size={11} />
            </button>
          ) : (
            <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
              <button onClick={() => onDelete()} className="text-[9px] px-2 py-0.5 bg-[#FF3B3B] text-white rounded font-bold">DELETE</button>
              <button onClick={() => setConfirmDelete(false)} className="text-[9px] px-2 py-0.5 bg-slate-800 text-slate-400 rounded">Cancel</button>
            </div>
          )}
        </div>
      </div>
      {/* Fields */}
      <div className="flex flex-col gap-1.5 mt-1">
        {field('stream_url', node.stream_url || '', 'URL')}
        <div className="flex gap-3">
          {field('lat', node.lat ?? 0, 'LAT', 'number')}
          {field('lng', node.lng ?? 0, 'LNG', 'number')}
        </div>
        <div className="flex items-center gap-2 mt-1">
            <span className="text-[9px] font-bold text-slate-600 uppercase tracking-wider w-10 shrink-0">TRIGGER</span>
            <select value={node.alarm_trigger_type || 'PIR'} onChange={e => onUpdate('alarm_trigger_type', e.target.value)}
              className="bg-[#0F172A] border border-slate-700 rounded px-1 py-0.5 text-white text-[10px] focus:outline-none">
              <option value="PIR">PIR (Instant)</option>
              <option value="DETECTION">DETECTION</option>
            </select>
        </div>
      </div>
      {/* Status badges */}
      <div className="flex gap-1.5 mt-2 flex-wrap">
        <span className={`text-[8px] px-1.5 py-0.5 rounded font-bold ${node.online ? 'bg-[#00FF9C]/10 text-[#00FF9C]' : 'bg-slate-800 text-slate-500'}`}>
          {node.online ? 'ONLINE' : 'OFFLINE'}
        </span>
        {node.has_permanent_bg && (
          <span className="text-[8px] px-1.5 py-0.5 rounded font-bold bg-blue-500/10 text-blue-400">CANNY-BG</span>
        )}
        <span className="text-[8px] px-1.5 py-0.5 rounded font-bold bg-slate-800 text-slate-500">
          {node.clips_saved ?? 0} clips
        </span>
      </div>
    </div>
  );
}

// ─── Add Node Form ────────────────────────────────────────────────────────────
function AddNodeForm({ onAdd, onCancel }) {
  const [form, setForm] = useState({ id: '', name: '', stream_url: '', lat: '', lng: '' });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const valid = form.id.trim() && form.stream_url.trim();

  return (
    <div className="border border-[#00F5FF]/30 bg-[#00F5FF]/5 rounded-xl p-4 flex flex-col gap-3">
      <div className="text-xs font-bold text-[#00F5FF] uppercase tracking-widest">Add New Node</div>
      {[
        { k: 'id', label: 'Node ID', ph: 'HASH-3', req: true },
        { k: 'name', label: 'Name', ph: 'Alpha Post', req: false },
        { k: 'stream_url', label: 'Stream URL', ph: 'http://192.168.x.x/stream', req: true },
        { k: 'lat', label: 'Latitude', ph: '24.165566', req: false },
        { k: 'lng', label: 'Longitude', ph: '94.259984', req: false },
      ].map(({ k, label, ph, req }) => (
        <div key={k}>
          <label className="block text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-1">
            {label}{req && <span className="text-[#FF3B3B] ml-1">*</span>}
          </label>
          <input value={form[k]} onChange={e => set(k, e.target.value)} placeholder={ph}
            className="w-full bg-[#0F172A] border border-slate-700 rounded p-2 text-white text-xs focus:border-[#00F5FF] focus:outline-none font-mono placeholder:text-slate-700"
          />
        </div>
      ))}
      <div className="mb-2">
        <label className="block text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-1">
          Alarm Trigger Type
        </label>
        <select value={form.alarm_trigger_type || 'PIR'} onChange={e => set('alarm_trigger_type', e.target.value)}
          className="w-full bg-[#0F172A] border border-slate-700 rounded p-2 text-white text-xs focus:border-[#00F5FF] focus:outline-none font-mono">
          <option value="PIR">PIR (Instant on Stream Connect)</option>
          <option value="DETECTION">DETECTION (Wait for Inference)</option>
        </select>
      </div>
      <div className="flex gap-2 mt-1">
        <button onClick={() => onAdd(form)} disabled={!valid}
          className="flex-1 bg-[#00F5FF]/10 hover:bg-[#00F5FF]/20 border border-[#00F5FF]/50 text-[#00F5FF] font-bold py-2 rounded text-xs disabled:opacity-30">
          ADD NODE
        </button>
        <button onClick={onCancel} className="px-4 bg-slate-800 text-slate-400 rounded text-xs hover:bg-slate-700">
          Cancel
        </button>
      </div>
    </div>
  );
}

// ─── Main AdminDashboard ───────────────────────────────────────────────────────
export default function AdminDashboard() {
  const [token] = useState('disabled');
  const [nodes, setNodes] = useState([]);
  const [selectedNode, setSelectedNode] = useState('');
  const [activeThreats, setActiveThreats] = useState({});
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('info');
  const [loading, setLoading] = useState(false);
  const [telemetry, setTelemetry] = useState(null);
  const [vizMode, setVizMode] = useState('COMBINED');
  const [fpResult, setFpResult] = useState(null);
  const [showAddNode, setShowAddNode] = useState(false);
  const [nodeConfig, setNodeConfig] = useState({
    person_conf: 0.05, prong_b_weight: 1.0,
    canny_low: 50, canny_high: 150,
    prong_a_threshold: 20, prong_a_weight: 1.0,
    intersection_iou: 0.10, intersection_containment: 0.20,
    min_contour_area: 50, clip_retention_days: 7,
    fp_count: 0, prong_a_fp_score: 0.0, prong_b_fp_score: 0.0,
  });
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [adminTab, setAdminTab] = useState('CONTROL'); // 'CONTROL' | 'DEBUG'

  const authHdr = { 'Authorization': token ? `Bearer ${token}` : '', 'Content-Type': 'application/json' };

  // ── Polling ─────────────────────────────────────────────────────────────────
  const refreshNodes = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/nodes?t=${Date.now()}`);
      if (!res.ok) return;
      setNodes(await res.json());
    } catch (e) {}
  };

  useEffect(() => {
    refreshNodes();
    const fetchTelemetry = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/admin/telemetry`, { headers: authHdr });
        if (!res.ok) return;
        setTelemetry(await res.json());
      } catch (e) {}
    };
    const fetchAnalysis = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/threats/active`, { headers: authHdr });
        if (!res.ok) return;
        const activeThreatsList = await res.json();
        const threats = {};
        activeThreatsList.forEach(t => {
          if (t.threat_count > 0) threats[t.node_id] = true;
        });
        // Still checking for analyzing jobs might be needed if they are still relevant
        const jobRes = await fetch(`${API_BASE}/api/analyze/all`);
        if (jobRes.ok) {
          const jobData = await jobRes.json();
          (jobData.jobs || []).forEach(j => {
             if (j.status === 'ANALYZING' && !threats[j.node_id]) threats[j.node_id] = 'analyzing';
          });
        }
        setActiveThreats(threats);
      } catch (e) {}
    };
    fetchTelemetry(); fetchAnalysis();
    const t1 = setInterval(refreshNodes, 5000);
    const t2 = setInterval(fetchTelemetry, 2000);
    const t3 = setInterval(fetchAnalysis, 1000);
    return () => { clearInterval(t1); clearInterval(t2); clearInterval(t3); };
  }, []);

  // ── Load config when node selected ──────────────────────────────────────────
  useEffect(() => {
    if (!selectedNode) return;
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/admin/node_config/${selectedNode}`, { headers: authHdr });
        if (!res.ok) return;
        setNodeConfig(await res.json());
        setHasUnsavedChanges(false);
        setFpResult(null);
        // Sync viz mode from node info
        const nodeInfo = nodes.find(n => n.id === selectedNode);
        if (nodeInfo?.viz_mode) setVizMode(nodeInfo.viz_mode);
      } catch (e) {}
    };
    load();

    const handleUpdate = () => load();
    window.addEventListener('configUpdated', handleUpdate);
    return () => window.removeEventListener('configUpdated', handleUpdate);
  }, [selectedNode, nodes]);

  const showMsg = (msg, type = 'info') => {
    setMessage(msg); setMessageType(type);
    setTimeout(() => setMessage(''), 5000);
  };

  // ── Node CRUD ────────────────────────────────────────────────────────────────
  const handleUpdateNodeField = async (node_id, key, value) => {
    try {
      const res = await fetch(`${API_BASE}/api/nodes/${node_id}`, {
        method: 'PATCH', headers: authHdr,
        body: JSON.stringify({ [key]: value })
      });
      const data = await res.json();
      if (data.error) { showMsg(`Error: ${data.error}`, 'warn'); return; }
      showMsg(`${node_id}: ${key} updated`, 'ok');
      await refreshNodes();
    } catch (e) { showMsg('Update failed', 'warn'); }
  };

  const handleDeleteNode = async (node_id) => {
    try {
      const res = await fetch(`${API_BASE}/api/nodes/${node_id}`, { method: 'DELETE', headers: authHdr });
      const data = await res.json();
      showMsg(data.message || 'Node deleted', 'ok');
      if (selectedNode === node_id) setSelectedNode('');
      await refreshNodes();
    } catch (e) { showMsg('Delete failed', 'warn'); }
  };

  const handleAddNode = async (form) => {
    try {
      const res = await fetch(`${API_BASE}/api/nodes/add`, {
        method: 'POST', headers: authHdr,
        body: JSON.stringify({
          id: form.id.trim(),
          stream_url: form.stream_url.trim(),
          name: form.name.trim() || form.id.trim(),
          lat: parseFloat(form.lat) || 0,
          lng: parseFloat(form.lng) || 0,
          alarm_trigger_type: form.alarm_trigger_type || 'PIR',
        })
      });
      const data = await res.json();
      if (data.error) { showMsg(`Error: ${data.error}`, 'warn'); return; }
      showMsg(`Node ${form.id} added`, 'ok');
      setShowAddNode(false);
      await refreshNodes();
    } catch (e) { showMsg('Add failed', 'warn'); }
  };

  // ── Admin actions ─────────────────────────────────────────────────────────
  const post = async (url, body = null) => {
    const res = await fetch(`${API_BASE}${url}`, {
      method: 'POST', headers: authHdr,
      body: body ? JSON.stringify(body) : undefined
    });
    return res.json();
  };

  const handleSetVizMode = async (mode) => {
    if (!selectedNode) return;
    setVizMode(mode);
    await post(`/api/admin/set_viz_mode/${selectedNode}`, { mode });
    showMsg(`Viz → ${mode}`, 'ok');
  };

  const handleFalsePositive = async () => {
    if (!selectedNode) return; setLoading(true); setFpResult(null);
    try {
      const data = await post(`/api/admin/false_positive/${selectedNode}`);
      setFpResult(data);
      showMsg(`FP logged — ${data.blame} blamed`, 'warn');
      const cfgRes = await fetch(`${API_BASE}/api/admin/node_config/${selectedNode}`, { headers: authHdr });
      if (cfgRes.ok) setNodeConfig(await cfgRes.json());
    } catch (e) { showMsg('Error reporting FP', 'warn'); }
    setLoading(false);
  };

  const handleAcknowledge = async () => {
    if (!selectedNode) return; setLoading(true);
    try { const d = await post(`/api/admin/acknowledge/${selectedNode}`); showMsg(d.message, 'ok'); }
    catch (e) { showMsg('Error', 'warn'); }
    setLoading(false);
  };

  const handleSetBackground = async () => {
    if (!selectedNode) return; setLoading(true);
    try { const d = await post(`/api/admin/set_background/${selectedNode}`); showMsg(d.message, 'ok'); }
    catch (e) { showMsg('Error', 'warn'); }
    setLoading(false);
  };

  const handleClearBackground = async () => {
    if (!selectedNode) return; setLoading(true);
    try { const d = await post(`/api/admin/clear_bg/${selectedNode}`); showMsg(d.message, 'info'); }
    catch (e) { showMsg('Error', 'warn'); }
    setLoading(false);
  };

  const handleSimulateThreat = async () => {
    if (!selectedNode) return; setLoading(true);
    try { const d = await post(`/api/admin/simulate_threat/${selectedNode}`); showMsg(d.message, 'warn'); }
    catch (e) { showMsg('Error', 'warn'); }
    setLoading(false);
  };

  const saveConfig = async (cfg = nodeConfig) => {
    if (!selectedNode) return; setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/node_config/${selectedNode}`, {
        method: 'POST', headers: authHdr, body: JSON.stringify(cfg)
      });
      const data = await res.json();
      if (data.config) { setNodeConfig(data.config); setHasUnsavedChanges(false); }
      showMsg('Tuning saved.', 'ok');
    } catch (e) { showMsg('Error saving', 'warn'); }
    setLoading(false);
  };

  const slider = (label, key, min, max, step, color = '#00F5FF', note = '') => (
    <div key={key}>
      <div className="flex justify-between items-center text-xs mb-1">
        <span className="text-slate-400">{label}</span>
        <input type="number" min={min} max={max} step={step} value={nodeConfig[key]}
          onChange={e => {
             let val = step < 1 ? parseFloat(e.target.value) : parseInt(e.target.value);
             if (isNaN(val)) val = min;
             setNodeConfig({ ...nodeConfig, [key]: val });
             setHasUnsavedChanges(true);
          }}
          className="w-16 bg-[#020617] text-right font-mono border border-slate-700 rounded px-1 py-0.5 text-xs focus:border-[#00F5FF] focus:outline-none"
          style={{ color }}
        />
      </div>
      <input type="range" min={min} max={max} step={step} value={nodeConfig[key]}
        onChange={e => { setNodeConfig({ ...nodeConfig, [key]: step < 1 ? parseFloat(e.target.value) : parseInt(e.target.value) }); setHasUnsavedChanges(true); }}
        className="w-full" style={{ accentColor: color }} />
      {note && <p className="text-[9px] text-slate-600 mt-0.5">{note}</p>}
    </div>
  );

  const msgStyle = { info: 'border-slate-600 text-white', warn: 'border-yellow-500/50 text-yellow-400', ok: 'border-[#00FF9C]/50 text-[#00FF9C]' };
  const vizModes = [
    { id: 'COMBINED', label: 'INTERSECTION', desc: 'Final validated detections only' },
    { id: 'PRONG_A', label: 'PRONG A (HEATMAP)', desc: 'Raw structural discrepancy overlay' },
    { id: 'PRONG_B', label: 'PRONG B (YOLO RAW)', desc: 'All YOLO detections before filtering' },
  ];
  const formatUptime = s => {
    if (!s) return '00:00:00';
    return `${String(Math.floor(s/3600)).padStart(2,'0')}:${String(Math.floor((s%3600)/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;
  };

  const selectedNodeInfo = nodes.find(n => n.id === selectedNode);

  return (
    <div className="h-screen overflow-hidden bg-[#020617] text-slate-300 font-sans p-4 lg:p-6 flex flex-col">
      <header className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6 shrink-0">
        <div className="flex items-center gap-3">
          <Settings className="text-[#00F5FF] w-7 h-7" />
          <h1 className="text-xl font-bold tracking-widest text-white uppercase">System Admin Console</h1>
        </div>
        <div className="text-xs tracking-widest text-slate-500 flex items-center gap-4">
          {telemetry && <span className="text-[#00FF9C]">UPTIME: {formatUptime(telemetry.uptime_sec)}</span>}
          <span className="uppercase">Hashtag V2</span>
        </div>
      </header>

      {/* ── Tab bar ── */}
      <div className="flex gap-1 mb-4 border-b border-slate-800 pb-0 shrink-0">
        {[
          { id: 'CONTROL', label: 'Control Panel', Icon: Settings },
          { id: 'DEBUG',   label: 'Live Debug',    Icon: Bug, accent: '#FF3B3B' },
        ].map(({ id, label, Icon, accent }) => (
          <button key={id} onClick={() => setAdminTab(id)}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-bold uppercase tracking-widest border-b-2 transition-all ${
              adminTab === id
                ? 'border-current text-white'
                : 'border-transparent text-slate-600 hover:text-slate-400'
            }`}
            style={adminTab === id && accent ? { borderColor: accent, color: accent } : {}}>
            <Icon size={12} />{label}
          </button>
        ))}
      </div>

      {adminTab === 'DEBUG' ? (
        <div className="flex gap-4 flex-1 min-h-0">
          {/* Compact node selector for debug mode */}
          <div className="w-56 shrink-0 bg-[#030B17] border border-slate-800 rounded-xl p-3 h-full overflow-y-auto custom-scrollbar">
            <div className="text-[9px] font-bold text-slate-600 uppercase tracking-widest mb-2">Select Node</div>
            <div className="flex flex-col gap-1.5">
              {nodes.map(n => (
                <button key={n.id} onClick={() => setSelectedNode(n.id)}
                  className={`flex items-center gap-2 px-2.5 py-2 rounded-lg text-left transition-all ${
                    selectedNode === n.id
                      ? 'bg-[#FF3B3B]/10 border border-[#FF3B3B]/30 text-white'
                      : 'bg-slate-900/50 border border-transparent text-slate-400 hover:border-slate-700 hover:text-white'
                  }`}>
                  <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${n.online ? 'bg-[#00FF9C]' : 'bg-slate-700'}`} />
                  <div>
                    <div className="text-xs font-bold">{n.id}</div>
                    <div className="text-[9px] text-slate-600 truncate">{n.name}</div>
                  </div>
                </button>
              ))}
              {nodes.length === 0 && <div className="text-slate-700 text-[10px] font-mono">No nodes loaded</div>}
            </div>
          </div>
          <div className="flex-1 min-w-0 h-full overflow-hidden">
            <DebugPanel nodeId={selectedNode} nodes={nodes} />
          </div>
        </div>
      ) : (
      <div className="max-w-[1800px] mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 min-h-0">

        {/* ── COL 1: Node Manager (3/12) ── */}
        <div className="lg:col-span-3 flex flex-col gap-4 h-full min-h-0">
          <div className="bg-[#030B17] border border-slate-800 rounded-xl p-4 flex flex-col h-full">
            <div className="flex items-center justify-between mb-3 shrink-0">
              <h2 className="text-xs font-bold text-white uppercase tracking-widest flex items-center gap-2">
                <MapPin size={13} className="text-[#00F5FF]" /> Field Nodes
              </h2>
              <button onClick={() => setShowAddNode(v => !v)}
                className="flex items-center gap-1 px-2 py-1 text-[9px] font-bold text-[#00F5FF] border border-[#00F5FF]/40 rounded hover:bg-[#00F5FF]/10 transition-all">
                <Plus size={11} /> ADD
              </button>
            </div>

            {showAddNode && (
              <div className="mb-3 shrink-0">
                <AddNodeForm onAdd={handleAddNode} onCancel={() => setShowAddNode(false)} />
              </div>
            )}

            <div className="flex flex-col gap-3 overflow-y-auto flex-1 pr-2 custom-scrollbar">
              {nodes.length === 0 && (
                <div className="text-slate-600 text-xs text-center py-4 font-mono">No nodes loaded yet...</div>
              )}
              {nodes.map(node => (
                <NodeCard key={node.id} node={node}
                  isSelected={selectedNode === node.id}
                  onSelect={setSelectedNode}
                  onUpdate={(key, value) => handleUpdateNodeField(node.id, key, value)}
                  onDelete={() => handleDeleteNode(node.id)}
                />
              ))}
            </div>
          </div>
        </div>

        {/* ── COL 2: Video Monitor + Tuning (6/12) ── */}
        <div className="lg:col-span-6 flex flex-col gap-4 h-full min-h-0 overflow-y-auto custom-scrollbar pr-2">

          {/* Video */}
          <div className="bg-[#000] border-2 border-slate-800 rounded-xl overflow-hidden relative min-h-[420px] flex items-center justify-center shrink-0">
            {selectedNode ? (
              <>
                <div className="absolute top-3 right-3 z-10 bg-black/50 backdrop-blur border border-white/10 px-3 py-1.5 rounded flex flex-col items-end pointer-events-none">
                  <span className="text-white font-black tracking-widest text-sm">{selectedNodeInfo?.name || selectedNode}</span>
                  {selectedNodeInfo && (
                    <span className="text-slate-400 font-mono text-[9px] mt-1">
                      {selectedNodeInfo.fps?.toFixed(1)} FPS | {selectedNodeInfo.has_permanent_bg ? 'CANNY-BG' : 'MOG2'}
                    </span>
                  )}
                </div>
                {activeThreats[selectedNode] === true && (
                  <div className="absolute inset-0 pointer-events-none z-10">
                    <div className="absolute inset-0 border-4 border-[#FF3B3B] animate-pulse" />
                    <div className="absolute top-3 left-3 bg-[#FF3B3B] text-white px-3 py-1 font-bold tracking-widest text-xs uppercase animate-pulse">
                      ⚠ THREAT DETECTED
                    </div>
                  </div>
                )}
                <img key={selectedNode} src={`${API_BASE}/video_feed/${selectedNode}`}
                  alt={`Feed ${selectedNode}`} className="w-full h-full object-contain"
                  onError={e => { e.target.style.display = 'none'; }}
                  onLoad={e => { e.target.style.display = 'block'; }}
                />
              </>
            ) : (
              <div className="text-slate-700 font-mono tracking-widest uppercase text-sm">Select a Node</div>
            )}
          </div>

          {/* Tuning */}
          <div className="bg-[#030B17] border border-slate-800 rounded-xl p-4 shrink-0">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xs font-bold text-white uppercase tracking-widest">Sensitivity Tuning</h3>
              {hasUnsavedChanges && <span className="text-[9px] text-yellow-500 animate-pulse font-bold">UNSAVED</span>}
            </div>
            <div className="grid grid-cols-2 gap-x-6 gap-y-3">
              <div>
                <div className="text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-2">Prong B — YOLO</div>
                {slider('Confidence', 'person_conf', 0.01, 1.0, 0.01, '#00F5FF')}
                {slider('YOLO Weight', 'prong_b_weight', 0.1, 3.0, 0.1, '#00F5FF')}
              </div>
              <div>
                <div className="text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-2">Prong A — Structural</div>
                {slider('Edge Threshold', 'prong_a_threshold', 5, 80, 1, '#94A3B8')}
                {slider('Prong A Weight', 'prong_a_weight', 0.1, 3.0, 0.1, '#94A3B8')}
                {slider('Min Blob (px²)', 'min_contour_area', 20, 307200, 100, '#94A3B8')}
              </div>
              <div>
                <div className="text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-2">Intersection Gate</div>
                {slider('Min IoU', 'intersection_iou', 0.01, 0.50, 0.01, '#475569')}
                {slider('Min Containment', 'intersection_containment', 0.05, 0.50, 0.05, '#475569')}
              </div>
              <div>
                <div className="text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-2">Canny</div>
                {slider('Canny Low', 'canny_low', 10, 100, 10, '#64748B')}
                {slider('Canny High', 'canny_high', 100, 300, 10, '#64748B')}
              </div>
              <div className="col-span-2 mt-2">
                <div className="text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-2">Display Mode (Diagnostic)</div>
                <div className="flex gap-2">
                  {vizModes.map(m => (
                    <button key={m.id} onClick={() => handleSetVizMode(m.id)}
                      className={`flex-1 text-center px-2 py-1.5 rounded border text-[9px] font-bold tracking-widest uppercase transition-all ${
                        vizMode === m.id
                          ? 'bg-[#00F5FF]/10 border-[#00F5FF]/40 text-[#00F5FF]'
                          : 'bg-black/30 border-slate-800 text-slate-500 hover:text-slate-300'
                      }`}>
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <button onClick={() => saveConfig()} disabled={!hasUnsavedChanges || !selectedNode || loading}
              className="mt-4 w-full bg-[#00F5FF]/10 hover:bg-[#00F5FF]/20 border border-[#00F5FF]/50 text-[#00F5FF] font-bold py-2 rounded text-xs disabled:opacity-30">
              SAVE TUNING TO DISK
            </button>
          </div>
        </div>

        {/* ── COL 3: Actions + Telemetry (3/12) ── */}
        <div className="lg:col-span-3 flex flex-col gap-4 h-full min-h-0 overflow-y-auto custom-scrollbar pr-2">

          {/* Actions */}
          <div className="bg-[#030B17] border border-slate-800 rounded-xl p-4 flex flex-col gap-2">
            <h3 className="text-xs font-bold text-white uppercase tracking-widest mb-2">Actions</h3>

            <button onClick={handleFalsePositive} disabled={!selectedNode || loading}
              className="flex items-center justify-center gap-2 w-full bg-yellow-500/10 hover:bg-yellow-500/20 border border-yellow-500/40 text-yellow-400 font-bold py-2 px-3 rounded text-xs transition-colors disabled:opacity-50">
              <ShieldX size={13} /> REPORT FALSE POSITIVE
            </button>

            {fpResult && (
              <div className={`text-[10px] p-2 rounded border font-mono ${fpResult.blame === 'PRONG_B' ? 'border-orange-500/30 bg-orange-500/10 text-orange-300' : fpResult.blame === 'PRONG_A' ? 'border-slate-500/30 bg-slate-500/10 text-slate-300' : 'border-yellow-500/30 bg-yellow-500/10 text-yellow-300'}`}>
                <div className="font-bold mb-1">⚡ {fpResult.blame} BLAMED</div>
                <div>{fpResult.action}</div>
                <div className="text-[9px] mt-1 opacity-70">{fpResult.reason}</div>
              </div>
            )}

            {nodeConfig.fp_count > 0 && (
              <div className="text-[9px] font-mono bg-black/30 border border-slate-800 rounded p-2">
                <div className="text-slate-400 font-bold mb-1">FP History ({nodeConfig.fp_count})</div>
                <div className="flex justify-between"><span className="text-orange-400">Prong B score:</span><span>{nodeConfig.prong_b_fp_score.toFixed(1)}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Prong A score:</span><span>{nodeConfig.prong_a_fp_score.toFixed(1)}</span></div>
              </div>
            )}

            <hr className="border-slate-800 my-1" />

            <button onClick={handleAcknowledge} disabled={!selectedNode || loading}
              className="flex items-center justify-center gap-2 w-full bg-[#00FF9C]/10 hover:bg-[#00FF9C]/20 border border-[#00FF9C]/40 text-[#00FF9C] font-bold py-2 px-3 rounded text-xs disabled:opacity-50">
              <BellOff size={13} /> ACKNOWLEDGE ALARM
            </button>

            <button onClick={handleSetBackground} disabled={!selectedNode || loading}
              className="flex items-center justify-center gap-2 w-full bg-slate-800 hover:bg-slate-700 text-white font-bold py-2 px-3 rounded text-sm disabled:opacity-50">
              <Camera className="w-4 h-4 text-[#00FF9C]" /> Capture Background
            </button>

            <button onClick={handleClearBackground} disabled={!selectedNode || loading}
              className="flex items-center justify-center gap-2 w-full bg-slate-800/50 hover:bg-slate-700 text-slate-400 font-bold py-2 px-3 rounded text-sm disabled:opacity-50">
              Revert to MOG2
            </button>

            <button onClick={handleSimulateThreat} disabled={!selectedNode || loading}
              className="flex items-center justify-center gap-2 w-full bg-[#FF3B3B]/10 hover:bg-[#FF3B3B]/20 border border-[#FF3B3B]/50 text-[#FF3B3B] font-bold py-2 px-3 rounded text-sm mt-1 disabled:opacity-50">
              <AlertTriangle className="w-4 h-4" /> Simulate Threat
            </button>

            <button onClick={() => { if(window.confirm('PERMANENTLY DELETE THIS NODE? This will archive all its clips and remove it from the system.')) handleDeleteNode(selectedNode); }} disabled={!selectedNode || loading}
              className="flex items-center justify-center gap-2 w-full bg-red-900/30 hover:bg-red-800/50 border border-red-700/50 text-red-400 font-bold py-2 px-3 rounded text-xs mt-4 disabled:opacity-50">
              <Trash2 size={13} /> PERMANENTLY DELETE NODE
            </button>

            {message && (
              <div className={`p-3 bg-slate-800 border text-xs rounded text-center font-mono ${msgStyle[messageType]}`}>
                {message}
              </div>
            )}
          </div>

          {/* System Health */}
          <div className="bg-[#030B17] border border-slate-800 rounded-xl p-4 flex flex-col gap-4">
            <h3 className="text-xs font-bold text-white uppercase tracking-widest flex items-center gap-2 border-b border-slate-800 pb-3">
              <Activity className="text-[#00FF9C] w-4 h-4" /> System Health
            </h3>
            {telemetry ? (
              <>
                {[
                  { label: 'CPU', icon: Cpu, val: `${telemetry.cpu_pct?.toFixed(1)}%`, pct: telemetry.cpu_pct, color: telemetry.cpu_pct > 85 ? '#FF3B3B' : '#00F5FF' },
                  { label: 'RAM', icon: Server, val: `${telemetry.ram_used_gb} / ${telemetry.ram_total_gb} GB`, pct: telemetry.ram_pct, color: telemetry.ram_pct > 85 ? '#FF3B3B' : '#00FF9C' },
                  { label: 'VRAM', icon: Server, val: `${telemetry.gpu_used_mb} MB`, pct: telemetry.gpu_total_mb > 0 ? telemetry.gpu_used_mb / telemetry.gpu_total_mb * 100 : 0, color: '#a855f7' },
                ].map(m => (
                  <div key={m.label}>
                    <div className="flex justify-between text-xs mb-1 font-mono">
                      <span className="text-slate-400 flex items-center gap-1"><m.icon size={11} />{m.label}</span>
                      <span style={{ color: m.color }}>{m.val}</span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${Math.min(100, m.pct)}%`, backgroundColor: m.color }} />
                    </div>
                  </div>
                ))}
                <div className="flex justify-between text-xs font-mono">
                  <span className="flex items-center gap-1 text-slate-400"><HardDrive size={11} />Disk</span>
                  <span>{telemetry.disk_used_gb} / {(telemetry.disk_free_gb + telemetry.disk_used_gb).toFixed(1)} GB</span>
                </div>

                <hr className="border-slate-800" />
                <div>
                  <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-2">Clip Retention</div>
                  <div className="flex gap-2 items-center">
                    <input type="number" min="1" max="90"
                      value={nodeConfig.clip_retention_days}
                      onChange={e => { setNodeConfig({ ...nodeConfig, clip_retention_days: parseInt(e.target.value) }); setHasUnsavedChanges(true); }}
                      className="w-16 bg-[#0F172A] border border-slate-700 rounded p-1 text-white text-center text-sm focus:border-[#00F5FF] focus:outline-none font-mono"
                    />
                    <span className="text-xs text-slate-500">days</span>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-slate-600 font-mono text-xs">Loading telemetry...</div>
            )}
          </div>
        </div>

      </div>
      )} {/* end adminTab ternary */}
    </div>
  );
}
