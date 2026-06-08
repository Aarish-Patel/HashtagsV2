import React from 'react';
import { Search, Download, AlertCircle, ShieldAlert, FileText } from 'lucide-react';

const AlertHistory = ({ 
  filteredHistory, 
  alertFilters, 
  setAlertFilters, 
  exportCSV, 
  incidents, 
  setSelectedClip, 
  setActiveTab 
}) => {
  return (
    <div className="w-full h-full flex flex-col animate-in fade-in duration-500 overflow-hidden bg-[#020617]">
       
       {/* UNIFIED TAB HEADER */}
       <div className="flex flex-col xl:flex-row justify-between items-start xl:items-end border-b border-[#00F5FF]/10 pb-4 mb-6 relative gap-6 px-4 lg:px-6 pt-4 lg:pt-6">
          <div className="flex flex-col">
             <div className="flex items-center gap-3 mb-1">
                <ShieldAlert size={20} className="text-[#FF3B3B] drop-shadow-[0_0_8px_#FF3B3B]" />
                <h2 className="text-xl lg:text-2xl font-black text-[#E2E8F0] tracking-[0.1em] uppercase leading-none">Forensic_Archive</h2>
             </div>
             <div className="flex items-center gap-2 mt-2">
                <span className="text-[9px] font-black tracking-[0.3em] text-[#00F5FF]/40 uppercase">Journal_Status: Indexed</span>
                <div className="w-1 h-1 rounded-full bg-[#00F5FF]/20" />
                <span className="text-[9px] font-black tracking-[0.3em] text-[#00F5FF]/40 uppercase">{filteredHistory.length} Record_Entries</span>
             </div>
          </div>
          
          <div className="flex flex-wrap items-center gap-3 w-full xl:w-auto">
             <div className="flex bg-[#030B17] border border-white/5 p-0.5 rounded-sm">
                {['ALL', 'DANGER'].map(l => (
                  <button 
                    key={l}
                    onClick={() => setAlertFilters(prev => ({ ...prev, level: l }))}
                    className={`px-3 py-1.5 text-[8px] font-black transition-all rounded-sm uppercase tracking-widest ${alertFilters.level === l ? 'bg-[#00F5FF] text-black shadow-[0_0_10px_#00F5FF44]' : 'text-[#94A3B8]/40 hover:text-[#E2E8F0]'}`}
                  >
                    {l}
                  </button>
                ))}
             </div>
             
             <button 
               onClick={() => setAlertFilters(prev => ({ ...prev, weapon: !prev.weapon }))}
               className={`px-3 py-2 border text-[8px] font-black tracking-[0.2em] transition-all rounded-sm uppercase ${alertFilters.weapon ? 'border-[#FF3B3B] bg-[#FF3B3B]/10 text-[#FF3B3B]' : 'border-white/5 text-[#94A3B8]/40 hover:bg-white/5 hover:text-[#94A3B8]'}`}
             >
                {alertFilters.weapon ? 'Weapon_Lock: On' : 'Weapon_Filter'}
             </button>

             <div className="relative grow max-w-sm">
                <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#94A3B8]/20" />
                <input 
                  value={alertFilters.search}
                  onChange={(e) => setAlertFilters(prev => ({ ...prev, search: e.target.value }))}
                  placeholder="ID_OR_EVENT_QUERY..." 
                  className="bg-[#030B17] border border-white/5 pl-9 pr-4 py-2 text-[9px] text-[#E2E8F0] font-black tracking-widest focus:border-[#00F5FF]/30 outline-none w-full shadow-inner placeholder:text-[#94A3B8]/20"
                />
             </div>

             <button 
               onClick={exportCSV}
               className="bg-[#00FF9C]/10 border border-[#00FF9C]/20 text-[#00FF9C] px-3 py-2 text-[8px] font-black hover:bg-[#00FF9C] hover:text-black transition-all uppercase tracking-widest flex items-center gap-2 rounded-sm"
             >
                <Download size={10} /> Export_Report
             </button>
          </div>
          <div className="absolute bottom-[-1px] left-0 w-24 h-[1px] bg-[#FF3B3B] shadow-[0_0_10px_#FF3B3B]" />
       </div>

       {/* TABLE VIEW (Desktop) */}
       <div className="hidden md:block grow overflow-y-auto custom-scrollbar border border-white/5 bg-[#030B17]/20 shadow-2xl">
          <table className="w-full text-left border-collapse">
             <thead className="sticky top-0 bg-[#040C1D] z-10 border-b border-white/10 shadow-lg">
                <tr>
                   <th className="px-4 py-2 text-[8px] font-black text-[#94A3B8]/40 uppercase tracking-widest">Temporal_Stamp</th>
                   <th className="px-4 py-2 text-[8px] font-black text-[#94A3B8]/40 uppercase tracking-widest">Entity_ID</th>
                   <th className="px-4 py-2 text-[8px] font-black text-[#94A3B8]/40 uppercase tracking-widest">Range</th>
                   <th className="px-4 py-2 text-[8px] font-black text-[#94A3B8]/40 uppercase tracking-widest">Threat_Coeff</th>
                   <th className="px-4 py-2 text-[8px] font-black text-[#94A3B8]/40 uppercase tracking-widest">Event_Manifest</th>
                   <th className="px-4 py-2 text-[8px] font-black text-[#94A3B8]/40 uppercase tracking-widest text-right">Actions</th>
                </tr>
             </thead>
             <tbody className="divide-y divide-white/[0.03]">
                {filteredHistory.map((a, i) => (
                   <tr key={i} className="hover:bg-[#00F5FF]/[0.02] transition-colors group">
                      <td className="px-4 py-1.5 text-[9px] font-black text-[#94A3B8]/60 tabular-nums">{a.time}</td>
                      <td className="px-4 py-1.5 text-[9px] font-black text-[#00F5FF] tracking-widest uppercase">{a.id}</td>
                      <td className="px-4 py-1.5 text-[9px] font-black text-[#E2E8F0] tracking-widest">{a.distance ? `${a.distance}m` : '--'}</td>
                      <td className="px-4 py-1.5">
                         <div className="flex items-center gap-3">
                            <div className="w-16 h-[2px] bg-white/5 overflow-hidden">
                               <div 
                                 className={`h-full ${a.level === 'danger' ? 'bg-[#FF3B3B]' : 'bg-[#FFD60A]'}`} 
                                 style={{ width: `${a.score}%` }} 
                               />
                            </div>
                            <span className={`text-[10px] font-black tabular-nums ${a.level === 'danger' ? 'text-[#FF3B3B]' : 'text-[#FFD60A]'}`}>{(a.score/100).toFixed(2)}</span>
                         </div>
                      </td>
                      <td className="px-4 py-1.5 text-[9px] font-bold text-[#94A3B8] uppercase group-hover:text-[#E2E8F0] transition-colors">
                         <div className="flex items-center gap-2">
                           <span>{a.txt}</span>
                           {a.txt.toLowerCase().includes('weapon') && <span className="text-[7px] bg-[#FF3B3B]/20 text-[#FF3B3B] px-1.5 py-0.5 font-black border border-[#FF3B3B]/20 rounded-sm">ARMED</span>}
                         </div>
                      </td>
                      <td className="px-4 py-1.5 text-right">
                         {a.level === 'danger' && (
                            <button 
                              onClick={() => {
                                 const eid = a.id.split('-')[1];
                                 const filename = incidents.find(inc => inc.filename.includes(`_E${eid}_`))?.filename;
                                 if (filename) {
                                   setSelectedClip(filename);
                                   setActiveTab('STORAGE');
                                 }
                              }}
                              className="opacity-0 group-hover:opacity-100 px-3 py-1 bg-[#00F5FF]/10 text-[#00F5FF] border border-[#00F5FF]/20 text-[7px] font-black hover:bg-[#00F5FF] hover:text-black transition-all uppercase tracking-widest"
                            >
                               View_Node
                            </button>
                         )}
                      </td>
                   </tr>
                ))}
             </tbody>
          </table>
       </div>

       {/* CARD VIEW (Mobile) */}
       <div className="md:hidden grow overflow-y-auto pr-2 custom-scrollbar">
          <div className="flex flex-col gap-1.5 max-w-2xl mx-auto w-full py-4 px-2">
             {filteredHistory.map((a, i) => (
                <div key={i} className="bg-[#030B17] border border-white/5 p-2.5 flex items-center justify-between gap-4 relative overflow-hidden group">
                   <div className={`absolute left-0 top-0 bottom-0 w-[2px] ${a.level === 'danger' ? 'bg-[#FF3B3B]' : 'bg-[#FFD60A]'}`} />
                   
                   <div className="flex flex-col grow min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                         <span className="text-[#00F5FF] text-[10px] font-black tracking-widest uppercase">{a.id}</span>
                         <span className="text-[#94A3B8]/30 text-[7px] font-black uppercase tracking-widest tabular-nums">{a.time}</span>
                      </div>
                      <div className="text-[8px] font-bold text-[#94A3B8] uppercase truncate">{a.txt}</div>
                   </div>

                   <div className="flex items-center gap-3 shrink-0">
                      <span className={`text-[10px] font-black tabular-nums leading-none ${a.level === 'danger' ? 'text-[#FF3B3B]' : 'text-[#FFD60A]'}`}>{(a.score/100).toFixed(2)}</span>
                      {a.level === 'danger' && (
                         <button 
                           onClick={() => {
                              const eid = a.id.split('-')[1];
                              const filename = incidents.find(inc => inc.filename.includes(`_E${eid}_`))?.filename;
                              if (filename) {
                                setSelectedClip(filename);
                                setActiveTab('STORAGE');
                              }
                           }}
                           className="w-6 h-6 flex items-center justify-center bg-[#00F5FF]/10 text-[#00F5FF] border border-[#00F5FF]/20 rounded-sm"
                         >
                            <ShieldAlert size={10} />
                         </button>
                      )}
                   </div>
                </div>
             ))}
          </div>
       </div>

       {filteredHistory.length === 0 && (
          <div className="grow flex flex-col items-center justify-center opacity-10 py-20 bg-[#030B17]/20 border border-white/5">
             <FileText size={48} className="mb-4" />
             <span className="text-[10px] font-black tracking-[0.5em] uppercase">Null_Pointer: No Logs</span>
          </div>
       )}
    </div>
  );
};

export default AlertHistory;
