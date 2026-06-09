import React, { useState, useEffect, useRef } from 'react';
import { API_BASE } from '../config';
import AlertTriangle from 'lucide-react/dist/esm/icons/alert-triangle';
import Camera from 'lucide-react/dist/esm/icons/camera';
import ShieldAlert from 'lucide-react/dist/esm/icons/shield-alert';
import Activity from 'lucide-react/dist/esm/icons/activity';
import Settings from 'lucide-react/dist/esm/icons/settings';
import ShieldX from 'lucide-react/dist/esm/icons/shield-x';
import Cpu from 'lucide-react/dist/esm/icons/cpu';
import Server from 'lucide-react/dist/esm/icons/server';
import HardDrive from 'lucide-react/dist/esm/icons/hard-drive';

export default function AdminDashboard() {
  const [nodes, setNodes] = useState([]);
  const [selectedNode, setSelectedNode] = useState('');
  const [activeThreats, setActiveThreats] = useState({});
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [telemetry, setTelemetry] = useState(null);
  
  // Node config state
  const [nodeConfig, setNodeConfig] = useState({
    person_conf: 0.35,
    canny_low: 50,
    canny_high: 150,
    clip_retention_days: 7
  });

  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Poll for telemetry and threats
  useEffect(() => {
    const fetchTelemetry = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/admin/telemetry`);
        const data = await res.json();
        setTelemetry(data);
        
        // Update nodes list if it changed
        const liveNodes = Object.keys(data.nodes || {}).map(id => ({
          id, name: id, ...data.nodes[id]
        }));
        setNodes(liveNodes);
        
        if (!selectedNode && liveNodes.length > 0) {
          setSelectedNode(liveNodes[0].id);
        }
      } catch (e) {
        console.error("Telemetry fetch failed", e);
      }
    };

    const fetchAnalysis = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/analyze/all`);
        const data = await res.json();
        const currentThreats = {};
        (data.jobs || []).forEach(job => {
            if (job.status === 'COMPLETE' && job.threat_detected) {
                currentThreats[job.node_id] = true;
            } else if (job.status === 'ANALYZING') {
                currentThreats[job.node_id] = 'analyzing';
            }
        });
        setActiveThreats(currentThreats);
      } catch (e) { }
    };

    fetchTelemetry();
    fetchAnalysis();
    
    const t1 = setInterval(fetchTelemetry, 2000);
    const t2 = setInterval(fetchAnalysis, 1000);
    return () => { clearInterval(t1); clearInterval(t2); };
  }, [selectedNode]);

  // Load config when node changes
  useEffect(() => {
    if (!selectedNode) return;
    const fetchConfig = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/admin/node_config/${selectedNode}`);
        const data = await res.json();
        setNodeConfig(data);
        setHasUnsavedChanges(false);
      } catch (e) {
        console.error("Failed to load node config", e);
      }
    };
    fetchConfig();
  }, [selectedNode]);

  const showMessage = (msg) => {
    setMessage(msg);
    setTimeout(() => setMessage(''), 3000);
  };

  const handleSimulateThreat = async () => {
    if (!selectedNode) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/simulate_threat/${selectedNode}`, { method: 'POST' });
      const data = await res.json();
      showMessage(data.message);
    } catch (e) { showMessage('Error triggering threat'); }
    setLoading(false);
  };

  const handleSetBackground = async () => {
    if (!selectedNode) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/set_background/${selectedNode}`, { method: 'POST' });
      const data = await res.json();
      showMessage(data.message);
    } catch (e) { showMessage('Error setting background'); }
    setLoading(false);
  };

  const handleClearBackground = async () => {
    if (!selectedNode) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/clear_bg/${selectedNode}`, { method: 'POST' });
      const data = await res.json();
      showMessage(data.message);
    } catch (e) { showMessage('Error clearing background'); }
    setLoading(false);
  };

  const saveConfig = async (newConfig = nodeConfig) => {
    if (!selectedNode) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/node_config/${selectedNode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
      });
      const data = await res.json();
      setNodeConfig(data.config);
      setHasUnsavedChanges(false);
      showMessage('Tuning saved to disk.');
    } catch (e) { showMessage('Error saving tuning'); }
    setLoading(false);
  };

  const reportFalsePositive = () => {
    const newConf = Math.min(0.95, nodeConfig.person_conf + 0.05);
    const updated = { ...nodeConfig, person_conf: newConf };
    setNodeConfig(updated);
    saveConfig(updated);
    showMessage(`False positive logged. Confidence raised to ${newConf.toFixed(2)}`);
  };

  const formatUptime = (seconds) => {
    if (!seconds) return '00:00:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen bg-[#020617] text-slate-300 font-sans p-6 flex flex-col">
      <header className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
        <div className="flex items-center gap-3">
          <Settings className="text-[#00F5FF] w-8 h-8" />
          <h1 className="text-2xl font-bold tracking-widest text-white">SYSTEM ADMIN CONSOLE</h1>
        </div>
        <div className="text-xs tracking-widest text-slate-500 uppercase flex items-center gap-4">
           {telemetry && (
              <span className="text-[#00FF9C]">UPTIME: {formatUptime(telemetry.uptime_sec)}</span>
           )}
          <span>Hashtag V2 Surveillance</span>
        </div>
      </header>

      <div className="max-w-[1600px] mx-auto w-full grid grid-cols-1 lg:grid-cols-4 gap-6">
        
        {/* Left Panel: Controls Sidebar */}
        <div className="bg-[#030B17] border border-slate-800 rounded-xl p-6 flex flex-col gap-6">
          
          <div>
            <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
              Select Camera Node
            </label>
            <select
              value={selectedNode}
              onChange={(e) => setSelectedNode(e.target.value)}
              className="w-full bg-[#0F172A] border border-slate-700 rounded-lg p-3 text-white focus:border-[#00F5FF] focus:outline-none appearance-none font-mono"
            >
              <option value="" disabled>-- Select Node --</option>
              {nodes.map(node => (
                <option key={node.id} value={node.id}>
                  {node.id} {activeThreats[node.id] === true ? ' [⚠]' : ''} {node.online ? '' : '(OFFLINE)'}
                </option>
              ))}
            </select>
          </div>

          <hr className="border-slate-800" />

          {/* PER-NODE TUNING */}
          <div className="flex flex-col gap-4">
             <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-[#00F5FF] uppercase tracking-widest">Tuning</h3>
                {hasUnsavedChanges && <span className="text-[10px] text-yellow-500 animate-pulse font-bold">UNSAVED</span>}
             </div>
             
             <div>
                <div className="flex justify-between text-xs mb-1">
                   <span>YOLO Confidence</span>
                   <span className="text-[#00F5FF] font-mono">{Number(nodeConfig.person_conf).toFixed(2)}</span>
                </div>
                <input 
                  type="range" min="0.05" max="0.80" step="0.05"
                  value={nodeConfig.person_conf}
                  onChange={e => { setNodeConfig({...nodeConfig, person_conf: parseFloat(e.target.value)}); setHasUnsavedChanges(true); }}
                  className="w-full accent-[#00F5FF]"
                />
             </div>

             <div>
                <div className="flex justify-between text-xs mb-1">
                   <span>Canny Edge Low</span>
                   <span className="text-slate-400 font-mono">{nodeConfig.canny_low}</span>
                </div>
                <input 
                  type="range" min="10" max="100" step="10"
                  value={nodeConfig.canny_low}
                  onChange={e => { setNodeConfig({...nodeConfig, canny_low: parseInt(e.target.value)}); setHasUnsavedChanges(true); }}
                  className="w-full accent-slate-500"
                />
             </div>

             <div>
                <div className="flex justify-between text-xs mb-1">
                   <span>Canny Edge High</span>
                   <span className="text-slate-400 font-mono">{nodeConfig.canny_high}</span>
                </div>
                <input 
                  type="range" min="100" max="300" step="10"
                  value={nodeConfig.canny_high}
                  onChange={e => { setNodeConfig({...nodeConfig, canny_high: parseInt(e.target.value)}); setHasUnsavedChanges(true); }}
                  className="w-full accent-slate-500"
                />
             </div>

             <div className="flex gap-2 mt-2">
                <button 
                  onClick={() => saveConfig()}
                  disabled={!hasUnsavedChanges || loading}
                  className="flex-1 bg-[#00F5FF]/10 hover:bg-[#00F5FF]/20 border border-[#00F5FF]/50 text-[#00F5FF] font-bold py-2 rounded text-xs transition-colors disabled:opacity-30"
                >
                  SAVE TO DISK
                </button>
                <button 
                  onClick={reportFalsePositive}
                  disabled={loading}
                  className="flex-1 flex items-center justify-center gap-1 bg-yellow-500/10 hover:bg-yellow-500/20 border border-yellow-500/50 text-yellow-500 font-bold py-2 rounded text-[10px] transition-colors"
                  title="Increases confidence by 0.05 to filter noise"
                >
                  <ShieldX size={12}/>
                  FALSE POSITIVE
                </button>
             </div>
          </div>

          <hr className="border-slate-800" />

          {/* ACTIONS */}
          <div className="flex flex-col gap-3">
            <h3 className="text-sm font-bold text-white uppercase tracking-widest mb-1">Actions</h3>
            
            <button
              onClick={handleSetBackground}
              disabled={!selectedNode || loading}
              className="flex items-center justify-center gap-2 w-full bg-slate-800 hover:bg-slate-700 text-white font-bold py-2 px-4 rounded text-sm transition-colors disabled:opacity-50"
            >
              <Camera className="w-4 h-4 text-[#00FF9C]" />
              Capture Background
            </button>

            <button
              onClick={handleClearBackground}
              disabled={!selectedNode || loading}
              className="flex items-center justify-center gap-2 w-full bg-slate-800/50 hover:bg-slate-700 text-slate-400 font-bold py-2 px-4 rounded text-sm transition-colors disabled:opacity-50"
            >
              Revert to MOG2
            </button>

            <button
              onClick={handleSimulateThreat}
              disabled={!selectedNode || loading}
              className="flex items-center justify-center gap-2 w-full bg-[#FF3B3B]/10 hover:bg-[#FF3B3B]/20 border border-[#FF3B3B]/50 text-[#FF3B3B] font-bold py-2 px-4 rounded text-sm transition-colors mt-2 disabled:opacity-50"
            >
              <AlertTriangle className="w-4 h-4" />
              Simulate Threat
            </button>
          </div>

          {message && (
            <div className="mt-auto p-3 bg-slate-800 border border-slate-600 text-white text-xs rounded text-center font-mono">
              {message}
            </div>
          )}
        </div>

        {/* Center Panel: Video Feed Monitor */}
        <div className="lg:col-span-2 bg-[#000] border-2 border-slate-800 rounded-xl overflow-hidden relative min-h-[500px] flex items-center justify-center">
          
          {selectedNode ? (
            <>
              {/* Overlays */}
              <div className="absolute top-4 right-4 z-10 bg-black/50 backdrop-blur border border-white/10 px-3 py-1.5 rounded flex flex-col items-end pointer-events-none">
                 <span className="text-white font-black tracking-widest text-sm">{selectedNode}</span>
                 <span className="text-[#00F5FF] font-mono text-[10px]">CONF: {Number(nodeConfig.person_conf).toFixed(2)}</span>
                 {telemetry?.nodes?.[selectedNode] && (
                    <span className="text-slate-400 font-mono text-[9px] mt-1">
                       {telemetry.nodes[selectedNode].fps.toFixed(1)} FPS | BG: {telemetry.nodes[selectedNode].has_permanent_bg ? 'CANNY' : 'MOG2'}
                    </span>
                 )}
              </div>

              {activeThreats[selectedNode] === true && (
                <div className="absolute inset-0 pointer-events-none z-10">
                   <div className="absolute inset-0 border-4 border-[#FF3B3B] animate-pulse"></div>
                   <div className="absolute top-4 left-4 bg-[#FF3B3B] text-white px-3 py-1 font-bold tracking-widest text-xs uppercase animate-pulse">
                     THREAT DETECTED
                   </div>
                </div>
              )}
              {activeThreats[selectedNode] === 'analyzing' && (
                <div className="absolute top-4 left-4 z-10 bg-[#FFD60A] text-black px-3 py-1 font-bold tracking-widest text-xs uppercase">
                  ANALYZING BUFFER...
                </div>
              )}
              
              <img 
                key={selectedNode}
                src={`${API_BASE}/video_feed/${selectedNode}`} 
                alt={`Live feed for ${selectedNode}`}
                className="w-full h-full object-contain"
                onError={(e) => { e.target.style.display = 'none'; }}
                onLoad={(e) => { e.target.style.display = 'block'; }}
              />
            </>
          ) : (
            <div className="text-slate-600 font-mono tracking-widest uppercase">
              No Node Selected
            </div>
          )}

        </div>

        {/* Right Panel: Telemetry & Health */}
        <div className="bg-[#030B17] border border-slate-800 rounded-xl p-6 flex flex-col gap-6">
           <h3 className="text-sm font-bold text-white uppercase tracking-widest flex items-center gap-2 border-b border-slate-800 pb-3">
              <Activity className="text-[#00FF9C] w-4 h-4"/> System Health
           </h3>

           {telemetry ? (
              <div className="flex flex-col gap-5">
                 
                 {/* CPU */}
                 <div>
                    <div className="flex justify-between text-xs mb-1 font-mono">
                       <span className="flex items-center gap-1 text-slate-400"><Cpu size={12}/> CPU</span>
                       <span className={telemetry.cpu_pct > 85 ? 'text-[#FF3B3B]' : 'text-white'}>{telemetry.cpu_pct.toFixed(1)}%</span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                       <div className={`h-full ${telemetry.cpu_pct > 85 ? 'bg-[#FF3B3B]' : 'bg-[#00F5FF]'}`} style={{width: `${telemetry.cpu_pct}%`}} />
                    </div>
                 </div>

                 {/* RAM */}
                 <div>
                    <div className="flex justify-between text-xs mb-1 font-mono">
                       <span className="flex items-center gap-1 text-slate-400"><Server size={12}/> RAM</span>
                       <span className={telemetry.ram_pct > 85 ? 'text-[#FF3B3B]' : 'text-white'}>{telemetry.ram_used_gb} / {telemetry.ram_total_gb} GB</span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                       <div className={`h-full ${telemetry.ram_pct > 85 ? 'bg-[#FF3B3B]' : 'bg-[#00FF9C]'}`} style={{width: `${telemetry.ram_pct}%`}} />
                    </div>
                 </div>

                 {/* VRAM */}
                 <div>
                    <div className="flex justify-between text-xs mb-1 font-mono">
                       <span className="flex items-center gap-1 text-slate-400"><Server size={12}/> VRAM (GPU)</span>
                       <span className="text-white">{telemetry.gpu_used_mb} / {telemetry.gpu_total_mb} MB</span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                       <div className="h-full bg-purple-500" style={{width: `${Math.min(100, (telemetry.gpu_used_mb / Math.max(1, telemetry.gpu_total_mb)) * 100)}%`}} />
                    </div>
                    {telemetry.batch_jobs_queued > 0 && (
                       <div className="text-[9px] text-yellow-500 mt-1 font-mono animate-pulse">
                          {telemetry.batch_jobs_queued} GPU jobs queued
                       </div>
                    )}
                 </div>

                 {/* DISK */}
                 <div>
                    <div className="flex justify-between text-xs mb-1 font-mono">
                       <span className="flex items-center gap-1 text-slate-400"><HardDrive size={12}/> DISK (Clips)</span>
                       <span className="text-white">{telemetry.disk_used_gb} / {telemetry.disk_free_gb + telemetry.disk_used_gb} GB</span>
                    </div>
                 </div>

                 <hr className="border-slate-800 my-2" />

                 {/* CLIP RETENTION */}
                 <div>
                    <div className="flex justify-between items-center mb-2">
                       <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Clip Retention</span>
                    </div>
                    <div className="flex gap-2">
                       <input 
                         type="number" 
                         min="1" max="30"
                         value={nodeConfig.clip_retention_days}
                         onChange={e => { setNodeConfig({...nodeConfig, clip_retention_days: parseInt(e.target.value)}); setHasUnsavedChanges(true); }}
                         className="w-16 bg-[#0F172A] border border-slate-700 rounded p-1 text-white text-center text-sm focus:border-[#00F5FF] focus:outline-none font-mono"
                       />
                       <span className="text-xs text-slate-500 self-center">days</span>
                    </div>
                    <p className="text-[10px] text-slate-500 mt-1 leading-tight">Clips older than this will be automatically deleted to save disk space.</p>
                 </div>

              </div>
           ) : (
              <div className="text-slate-600 font-mono text-sm">Loading telemetry...</div>
           )}
        </div>

      </div>
    </div>
  );
}
