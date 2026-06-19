import React, { useState } from 'react';
import X from 'lucide-react/dist/esm/icons/x';
import Plus from 'lucide-react/dist/esm/icons/plus';
import Edit2 from 'lucide-react/dist/esm/icons/edit-2';
import Trash2 from 'lucide-react/dist/esm/icons/trash-2';
import Send from 'lucide-react/dist/esm/icons/send';
import PlayCircle from 'lucide-react/dist/esm/icons/play-circle';
import CheckCircle from 'lucide-react/dist/esm/icons/check-circle';
import { API_BASE } from '../../config';

const NodeAlerts = ({ entities }) => {
  // Group entities by node
  const nodesInAlert = [...new Set(entities.map(e => e.camera || 'UNKNOWN_NODE'))];
  
  if (nodesInAlert.length === 0) return null;

  return (
    <div className="flex flex-col mt-4 px-5">
      <div className="flex justify-between items-center mb-2 border-b border-red-500/20 pb-1 opacity-80">
         <h3 className="text-[9px] font-black tracking-[0.4em] text-[#FF3B3B] uppercase">NODE ALERTS</h3>
         <span className="text-[10px] text-[#FF3B3B] font-black tabular-nums animate-pulse">{nodesInAlert.length}</span>
      </div>
      <div className="flex flex-col gap-2">
        {nodesInAlert.map(nodeId => (
           <div key={nodeId} className="bg-[#FF3B3B]/10 border border-[#FF3B3B]/30 p-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                 <div className="w-1.5 h-1.5 rounded-full bg-[#FF3B3B] animate-ping" />
                 <span className="text-[10px] font-black tracking-widest text-[#FF3B3B] uppercase">{nodeId}</span>
              </div>
              <span className="text-[8px] text-red-400 font-bold uppercase tracking-wider">Active Intrusion</span>
           </div>
        ))}
      </div>
    </div>
  );
};

const CurrentAlerts = ({ incidents, nodes }) => {
  const [ackedClips, setAckedClips] = useState([]);

  // Acknowledge clip
  const handleAck = async (id, e, nodeId) => {
    e.stopPropagation();
    setAckedClips(prev => [...prev, id]);
    if (nodeId) {
      try {
        const token = localStorage.getItem('token');
        const headers = {};
        if (token && token !== 'null' && token !== 'undefined') {
          headers['Authorization'] = 'Bearer ' + token;
        }
        await fetch(`${API_BASE}/api/admin/acknowledge/${nodeId}`, {
          method: 'POST',
          headers
        });
      } catch (err) {
        console.error("Failed to ack node backend", err);
      }
    }
  };
  const handleOpenFolder = async () => {
    try {
      await fetch(`${API_BASE}/api/open_clips_folder`, { method: 'POST' });
    } catch (e) {
      console.error("Failed to open clips folder", e);
    }
  };

  // If no incidents, we can show a placeholder or empty list
  const displayClips = incidents && incidents.length > 0 ? incidents : []; 

  const activeClips = displayClips.filter(c => !ackedClips.includes(c.clip_file || c.filename || c.id));

  return (
    <div className="flex flex-col mt-4 px-5 mb-4">
      <div className="flex justify-between items-center mb-3 border-b border-white/5 pb-1 opacity-90 gap-2">
         <h3 className="text-[9px] font-black tracking-[0.4em] text-[#00F5FF] uppercase">CURRENT ALERTS</h3>
         <div className="flex gap-2 shrink-0">
           <button onClick={handleOpenFolder} className="text-[7px] bg-[#00F5FF]/10 text-[#00F5FF] border border-[#00F5FF]/30 px-2 py-0.5 hover:bg-[#00F5FF]/20 uppercase font-black transition-colors">
             OPEN DIR
           </button>
           <button onClick={async () => {
             if (window.confirm("PERMANENTLY DELETE ALL REPLAYS? This action cannot be undone.")) {
               try {
                 await fetch(`${API_BASE}/api/admin/clear_clips`, { method: 'POST' });
                 setAckedClips(displayClips.map(c => c.clip_file || c.filename || c.id));
               } catch (e) { console.error(e); }
             }
           }} className="text-[7px] bg-[#FF3B3B]/10 text-[#FF3B3B] border border-[#FF3B3B]/30 px-2 py-0.5 hover:bg-[#FF3B3B]/20 uppercase font-black transition-colors">
             CLEAR CLIPS
           </button>
         </div>
      </div>
      <div className="flex flex-col gap-2 max-h-[300px] overflow-y-auto custom-scrollbar pr-1">
        {activeClips.length === 0 && <div className="text-[9px] text-[#94A3B8]/40 font-black tracking-widest uppercase py-4">ALL ALERTS ACKNOWLEDGED</div>}
        {activeClips.map((clip, i) => {
          const rep = clip.report || {};
          const clipId = clip.filename || `INC-${i}`;
          
          // Use node_id from report to look up the node details directly
          const nodeId = rep.node_id || (clip.filename ? clip.filename.split('_')[0] : 'UNKNOWN');
          const node = nodes?.find(n => n.id === nodeId);
          
          const nodeName = node?.name || nodeId;
          const nodeLoc = node ? `${node.lat}, ${node.lng}` : 'LOCATION UNAVAILABLE';
          
          // Format time safely
          let timeStr = 'UNKNOWN TIME';
          if (rep.timestamp) {
             const d = new Date(rep.timestamp);
             if (!isNaN(d.getTime())) timeStr = d.toLocaleString();
          } else if (clip.time) {
             timeStr = clip.time;
          }
          
          const entityCount = rep.entity_count || clip.entity_count || 0;
          const isHighThreat = rep.weapons_detected || clip.weapons_detected || (rep.max_threat_level >= 3);
          
          return (
            <div key={clipId} className="group relative bg-[#030B17]/40 border border-white/5 p-2 flex flex-col gap-1.5 hover:border-[#00F5FF]/30 transition-all cursor-pointer overflow-hidden">
               {/* Base info */}
               <div className="flex justify-between items-start transition-opacity duration-200 group-hover:opacity-5">
                 <div className="flex flex-col gap-0.5">
                   <span className="text-[10px] font-black text-[#E2E8F0] tracking-widest uppercase leading-none">{clipId}</span>
                   <span className="text-[9px] font-bold text-slate-400 tracking-wider uppercase mt-1">{timeStr}</span>
                   <span className="text-[8px] font-bold text-[#00F5FF] tracking-wider uppercase">{nodeName} — {nodeLoc}</span>
                   <span className="text-[7px] font-black text-[#94A3B8] tracking-widest uppercase mt-1">
                     {entityCount} ENTITIES {rep.weapons_detected ? ' | WEAPON DETECTED' : ''}
                   </span>
                 </div>
                 <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${isHighThreat ? 'bg-[#FF3B3B]' : 'bg-[#FFD60A]'}`} />
               </div>
               
               {/* Hover Overlay with 2 Buttons */}
               <div className="absolute inset-0 bg-[#00F5FF]/5 backdrop-blur-sm flex items-center justify-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200 p-1">
                 <button onClick={(e) => handleAck(clipId, e, nodeId)} className="flex-1 h-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center gap-1 text-[7px] font-black uppercase tracking-widest hover:bg-emerald-500/20 transition-colors">
                   <CheckCircle size={10} /> ACK
                 </button>
                 <button className="flex-1 h-full bg-[#FF3B3B]/10 border border-[#FF3B3B]/30 text-[#FF3B3B] flex items-center justify-center gap-1 text-[7px] font-black uppercase tracking-widest hover:bg-[#FF3B3B]/20 transition-colors">
                   <Send size={10} /> ESCALATE
                 </button>
               </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const NodeManager = ({ nodes, setNodes }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({ id: '', name: '', lat: '', lng: '', ip: '', alarm_trigger_type: 'PIR' });

  const handleSave = async () => {
    if (!formData.name || !formData.lat || !formData.lng || !formData.ip) return;
    
    const isNew = !formData.id;
    const endpoint = isNew ? `${API_BASE}/api/nodes/add` : `${API_BASE}/api/nodes/${formData.id}`;
    const method = isNew ? 'POST' : 'PATCH';
    
    const payload = {
      id: formData.id || `HASH-${Date.now()}`,
      name: formData.name,
      lat: parseFloat(formData.lat),
      lng: parseFloat(formData.lng),
      stream_url: (formData.ip.startsWith('http') || formData.ip.startsWith('raw') || formData.ip.startsWith('tcp') || formData.ip.includes('!')) ? formData.ip.replace(/`/g, '').trim() : `http://${formData.ip}/stream`,
      alarm_trigger_type: formData.alarm_trigger_type || 'PIR'
    };

    try {
      const res = await fetch(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        if (isNew) {
           setNodes([...nodes, payload]);
        } else {
           setNodes(nodes.map(n => n.id === formData.id ? { ...n, ...payload } : n));
        }
      }
    } catch (e) {
      console.error("Failed to save node:", e);
    }
    setIsEditing(false);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("PERMANENTLY DELETE THIS NODE? This will archive all its clips.")) return;
    try {
      const res = await fetch(`${API_BASE}/api/nodes/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setNodes(nodes.filter(n => n.id !== id));
      }
    } catch (e) {
      console.error("Failed to delete node:", e);
    }
  };

  return (
    <div className="px-5 flex flex-col mb-4">
      <div className="flex justify-between items-center mb-2 border-b border-white/5 pb-1 opacity-80">
         <h3 className="text-[9px] font-black tracking-[0.3em] text-[#00F5FF] uppercase">HASHTAG NODES</h3>
         {!isEditing && (
           <button onClick={() => { setFormData({ id: '', name: '', lat: '', lng: '', ip: '', alarm_trigger_type: 'DETECTION' }); setIsEditing(true); }} className="text-[#00F5FF] hover:text-white transition-colors">
             <Plus size={12} />
           </button>
         )}
      </div>

      {isEditing ? (
        <div className="bg-[#030B17]/80 border border-[#00F5FF]/20 p-2 flex flex-col gap-2">
           <input className="bg-black border border-white/10 text-[9px] p-1.5 px-2 text-white placeholder-slate-600 outline-none focus:border-[#00F5FF]/50" placeholder="Node Name (e.g. Tiger Chongjan)" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} />
           <input className="bg-black border border-white/10 text-[9px] p-1.5 px-2 text-white placeholder-slate-600 outline-none focus:border-[#00F5FF]/50" placeholder="Latitude (e.g. 24.165)" value={formData.lat} onChange={e => setFormData({...formData, lat: e.target.value})} />
           <input className="bg-black border border-white/10 text-[9px] p-1.5 px-2 text-white placeholder-slate-600 outline-none focus:border-[#00F5FF]/50" placeholder="Longitude (e.g. 94.259)" value={formData.lng} onChange={e => setFormData({...formData, lng: e.target.value})} />
           <input className="bg-black border border-white/10 text-[9px] p-1.5 px-2 text-white placeholder-slate-600 outline-none focus:border-[#00F5FF]/50" placeholder="Stream IP (e.g. 192.168.1.50)" value={formData.ip} onChange={e => setFormData({...formData, ip: e.target.value})} />
           <select className="w-full bg-[#0F172A]/50 border border-slate-700 rounded px-2 py-1 text-white text-[10px] focus:outline-none focus:border-[#00F5FF]" value={formData.alarm_trigger_type || 'PIR'} onChange={e => setFormData({...formData, alarm_trigger_type: e.target.value})}>
             <option value="DETECTION">DETECTION</option>
             <option value="PIR">PIR</option>
           </select>
           <div className="flex gap-2 mt-1">
             <button onClick={handleSave} className="flex-1 bg-[#00F5FF]/20 text-[#00F5FF] border border-[#00F5FF]/30 text-[9px] py-1.5 font-black uppercase tracking-widest hover:bg-[#00F5FF]/30 transition-colors">SAVE</button>
             <button onClick={() => setIsEditing(false)} className="flex-1 bg-slate-800 text-slate-400 border border-slate-700 text-[9px] py-1.5 font-black uppercase tracking-widest hover:text-white transition-colors">CANCEL</button>
           </div>
        </div>
      ) : (
        <div className="flex flex-col gap-1.5 max-h-[250px] overflow-y-auto custom-scrollbar pr-1">
          {nodes.map(n => (
            <div key={n.id} className="bg-[#030B17]/40 border border-[#E2E8F0]/5 p-2 flex flex-col gap-1 group hover:border-[#00F5FF]/30 transition-colors">
              <div className="flex justify-between items-center">
                 <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-[#00FF9C] shadow-[0_0_5px_#00FF9C88]" />
                    <span className="text-[9px] font-black text-[#E2E8F0] tracking-widest uppercase">{n.name} ({n.alarm_trigger_type || 'PIR'})</span>
                 </div>
                 <div className="opacity-0 group-hover:opacity-100 flex gap-2 transition-opacity">
                    <button onClick={() => { setFormData({...n, ip: n.stream_url, alarm_trigger_type: n.alarm_trigger_type || 'PIR'}); setIsEditing(true); }} className="text-[#00F5FF] hover:text-white">
                       <Edit2 size={10} />
                    </button>
                    <button onClick={() => handleDelete(n.id)} className="text-[#FF3B3B] hover:text-white">
                       <Trash2 size={10} />
                    </button>
                 </div>
              </div>
              <div className="flex justify-between text-[7px] font-black text-[#94A3B8]/60 uppercase tracking-wider">
                 <span>{n.lat}, {n.lng}</span>
                 <span className="truncate max-w-[100px] ml-2 text-right">IP: {n.stream_url}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const Sidebar = ({ entities, incidents, nodes, setNodes, sidebarOpen, setSidebarOpen }) => {
  return (
    <>
      {/* MOBILE OVERLAY */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[55] lg:hidden transition-opacity animate-in fade-in duration-300"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside className={`
        fixed lg:static top-0 right-0 h-full lg:h-auto 
        w-[320px] lg:w-[340px] shrink-0 
        z-[60] lg:z-auto
        bg-[#030B17] border-l border-[#00F5FF]/10 
        flex flex-col overflow-y-auto custom-scrollbar 
        transition-transform duration-500 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : 'translate-x-full lg:translate-x-0'}
      `}>
         
         <div className="lg:hidden flex items-center justify-between p-4 border-b border-white/5 bg-[#00F5FF]/5">
            <span className="text-[#00F5FF] text-[10px] font-black tracking-widest uppercase">TARGET_MONITOR</span>
            <button onClick={() => setSidebarOpen(false)} className="text-[#94A3B8] hover:text-[#E2E8F0]">
               <X size={20} />
            </button>
         </div>

         {/* 1. NODE ALERTS */}
         <NodeAlerts entities={entities} />

         {/* 2. CURRENT ALERTS */}
         <CurrentAlerts incidents={incidents} nodes={nodes} />

         <div className="mt-auto pt-2">
            {/* 3. NODE MANAGER */}
            <NodeManager nodes={nodes} setNodes={setNodes} />
         </div>
      </aside>
    </>
  );
};

export default Sidebar;
