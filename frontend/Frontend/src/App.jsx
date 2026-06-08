import React, { useState, useEffect } from 'react';
/* 
  Imports:
  React: Main library for building the interface components.
  useState: Allows the dashboard to remember data (like which tab is open).
  useEffect: Runs specific code at set intervals (like fetching camera data every second).
*/

// --- Layout Components (Different parts of the screen) ---
import Header from './components/layout/Header'; // Top bar with logo and clock
import Sidebar from './components/layout/Sidebar'; // Right-side bar with detection list
import Footer from './components/layout/Footer'; // Bottom status bar with uptime
import Terminal from './components/layout/Terminal'; // The scrolling text log at the bottom

// --- Tab Components (The different screens you can switch between) ---
import LiveFeed from './components/tabs/LiveFeed'; // The 4-camera grid view
import EntityTracker from './components/tabs/EntityTracker'; // Detailed stats of every person detected
import AlertHistory from './components/tabs/AlertHistory'; // Searchable list of past security breaches
import StorageView from './components/tabs/StorageView'; // Folder for viewing saved video clips
import { Monitor, Activity } from 'lucide-react';
import { API_BASE } from './config'; // The network address of your Python AI server

export default function App() {
  /* 
    State Variables (Memory):
    These track everything happening on the screen.
  */
  const [activeTab, setActiveTab] = useState('LIVE FEED'); // Which mode are we in?
  const [time, setTime] = useState(''); // Current clock time
  const [uptime, setUptime] = useState(0); // Seconds since the system started
  const [entities, setEntities] = useState([]); // List of current people/weapons seen
  const [isRecording, setIsRecording] = useState(false); // Is the system saving video?
  const [alerts, setAlerts] = useState([]); // List of high-priority security events
  const [logs, setLogs] = useState([]); // Scrolling lines of code in the 'Terminal'
  const [incidents, setIncidents] = useState([]); // List of saved video files on disk
  
  const [highlight, setHighlight] = useState(null); // Which person is being focused on
  const [selectedClip, setSelectedClip] = useState(null); // The video clip currently playing
  const [selectedReport, setSelectedReport] = useState(null); // Data for a specific incident
  const [reportLoading, setReportLoading] = useState(false); // Waiting for report data to load
  
  // System Health (How hard the laptop is working)
  const [system, setSystem] = useState({ cpu: 0, memory: 0, disk: 0, gpu: 0 });
  const [sensors, setSensors] = useState([]); // Online/Offline status of the 4 cameras
  const [beacons, setBeacons] = useState([]); // Bluetooth/Network signal markers (if any)
  
  // Search Filters for the alert history page
  const [alertFilters, setAlertFilters] = useState({ level: 'ALL', weapon: false, search: '' });

  // UI Settings (Is the sidebar open or closed?)
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [terminalOpen, setTerminalOpen] = useState(true);

  // CLOCK: Update the time every 1 second
  useEffect(() => {
    const t = setInterval(() => {
        setTime(new Date().toLocaleTimeString('en-GB')); // Set 24h clock string
        setUptime(u => u + 1); // Increase uptime by 1 second
    }, 1000);
    return () => clearInterval(t); // Stop the clock if the dashboard is closed
  }, []);

  // Format seconds into HH:MM:SS format
  const formatUptime = (secs) => {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = Math.floor(secs % 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // FETCH DATA: This function asks the Python AI for new information
  const fetchData = async () => {
    try {
      // 1. Get Camera Status (Online/Offline) and CPU usage
      const statusRes = await fetch(`${API_BASE}/api/status`);
      const statusData = await statusRes.json();
      setSensors(statusData.sensors || []);
      setSystem(prev => ({ ...prev, ...statusData.system }));
      
      // Build beacon mesh from sensor data
      const beaconData = (statusData.sensors || []).map((s, i) => ({
        id: `NODE-${i+1}`,
        label: s.label || (s.online ? 'ACTIVE' : 'OFFLINE'),
        fps: s.online ? (s.fps || 10) : 0
      }));
      setBeacons(beaconData);

      // 2. Get the list of People and Weapons being 'seen' right now
      const entRes = await fetch(`${API_BASE}/api/entities`);
      const entData = await entRes.json();
      
      // Convert the raw data into a format the GUI understands
      const sortedEnts = (entData.entities || []).map(e => {
        const rawId = (e.id || 0).toString();
        return {
          ...e,
          id: rawId.startsWith('ENT-') ? rawId : `ENT-${rawId}`, 
          score: e.threat_score !== undefined ? e.threat_score : (e.threat_level !== undefined ? (e.threat_level * 25) : (e.score || 0)),
          status: e.status || e.behavior || 'SCANNING',
          type: e.threat_level >= 4 ? 'high' : e.threat_level >= 2 ? 'mid' : 'low',
          distance: e.distance_m || 0,
          weapon: e.class === 'Weapon' || e.behavior?.includes('ARMED')
        };
      }).sort((a, b) => b.score - a.score);

      setEntities(sortedEnts);
      setIsRecording(entData.recording || false);

      // Automated Alert Trigger for new High Threats (Debounced)
      if (sortedEnts.some(e => e.type === 'high')) {
          const highEnt = sortedEnts.find(e => e.type === 'high');
          setAlerts(prev => {
              // Only add if the most recent alert isn't already for this target/behavior
              if (prev.length > 0 && prev[0].id === highEnt.id && prev[0].txt.includes(highEnt.status)) {
                  return prev;
              }
              const newAlert = {
                  id: highEnt.id,
                  level: 'danger',
                  time: new Date().toLocaleTimeString(),
                  txt: `CRITICAL: ${highEnt.status}`,
                  score: highEnt.score
              };
              return [newAlert, ...prev.slice(0, 49)];
          });
      }
      
      // 3. Get the list of security events (breaches/tampering)
      const evtRes = await fetch(`${API_BASE}/api/events?limit=500`);
      const evtData = await evtRes.json();
      
      // Process events for the 'Alert History' tab
      const parsedAlerts = evtData.map(e => ({
          id: e.entity_id || `ENT-${Math.floor(Math.random()*1000)}`,
          score: e.threat_level !== undefined ? (e.threat_level * 25.0) : (e.threat_score || 0),
          txt: e.behavior || e.event || 'SECURITY BREACH',
          time: new Date(e.timestamp).toLocaleTimeString('en-GB'),
          dateObj: new Date(e.timestamp),
          level: (e.threat_level >= 4 || e.threat_score >= 80) ? 'danger' : 'warning',
          weapon: e.weapon_flag || e.class_name === 'Weapon' || (e.behavior && e.behavior.includes('ARMED')),
          zone: e.camera || 'PERIMETER',
          distance: e.distance_m || 0,
          json: e.clip_file ? e.clip_file.replace('.mp4', '_report.json') : null
      }));
      
      parsedAlerts.sort((a,b) => b.dateObj - a.dateObj); // Sort by most recent
      setAlerts(parsedAlerts);
      
      // Process events for the scrolling 'Terminal' text log
      const parsedLogs = evtData.slice(0, 50).map(e => {
          const score = e.threat_level !== undefined ? (e.threat_level * 25.0) : (e.threat_score || 0);
          const behavior = e.behavior || e.event || 'SCANNING';
          return {
            time: `[${new Date(e.timestamp).toLocaleTimeString('en-GB')}]`,
            txt: `[${behavior}] ENT-${e.entity_id} dist=${e.distance_m || '?' }m score=${score.toFixed(0)}`,
            color: score >= 70 ? 'text-[#FF3B3B]' : score >= 45 ? 'text-[#FFD60A]' : 'text-[#00F5FF]'
          };
      });
      setLogs(parsedLogs.reverse());
    } catch (e) {
      console.error("API Read Error:", e); // Error if Python backend is offline
    }
  };

  // Get the list of saved video recordings
  const fetchIncidents = async () => {
    try {
      const incRes = await fetch(`${API_BASE}/api/incidents`);
      if (incRes.ok) {
        setIncidents(await incRes.json());
      }
    } catch (e) {}
  };

  // Main Background Loop: Fetch data every 1 second
  useEffect(() => {
    fetchData();
    const intervalTime = 500;
    const tInterval = setInterval(fetchData, intervalTime);
    return () => clearInterval(tInterval);
  }, [activeTab]);

  // Secondary Loop: Fetch saved clips every 10 seconds
  useEffect(() => {
    fetchIncidents();
    const sInterval = setInterval(fetchIncidents, 10000);
    return () => clearInterval(sInterval);
  }, [activeTab]);

  // Loading Logic: Fetch report data when a video clip is clicked
  useEffect(() => {
    if (selectedClip) {
      const fetchReport = async () => {
        setReportLoading(true);
        setSelectedReport(null);
        try {
          const reportName = selectedClip.replace('.mp4', '_report.json');
          const res = await fetch(`${API_BASE}/incidents/${reportName}`);
          if (res.ok) {
            setSelectedReport(await res.json());
          }
        } catch (e) {} finally {
          setReportLoading(false);
        }
      };
      fetchReport();
    } else {
      setSelectedReport(null);
      setReportLoading(false);
    }
  }, [selectedClip]);

  // User Action: Pinning/Highlighting a specific detected person
  const handleHighlight = async (id) => {
      setHighlight(id);
      try {
          await fetch(`http://localhost:5000/api/highlight/${id || 'none'}`, { method: 'POST' });
      } catch (e) {}
  };

  return (
    <div className="h-screen w-screen bg-[#020617] text-[#94A3B8] font-sans overflow-hidden flex flex-col selection:bg-[#00F5FF]/20 select-none">
      
      {/* 1. Header (The tactical bar at the very top) */}
      <Header 
        entities={entities} 
        time={time} 
        isRecording={isRecording} 
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
        system={system}
      />

      {/* 2. Navigation Tabs */}
      <nav className="h-14 bg-[#030B17] border-b border-[#00F5FF]/20 px-6 flex items-center gap-4 shrink-0 z-40 relative">
        <button 
          onClick={() => setActiveTab('LIVE FEED')}
          className={`flex items-center gap-2 px-6 py-2 rounded-lg transition-all ${activeTab === 'LIVE FEED' ? 'bg-[#00F5FF]/20 text-[#00F5FF] border border-[#00F5FF]/30' : 'text-slate-400 hover:text-white'}`}
        >
          <Monitor size={18} />
          <span className="text-sm font-medium tracking-tight uppercase">01 Live Feed</span>
        </button>
        
        <button 
          onClick={() => setActiveTab('ENTITY TRACKER')}
          className={`flex items-center gap-2 px-6 py-2 rounded-lg transition-all ${activeTab === 'ENTITY TRACKER' ? 'bg-[#00F5FF]/20 text-[#00F5FF] border border-[#00F5FF]/30' : 'text-slate-400 hover:text-white'}`}
        >
          <Activity size={18} />
          <span className="text-sm font-medium tracking-tight uppercase">02 Tactical Tracker</span>
        </button>
      </nav>

      <main className="grow flex overflow-hidden relative">
        {/* 3. Central Content Area */}
        <section className="grow flex flex-col min-w-0 bg-[#030B17] relative border-t lg:border-t-0 border-[#00F5FF]/20 shadow-[0_-2px_10px_#00F5FF33]">
          
          <div className="grow overflow-hidden bg-[#020617]">
             {/* Switches which screen is shown based on your tab selection */}
             {activeTab === 'LIVE FEED' && <LiveFeed sensors={sensors} entities={entities} />}
             {activeTab === 'ENTITY TRACKER' && <EntityTracker entities={entities} setHighlight={handleHighlight} setActiveTab={setActiveTab} />}
          </div>

          {/* 4. Footer (Bottom-most status bar) */}
          <Footer entities={entities} uptime={uptime} alerts={alerts} incidents={incidents} formatUptime={formatUptime} />
          
          {/* 5. Terminal (The code-style log line) */}
          <Terminal 
            logs={logs} 
            terminalOpen={terminalOpen} 
            setTerminalOpen={setTerminalOpen} 
          />

        </section>

        {/* 6. Sidebar (The right-hand list of threats) */}
        <Sidebar 
          entities={entities} 
          alerts={alerts} 
          beacons={beacons} 
          system={system}
          setHighlight={handleHighlight} 
          sidebarOpen={sidebarOpen}
          setSidebarOpen={setSidebarOpen}
        />
      </main>

    </div>
  );
}
