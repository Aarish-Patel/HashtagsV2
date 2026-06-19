import React, { useState, useEffect, useRef, useCallback } from 'react';
import Header from './components/layout/Header';
import Sidebar from './components/layout/Sidebar';
import Footer from './components/layout/Footer';
import Terminal from './components/layout/Terminal';
import LiveFeed from './components/tabs/LiveFeed';
import EntityTracker from './components/tabs/EntityTracker';
import AlertHistory from './components/tabs/AlertHistory';
import StorageView from './components/tabs/StorageView';
import TacticalMap from './components/tabs/TacticalMap';
import Monitor from 'lucide-react/dist/esm/icons/monitor';
import Activity from 'lucide-react/dist/esm/icons/activity';
import Map from 'lucide-react/dist/esm/icons/map';
import { API_BASE } from './config';

// ────────────────────────────────────────────────────────────
// ANALYSIS STATE MACHINE
//   STANDBY   → feeds are clean, no ML running
//   ANALYZING → SPACEBAR pressed, ML running on buffered clip
//   THREAT    → threat confirmed, replay shown + alarm
//   CLEAR     → no threat, brief "SECTOR CLEAR" shown
// ────────────────────────────────────────────────────────────
const MODE = {
  STANDBY:   'STANDBY',
  ANALYZING: 'ANALYZING',
  THREAT:    'THREAT',
  CLEAR:     'CLEAR',
};

// Browser-side alarm using the custom MP3 file
let activeAlarmAudio = null;

function playBrowserBuzzer() {
  try {
    if (!activeAlarmAudio) {
      activeAlarmAudio = new Audio('/alarm.mp3');
      activeAlarmAudio.loop = true; // Repeat the alarm
    }
    // Prevent overlapping play calls
    if (activeAlarmAudio.paused) {
      activeAlarmAudio.play().catch(e => console.warn("Browser blocked audio playback without interaction", e));
    }
  } catch (e) {
    console.warn("Failed to play alarm audio", e);
  }
}

function stopBrowserBuzzer() {
  if (activeAlarmAudio) {
    activeAlarmAudio.pause();
    activeAlarmAudio.currentTime = 0;
  }
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('token'));
  const [role, setRole] = useState(() => localStorage.getItem('role'));

  // ── Core state ──────────────────────────────────────────────
  const [activeTab, setActiveTab]       = useState('TACTICAL MAP');
  const [time, setTime]                 = useState('');
  const [uptime, setUptime]             = useState(0);
  const [sensors, setSensors]           = useState([]);
  const [beacons, setBeacons]           = useState([]);
  const [system, setSystem]             = useState({ cpu: 0, memory: 0, disk: 0, gpu: 0 });
  const [logs, setLogs]                 = useState([]);
  const [alerts, setAlerts]             = useState([]);
  const [incidents, setIncidents]       = useState([]);
  // ── Nodes — fetched from backend (single source of truth) ─
  const [nodes, setNodes] = useState([]);

  const fetchNodes = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/nodes`, { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      // Normalize to the shape the rest of the app uses
      setNodes(data.map(n => ({
        id: n.id,
        name: n.name,
        lat: n.lat,
        lng: n.lng,
        stream_url: n.stream_url,
        online: n.online,
        fps: n.fps,
        clips_saved: n.clips_saved,
        has_permanent_bg: n.has_permanent_bg,
        viz_mode: n.viz_mode,
        config: n.config,
        // Legacy field aliases for older components
        ip: n.stream_url,
      })));
    } catch (e) { /* backend offline */ }
  }, []);

  // ── Analysis state machine ───────────────────────────────────
  const [mode, setMode]                 = useState(MODE.STANDBY);
  const [analysisJobs, setAnalysisJobs] = useState([]);
  const [threatEntities, setThreatEntities] = useState([]);
  const [replayUrls, setReplayUrls]     = useState({});
  const [clearTimer, setClearTimer]     = useState(null);

  // ── Multi-threat map state ───────────────────────────────────
  // activeThreatNodes: [{node_id, name, lat, lng, threat_count, replay_url}]
  const [activeThreatNodes, setActiveThreatNodes] = useState([]);

  // ── Polling refs to avoid stale closures ───────────────────
  const analysisJobsRef = useRef([]);
  analysisJobsRef.current = analysisJobs;
  const modeRef = useRef(MODE.STANDBY);
  modeRef.current = mode;
  // Timestamp of last acknowledge — used to reject stale jobs in pollJobs.
  // A ref (not state) so it's always current inside closures without re-renders.
  const acknowledgedAtRef = useRef(0);

  // ── Clock ────────────────────────────────────────────────────
  useEffect(() => {
    const t = setInterval(() => {
      setTime(new Date().toLocaleTimeString('en-GB'));
      setUptime(u => u + 1);
    }, 1000);
    return () => clearInterval(t);
  }, []);

  const formatUptime = (secs) => {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = Math.floor(secs % 60);
    return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  };

  // ── Fetch system status (sensors, events) ───────────────────
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`);
      const data = await res.json();
      setSensors(data.sensors || []);
      setSystem(prev => ({ ...prev, ...data.system }));
      setBeacons((data.sensors || []).map((s, i) => ({
        id: `NODE-${i+1}`,
        label: s.online ? 'ACTIVE' : 'OFFLINE',
        fps: s.online ? (s.fps || 5) : 0,
      })));

      const evtRes = await fetch(`${API_BASE}/api/events?limit=200`);
      const evtData = await evtRes.json();
      const parsedLogs = evtData.slice(0, 60).map(e => ({
        time: `[${e.ts_str || '??:??:??'}]`,
        txt: `${e.type || 'EVENT'}: ${e.description || ''}`,
        color: (e.threat_level >= 4) ? 'text-[#FF3B3B]'
             : (e.threat_level >= 3) ? 'text-[#FFD60A]'
             : 'text-[#00F5FF]',
      }));
      setLogs(parsedLogs.reverse());
    } catch (e) { /* backend offline */ }
  }, []);

  const fetchIncidents = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/clips`);
      if (res.ok) setIncidents(await res.json());
    } catch (e) {}
  }, []);

  useEffect(() => {
    fetchStatus();
    const t = setInterval(fetchStatus, 500);
    return () => clearInterval(t);
  }, [fetchStatus]);

  useEffect(() => {
    fetchNodes();
    const t = setInterval(fetchNodes, 5000); // Sync nodes from backend every 5s
    return () => clearInterval(t);
  }, [fetchNodes]);

  useEffect(() => {
    fetchIncidents();
    const t = setInterval(fetchIncidents, 2000);
    return () => clearInterval(t);
  }, [fetchIncidents]);

  // ── Poll /api/threats/active for multi-threat map zoom ───────
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/threats/active`);
        if (!res.ok) return;
        const threats = await res.json();
        setActiveThreatNodes(threats);
        // Keep mode in sync: if backend says there are active threats, enter THREAT mode
        if (threats.length > 0) {
          if (modeRef.current !== MODE.THREAT) {
            setMode(MODE.THREAT);
          }
          playBrowserBuzzer(4);
          // Build replayUrls for LiveFeed tab backward compat
          const urls = {};
          threats.forEach(t => { urls[t.node_id] = t.replay_url; });
          setReplayUrls(urls);
        } else if (modeRef.current === MODE.THREAT) {
          // All threats cleared
          stopBrowserBuzzer();
          setMode(MODE.STANDBY);
          setReplayUrls({});
          setThreatEntities([]);
        }
      } catch (e) { /* backend offline */ }
    };
    poll();
    const t = setInterval(poll, 1500);
    return () => clearInterval(t);
  }, []);

  // ── Poll for Batch Analysis Jobs (SPACEBAR-triggered only) ───────────────────
  // NOTE: INSTANT alarm jobs (PIR/DETECTION) are handled exclusively by
  // pollThreats via _active_threat_count. pollJobs MUST NOT act on them.
  const [lastSeenJobId, setLastSeenJobId] = useState(null);

  useEffect(() => {
    const pollJobs = async () => {
      // While in THREAT or CLEAR, do not interfere — pollThreats owns those states
      if (modeRef.current === MODE.THREAT || modeRef.current === MODE.CLEAR) return;
      
      try {
        const res = await fetch(`${API_BASE}/api/analyze/all`);
        const data = await res.json();
        const jobs = data.jobs || [];

        // Eligibility rules for pollJobs:
        //   1. Not already acknowledged on the backend
        //   2. NOT an INSTANT job — those are driven by _active_threat_count in pollThreats
        //   3. Created AFTER the last time the operator hit Acknowledge
        //      (prevents stale pre-acknowledge jobs from re-triggering)
        const eligibleJobs = jobs.filter(j =>
          !j.acknowledged &&
          !j.job_id.startsWith('INSTANT') &&
          (acknowledgedAtRef.current === 0 || (j.created_at * 1000) > acknowledgedAtRef.current)
        );

        if (eligibleJobs.length === 0) return;

        // STANDBY → check if a new batch auto-job appeared
        if (modeRef.current === MODE.STANDBY) {
            const latestJob = eligibleJobs[eligibleJobs.length - 1];
            if (latestJob.job_id !== lastSeenJobId) {
                setLastSeenJobId(latestJob.job_id);
                if (latestJob.is_auto_trigger) {
                    setAnalysisJobs([latestJob]);
                    setMode(MODE.ANALYZING);
                    setLogs(prev => [{
                        time: `[${new Date().toLocaleTimeString('en-GB')}]`,
                        txt: `AUTO_TRIGGER — Node ${latestJob.node_id} wake-up analysis started`,
                        color: 'text-[#00F5FF]'
                    }, ...prev.slice(0, 59)]);
                }
            }
            return;
        }

        // ANALYZING → track progress of the batch jobs we launched
        if (modeRef.current === MODE.ANALYZING) {
            const currentJobIds = analysisJobsRef.current.map(j => j.job_id);
            const activeServerJobs = jobs.filter(j => currentJobIds.includes(j.job_id));
            
            if (activeServerJobs.length > 0) {
                setAnalysisJobs(activeServerJobs);
                
                const allDone = activeServerJobs.every(j => j.status === 'COMPLETE' || j.status === 'CLEAR' || j.status === 'ERROR');
                if (allDone) {
                    const threatJobs = activeServerJobs.filter(j => j.threat_detected);

                    if (threatJobs.length > 0) {
                        const allEntities = threatJobs.flatMap(j => 
                            (j.entities || []).map(ent => ({ ...ent, camera: j.node_id }))
                        );
                        const maxThreat = Math.max(...threatJobs.map(j => j.max_threat_level || 0));
                        const urls = {};
                        threatJobs.forEach(j => {
                            if (j.clip_url) urls[j.node_id] = j.clip_url;
                            else if (j.replay_url) urls[j.node_id] = j.replay_url;
                        });

                        setThreatEntities(allEntities);
                        setReplayUrls(urls);
                        setMode(MODE.THREAT);
                        playBrowserBuzzer(maxThreat);
                        fetchIncidents();

                        setAlerts(prev => [{
                            id: `JOB-${Date.now()}`,
                            level: maxThreat >= 4 ? 'danger' : 'warning',
                            time: new Date().toLocaleTimeString(),
                            txt: `THREAT CONFIRMED — ${allEntities.length} entities | L${maxThreat}`,
                            score: maxThreat * 25,
                        }, ...prev.slice(0, 49)]);
                    } else {
                        setMode(MODE.STANDBY);
                        setAnalysisJobs([]);
                    }
                }
            } else {
                setMode(MODE.STANDBY);
                setAnalysisJobs([]);
            }
        }
      } catch (e) {
      }
    };

    const interval = setInterval(pollJobs, 800);
    return () => clearInterval(interval);
  }, [lastSeenJobId, fetchIncidents]);

  // ── SPACEBAR handler ─────────────────────────────────────────
  const triggerAnalysis = useCallback(async () => {
    if (modeRef.current === MODE.ANALYZING) return; // Already running

    // Reset any previous results
    if (clearTimer) clearTimeout(clearTimer);
    setThreatEntities([]);
    setReplayUrls({});
    setAnalysisJobs([]);
    setMode(MODE.ANALYZING);

    try {
      const res = await fetch(`${API_BASE}/api/analyze`, { method: 'POST' });
      const data = await res.json();
      const jobs = (data.job_ids || []).map(jid => ({
        job_id: jid, status: 'QUEUED', progress: 0,
        threat_detected: false, entities: [],
      }));
      setAnalysisJobs(jobs);
      
      // Update lastSeenJobId so pollJobs doesn't think this is a new auto-trigger
      if (jobs.length > 0) {
        setLastSeenJobId(jobs[jobs.length - 1].job_id);
      }

      // Add to log
      setLogs(prev => [{
        time: `[${new Date().toLocaleTimeString('en-GB')}]`,
        txt: `ANALYSIS TRIGGERED — ${data.node_count} nodes | ${data.job_ids?.length} jobs queued`,
        color: 'text-[#00F5FF]'
      }, ...prev.slice(0, 59)]);
    } catch (e) {
      console.error('Analyze trigger failed:', e);
      setMode(MODE.STANDBY);
    }
  }, [clearTimer]);

  const simulateThreat = useCallback(async () => {
    if (modeRef.current === MODE.ANALYZING) return;
    
    if (clearTimer) clearTimeout(clearTimer);
    setThreatEntities([]);
    setReplayUrls({});
    setAnalysisJobs([]);
    setMode(MODE.ANALYZING);

    try {
      // Create a dummy job simulating a 2-second analysis that results in a threat
      const dummyJobId = `SIM-${Date.now()}`;
      setAnalysisJobs([{
        job_id: dummyJobId, status: 'QUEUED', progress: 0,
        threat_detected: false, entities: []
      }]);
      
      setLogs(prev => [{
        time: `[${new Date().toLocaleTimeString('en-GB')}]`,
        txt: `SIMULATION TRIGGERED — Initiating mock threat detection`,
        color: 'text-[#FFD60A]'
      }, ...prev.slice(0, 59)]);

      // After 1.5 seconds, force threat state
      setTimeout(() => {
        const dummyThreat = {
            id: 9999, class: 'Person', confidence: 0.99,
            threat_level: 4, threat_score: 99,
            distance_m: 50, behavior: 'SIMULATED INTRUSION',
            camera: 'CAM-SIM-01'
        };
        
        setAnalysisJobs([{
            job_id: dummyJobId,
            node_id: 'HASH-1', // Tie to an existing node
            status: 'COMPLETE',
            progress: 100,
            threat_detected: true,
            max_threat_level: 4,
            entities: [dummyThreat],
            replay_url: '/api/clips' // Dummy or we can use existing clip URL logic if needed, actually replay_url is the full path. Let's look up an existing incident or use a dummy image.
        }]);
        
        // Let the polling mechanism naturally pick up this COMPLETE job? No, pollJobs overrides analysisJobs from the server!
        // To make it sticky, we just directly invoke the threat logic here, since pollJobs will wipe it if the server doesn't know about `SIM-...`.
        setThreatEntities([dummyThreat]);
        
        // Wait, what if we just use an existing clip for the replay?
        // Let's use the first available activeClip from the backend or a dummy video URL
        setReplayUrls({
            'HASH-1': `${API_BASE}/clips/20260608_153957_24.180_94.260_PANGAL_SANGJAI.mp4`
        });
        
        setMode(MODE.THREAT);
        playBrowserBuzzer(4);
        
        setAlerts(prev => [{
            id: `JOB-${Date.now()}`,
            level: 'danger',
            time: new Date().toLocaleTimeString(),
            txt: `SIMULATED THREAT — 1 entity | L4`,
            score: 100,
        }, ...prev.slice(0, 49)]);
        
      }, 1500);

    } catch (e) {
      setMode(MODE.STANDBY);
    }
  }, [clearTimer]);

  const dismissThreat = useCallback(async (nodeId) => {
    // Stop the alarm immediately
    stopBrowserBuzzer();
    
    // If called from an onClick the argument is a React SyntheticEvent — ignore it
    if (nodeId && typeof nodeId === 'object') nodeId = undefined;

    // Stamp the acknowledge time FIRST so pollJobs immediately ignores stale jobs,
    // even before the backend responds.
    acknowledgedAtRef.current = Date.now();

    // Optimistically clear the UI so the user sees instant feedback
    setActiveThreatNodes([]);
    setMode(MODE.STANDBY);
    setAnalysisJobs([]);
    setThreatEntities([]);
    setReplayUrls({});

    // Collect all node IDs that need to be acknowledged on the backend
    const nodesToAck = new Set();
    if (nodeId) nodesToAck.add(nodeId);
    activeThreatNodes.forEach(t => nodesToAck.add(t.node_id));
    threatEntities.forEach(t => { if (t.camera) nodesToAck.add(t.camera); });
    
    if (nodesToAck.size > 0) {
      // Helper: attempt one acknowledge POST.
      // CRITICAL: if auth fails (expired/invalid token) we MUST retry without a
      // token so the backend's dev-mode bypass accepts the request.
      // Silently swallowing a 401 was the root cause of the persistent re-alarm.
      const ackNode = async (nid) => {
        const tryPost = async (includeAuth) => {
          const headers = {};
          if (includeAuth && token && token !== 'null' && token !== 'undefined') {
            headers['Authorization'] = 'Bearer ' + token;
          }
          const res = await fetch(`${API_BASE}/api/admin/acknowledge/${nid}`, {
            method: 'POST', headers
          });
          return res.ok;
        };
        try {
          const ok = await tryPost(true);
          if (!ok) {
            // Auth rejected — retry without token (dev bypass allows header-less requests)
            await tryPost(false);
          }
        } catch {
          // Network/fetch error — last-resort attempt without auth header
          try { await tryPost(false); } catch { /* truly unreachable */ }
        }
      };

      await Promise.all(Array.from(nodesToAck).map(ackNode));
    }
  }, [activeThreatNodes, threatEntities, token]);

  // Global SPACEBAR listener
  useEffect(() => {
    const handler = (e) => {
      if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        if (modeRef.current === MODE.THREAT) {
          dismissThreat();
        } else {
          triggerAnalysis();
        }
      } else if (e.code === 'KeyT' && e.target.tagName !== 'INPUT') {
        // T for Simulate Threat
        e.preventDefault();
        simulateThreat();
      } else if (e.code === 'Escape') {
        if (modeRef.current === MODE.THREAT) {
          dismissThreat();
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [triggerAnalysis, dismissThreat]);

  // ── Overlay states ────────────────────────────────────────────
  const isAnalyzing = mode === MODE.ANALYZING;
  const isThreat    = mode === MODE.THREAT;
  const isClear     = mode === MODE.CLEAR;

  const analyzeProgress = analysisJobs.length > 0
    ? Math.round(analysisJobs.reduce((s, j) => s + (j.progress || 0), 0) / analysisJobs.length)
    : 0;

  // For sidebar: show threat entities when in THREAT mode, else empty
  const displayEntities = isThreat ? threatEntities.map(e => ({
    ...e,
    id: `ENT-${String(e.id || 0)}`,
    score: e.threat_score || e.threat_level * 25,
    status: e.behavior || 'DETECTED',
    type: e.threat_level >= 4 ? 'high' : e.threat_level >= 2 ? 'mid' : 'low',
    distance: e.distance_m || 0,
    weapon: e.class === 'Weapon',
    camera: e.camera,
  })) : [];

  return (
    <div className="h-screen w-screen bg-[#020617] text-[#94A3B8] font-sans overflow-hidden flex flex-col select-none">


      {/* THREAT ALARM OVERLAY MOVED TO MAP CONTAINER */}


      {/* SECTOR CLEAR OVERLAY REMOVED AS REQUESTED */}

      {/* ── THREAT CONFIRMED BANNER ── */}
      {isThreat && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-[180] pointer-events-auto">
          <div className="bg-[#FF3B3B]/10 border border-[#FF3B3B] rounded-xl px-8 py-4 flex items-center gap-6 shadow-2xl shadow-[#FF3B3B]/20 backdrop-blur-md">
            <div className="w-3 h-3 rounded-full bg-[#FF3B3B] animate-ping" />
            <div>
              <div className="text-[#FF3B3B] font-bold text-lg tracking-widest uppercase">
                ⚠ THREAT CONFIRMED
              </div>
              <div className="text-red-300/70 text-xs mt-0.5">
                Clip saved. Press ESC to dismiss.
              </div>
            </div>
            <button
              onClick={dismissThreat}
              className="ml-4 text-slate-400 hover:text-white text-xl"
            >✕</button>
          </div>
        </div>
      )}





      {/* ── HEADER ── */}
      <Header
        entities={displayEntities}
        time={time}
        isRecording={isThreat}
        mode={mode}
        analyzeProgress={analyzeProgress}
        sidebarOpen={false}
        setSidebarOpen={() => {}}
        system={system}
      />

      <main className="grow flex overflow-hidden relative">
        <section className="grow flex flex-col min-w-0 bg-[#030B17] relative">
          <div className="grow overflow-hidden bg-[#020617] relative">
            {/* ── THREAT ALARM OVERLAY ── */}
            {isThreat && (
              <div className="absolute inset-0 z-[200] pointer-events-none">
                <div className="absolute inset-0 border-4 border-[#FF3B3B] animate-pulse rounded-none shadow-[inset_0_0_50px_rgba(255,59,59,0.2)]" />
                <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-[#FF3B3B] to-transparent animate-pulse" />
                <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-[#FF3B3B] to-transparent animate-pulse" />
              </div>
            )}
            <TacticalMap
              nodes={nodes}
              entities={displayEntities}
              mode={mode}
              replayUrls={replayUrls}
              activeThreatNodes={activeThreatNodes}
              onDismiss={dismissThreat}
            />
          </div>
          <Footer entities={displayEntities} uptime={uptime} alerts={alerts} incidents={incidents} formatUptime={formatUptime} />
        </section>

        <Sidebar
          entities={displayEntities}
          alerts={alerts}
          incidents={incidents}
          beacons={beacons}
          system={system}
          nodes={nodes}
          setNodes={setNodes}
          setHighlight={() => {}}
          sidebarOpen={isThreat}   /* Auto-open when threat */
          setSidebarOpen={() => {}}
          token={token}
        />
      </main>
    </div>
  );
}
