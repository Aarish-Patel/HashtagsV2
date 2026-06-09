import React, { useState, useEffect, useRef } from 'react';
import { API_BASE } from '../config';
import AlertTriangle from 'lucide-react/dist/esm/icons/alert-triangle';
import Camera from 'lucide-react/dist/esm/icons/camera';
import ShieldAlert from 'lucide-react/dist/esm/icons/shield-alert';

export default function AdminDashboard() {
  const [nodes, setNodes] = useState([]);
  const [selectedNode, setSelectedNode] = useState('');
  const [activeThreats, setActiveThreats] = useState({});
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  // Poll for active nodes and active threats
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/status`);
        const data = await res.json();
        
        // Populate node dropdown from the backend's live sensor list
        if (data.sensors) {
          const liveNodes = data.sensors.map((s) => ({
            id: s.id,
            name: s.id
          }));
          
          setNodes(liveNodes);
          
          // Auto-select first node if none selected
          if (!selectedNode && liveNodes.length > 0) {
            setSelectedNode(liveNodes[0].id);
          }
        }
      } catch (e) {
        console.error("Failed to fetch status", e);
      }
    };

    const fetchAnalysis = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/analyze/all`);
        const data = await res.json();
        const jobs = data.jobs || [];
        
        const currentThreats = {};
        jobs.forEach(job => {
            if (job.status === 'COMPLETE' && job.threat_detected) {
                // Threat is active on this node (keep it simple for Admin view)
                // In a real app we'd clear this after dismissal, but this shows recent threats
                currentThreats[job.node_id] = true;
            } else if (job.status === 'ANALYZING') {
                currentThreats[job.node_id] = 'analyzing';
            }
        });
        setActiveThreats(currentThreats);
        
      } catch (e) {
        console.error("Failed to fetch analysis", e);
      }
    };

    fetchStatus();
    fetchAnalysis();
    
    const t1 = setInterval(fetchStatus, 2000);
    const t2 = setInterval(fetchAnalysis, 1000);
    
    return () => {
      clearInterval(t1);
      clearInterval(t2);
    };
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
      showMessage(data.message || 'Simulated threat triggered');
    } catch (e) {
      showMessage('Error triggering threat');
    }
    setLoading(false);
  };

  const handleSetBackground = async () => {
    if (!selectedNode) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/set_background/${selectedNode}`, { method: 'POST' });
      const data = await res.json();
      showMessage(data.message || 'Permanent background captured');
    } catch (e) {
      showMessage('Error setting background');
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#020617] text-slate-300 font-sans p-6 flex flex-col">
      <header className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
        <div className="flex items-center gap-3">
          <ShieldAlert className="text-[#FF3B3B] w-8 h-8" />
          <h1 className="text-2xl font-bold tracking-widest text-white">SYSTEM ADMIN CONSOLE</h1>
        </div>
        <div className="text-xs tracking-widest text-slate-500 uppercase">
          Hashtag V2 Surveillance
        </div>
      </header>

      <div className="max-w-6xl mx-auto w-full grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Controls Sidebar */}
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
                  {node.id} {activeThreats[node.id] === true ? ' [⚠ THREAT]' : ''}
                </option>
              ))}
            </select>
          </div>

          <hr className="border-slate-800" />

          <div className="flex flex-col gap-4">
            <h3 className="text-sm font-bold text-white uppercase tracking-widest">Node Actions</h3>
            
            <button
              onClick={handleSetBackground}
              disabled={!selectedNode || loading}
              className="flex items-center justify-center gap-2 w-full bg-slate-800 hover:bg-slate-700 text-white font-bold py-3 px-4 rounded-lg transition-colors disabled:opacity-50"
            >
              <Camera className="w-5 h-5 text-[#00F5FF]" />
              Capture Permanent Background
            </button>
            <p className="text-xs text-slate-500 mt-[-8px]">
              Takes a snapshot of the empty room to prevent MOG2 from adapting to stationary humans.
            </p>

            <button
              onClick={handleSimulateThreat}
              disabled={!selectedNode || loading}
              className="flex items-center justify-center gap-2 w-full bg-[#FF3B3B]/10 hover:bg-[#FF3B3B]/20 border border-[#FF3B3B]/50 text-[#FF3B3B] font-bold py-3 px-4 rounded-lg transition-colors mt-4 disabled:opacity-50"
            >
              <AlertTriangle className="w-5 h-5" />
              Simulate High Threat
            </button>
            <p className="text-xs text-slate-500 mt-[-8px]">
              Injects a mock human detection to trigger the alarm protocol.
            </p>
          </div>

          {message && (
            <div className="mt-auto p-4 bg-[#00F5FF]/10 border border-[#00F5FF]/30 text-[#00F5FF] text-sm rounded-lg text-center font-mono">
              {message}
            </div>
          )}
        </div>

        {/* Video Feed Monitor */}
        <div className="lg:col-span-2 bg-[#000] border-2 border-slate-800 rounded-xl overflow-hidden relative min-h-[500px] flex items-center justify-center">
          
          {selectedNode ? (
            <>
              {/* Visual Threat Indicator */}
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
                onError={(e) => {
                  e.target.style.display = 'none';
                }}
                onLoad={(e) => {
                  e.target.style.display = 'block';
                }}
              />
            </>
          ) : (
            <div className="text-slate-600 font-mono tracking-widest uppercase">
              No Node Selected
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
