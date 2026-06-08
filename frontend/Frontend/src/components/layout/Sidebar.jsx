import React from 'react';
import { AlertTriangle, X } from 'lucide-react';

const EntityCard = ({ ent, setHighlight, setSidebarOpen }) => {
  const color = ent.type === 'high' ? '#FF3B3B' : ent.type === 'mid' ? '#FFD60A' : '#00FF9C';
  
  return (
    <div 
      className="mb-3 flex bg-[#030B17]/40 border border-white/5 hover:bg-[#E2E8F0]/[0.05] transition-all cursor-pointer group relative overflow-hidden"
      onClick={() => {
        setHighlight(ent.id.split('-')[1]);
        if (window.innerWidth < 1024) setSidebarOpen(false);
      }}
      onMouseEnter={() => setHighlight(ent.id.split('-')[1])}
      onMouseLeave={() => setHighlight(null)}
    >
      <div className="w-[3px] shrink-0" style={{ backgroundColor: color }} />

      <div className="grow p-2.5 px-3 flex flex-col">
        <div className="flex justify-between items-center">
          <div className="flex flex-col">
            <span className="text-[12px] font-black tracking-widest text-[#00F5FF] leading-none uppercase">{ent.id}</span>
            <span className="text-[9px] text-[#94A3B8]/50 font-medium uppercase tracking-widest mt-1.5">{ent.distance ? `${ent.distance}m` : 'SIGNALING'} | {ent.status}</span>
          </div>
          <span className="text-[24px] font-black tracking-tighter tabular-nums leading-none" style={{ color }}>
             {(ent.score / 100).toFixed(2)}
          </span>
        </div>
        
        <div className="w-full h-[2px] mt-2.5 mb-2 bg-white/5 relative overflow-hidden">
           <div className="h-full absolute left-0 top-0 transition-all duration-700 ease-out" style={{ width: `${Math.min(ent.score, 100)}%`, backgroundColor: color }} />
        </div>

        <div className="flex justify-between items-end">
          <div className="flex flex-col select-none">
             <span className="text-[8px] text-[#E2E8F0]/30 font-black leading-none mb-0.5">
                {ent.score >= 70 ? 'CRITICAL' : ent.score >= 40 ? 'WARNING' : 'STABLE'}
             </span>
             <span className="text-[9px] text-[#94A3B8] font-black uppercase tracking-[0.15em] transition-colors group-hover:text-[#E2E8F0] leading-none">
                {ent.status}
             </span>
          </div>
          <div className="flex items-center">
            {ent.weapon ? (
              <div className="flex items-center gap-1 bg-[#FF3B3B]/20 px-1.5 py-0.5 rounded-sm border border-[#FF3B3B]/30">
                 <AlertTriangle size={7} className="text-[#FF3B3B]" />
                 <span className="text-[7px] font-black text-[#FF3B3B] tracking-widest uppercase">WEAPON</span>
              </div>
            ) : (
              <span className="text-[8px] text-[#94A3B8]/20 font-black tracking-widest uppercase line-through">NON-ARMED</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const Sidebar = ({ entities, alerts, beacons, system, setHighlight, sidebarOpen, setSidebarOpen }) => {
   const { cpu, gpu, memory, disk } = system || { cpu: 0, gpu: 0, memory: 0, disk: 0 };
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

         <div className="flex flex-col mt-2">
            <div className="px-5 py-2 flex justify-between items-center opacity-40">
               <h3 className="text-[9px] font-black tracking-[0.4em] text-[#94A3B8] uppercase">
                  ACTIVE_NODES
               </h3>
               <span className="text-[10px] text-[#00F5FF] font-black tabular-nums">{entities.length}</span>
            </div>
            <div className="px-1 flex flex-col">
              {entities.map(e => <EntityCard key={e.id} ent={e} setHighlight={setHighlight} setSidebarOpen={setSidebarOpen} />)}
              {entities.length === 0 && <div className="px-5 py-8 text-center text-[#94A3B8]/20 text-[10px] font-black uppercase tracking-widest border border-dashed border-white/5 mx-4">Zero_Targets</div>}
            </div>
         </div>

         <div className="mt-4 px-5 flex flex-col">
            <div className="flex justify-between items-center mb-3 border-b border-white/5 pb-1 opacity-40">
               <h3 className="text-[8px] font-black tracking-[0.4em] text-[#94A3B8] uppercase">
                  RECENT_ALERTS
               </h3>
            </div>
            <div className="flex flex-col gap-3">
              {alerts.slice(0, 3).map((alert, i) => (
                <div key={i} className="flex gap-4 relative group cursor-pointer hover:bg-white/[0.02] p-2 -ml-2 transition-colors">
                  <div className={`shrink-0 w-1.5 h-1.5 rounded-full mt-1.5 ${alert.level === 'danger' ? 'bg-[#FF3B3B] animate-pulse shadow-[0_0_8px_#FF3B3B]' : 'bg-[#FFD60A] shadow-[0_0_8px_#FFD60A77]'}`} />
                  <div className="flex flex-col gap-1 w-full">
                     <div className="flex justify-between text-[11px] font-black leading-none tracking-tight">
                        <span className="text-[#00F5FF]/80">{alert.id} // {(alert.score/100).toFixed(2)}</span>
                        <span className="text-[#94A3B8] opacity-30 tabular-nums text-[9px]">{alert.time}</span>
                     </div>
                     <p className="text-[10px] text-[#94A3B8] leading-tight font-bold tracking-tight uppercase group-hover:text-[#E2E8F0] transition-colors">{alert.txt}</p>
                  </div>
                </div>
              ))}
              {alerts.length === 0 && <div className="text-[#94A3B8]/40 text-[9px] font-black tracking-widest uppercase text-center py-4">Logs_Clear</div>}
            </div>
         </div>

         <div className="mt-auto px-5 flex flex-col mb-4 pt-6">
            <h3 className="text-[8px] font-black tracking-[0.3em] text-[#94A3B8]/30 uppercase mb-2">BEACON_MESH</h3>
            <div className="grid grid-cols-2 gap-1.5">
               {beacons.map(b => (
                 <div key={b.id} className="bg-[#030B17]/40 border border-[#E2E8F0]/5 p-1.5 flex flex-col gap-0.5 hover:border-[#00F5FF]/30 transition-colors">
                    <div className="flex items-center gap-1.5">
                       <div className="w-1 h-1 rounded-full bg-[#00FF9C] shadow-[0_0_5px_#00FF9C88]" />
                       <span className="text-[7px] font-black text-[#E2E8F0] tracking-widest">{b.id}</span>
                    </div>
                    <div className="flex justify-between text-[6px] font-black text-[#94A3B8]/40">
                       <span className="truncate mr-1">{b.label}</span>
                       <span className="tabular-nums">{b.fps}</span>
                    </div>
                 </div>
               ))}
            </div>
         </div>

         {/* SYSTEM METRICS GRID (COMPACT) */}
         <div className="p-5 flex flex-col gap-3 border-t border-white/5 bg-[#00F5FF]/[0.01]">
            <h3 className="text-[8px] font-black tracking-[0.3em] text-[#94A3B8]/30 uppercase">SYSTEM</h3>
            <div className="grid grid-cols-2 gap-2">
               {[
                  { label: 'CPU', val: `${cpu}%`, col: cpu > 50 ? 'text-[#FFD60A]' : 'text-[#00F5FF]' },
                  { label: 'GPU', val: `${gpu}%`, col: gpu > 50 ? 'text-[#FFD60A]' : 'text-[#00FF9C]' },
                  { label: 'RAM', val: `${memory}G`, col: 'text-[#00FF9C]' },
                  { label: 'DSK', val: `${disk}G`, col: 'text-[#00FF9C]' }
               ].map((m, i) => (
                  <div key={i} className="bg-[#030B17]/40 border border-white/5 p-1.5 flex flex-col gap-0.5 shadow-inner">
                     <span className="text-[8px] font-black text-[#94A3B8]/40 uppercase tracking-widest leading-none">{m.label}</span>
                     <span className={`text-[12px] font-black tabular-nums leading-none ${m.col} tracking-tighter`}>{m.val}</span>
                  </div>
               ))}
            </div>
         </div>

         {/* BEACON BAR CHART (COMPACT) */}
         <div className="mt-auto px-5 pb-5 flex flex-col">
            <div className="flex items-center justify-between h-6 gap-0.5">
               {beacons.map((b, i) => (
                  <div 
                    key={i} 
                    className="flex-1 bg-white/[0.03] relative h-full rounded-t-[1px] overflow-hidden"
                  >
                     <div 
                        className={`absolute bottom-0 left-0 right-0 transition-all duration-700 animate-heartbeat ${b.fps > 20 ? 'bg-[#00FF9C]' : b.fps > 0 ? 'bg-[#FF3B3B]' : 'bg-[#94A3B8]/05'}`}
                        style={{ 
                           height: `${Math.max(10, (b.fps / 30) * 100)}%`,
                           animationDelay: `${i * 150}ms`
                        }}
                     />
                  </div>
               ))}
            </div>
         </div>
      </aside>
    </>
  );
};

export default Sidebar;
