import React from 'react';
import AlertCircle from 'lucide-react/dist/esm/icons/alert-circle';
import Target from 'lucide-react/dist/esm/icons/target';
import Database from 'lucide-react/dist/esm/icons/database';
import Activity from 'lucide-react/dist/esm/icons/activity';
import { API_BASE } from '../../config';

const EntityTracker = ({ entities, setHighlight, setActiveTab }) => {
   return (
      <div className="w-full h-full flex flex-col animate-in fade-in duration-500 overflow-hidden bg-[#020617]">

         {/* UNIFIED TAB HEADER */}
         <div className="flex flex-col md:flex-row justify-between items-start md:items-end border-b border-[#00F5FF]/10 pb-4 mb-6 relative gap-4 px-4 lg:px-6 pt-4 lg:pt-6">
            <div className="flex flex-col">
               <div className="flex items-center gap-3 mb-1">
                  <Database size={20} className="text-[#00F5FF] drop-shadow-[0_0_8px_#00F5FF]" />
                  <h2 className="text-xl lg:text-2xl font-black text-[#E2E8F0] tracking-[0.1em] uppercase leading-none">Global_Entity_Database</h2>
               </div>
               <div className="flex items-center gap-2 mt-2">
                  <span className="text-[9px] font-black tracking-[0.3em] text-[#00F5FF]/40 uppercase">Secure_Session: Active</span>
                  <div className="w-1 h-1 rounded-full bg-[#00F5FF]/20" />
                  <span className="text-[9px] font-black tracking-[0.3em] text-[#00F5FF]/40 uppercase">Nodes: {entities.length}</span>
               </div>
            </div>

            <div className="flex items-center gap-2 w-full md:w-auto">
               <div className="flex bg-[#030B17] border border-white/5 divide-x divide-white/5 shadow-2xl">
                  <div className="px-4 py-2 flex flex-col items-center justify-center min-w-[80px]">
                     <span className="text-[7px] font-black text-[#94A3B8]/40 uppercase mb-0.5 tracking-widest">Active</span>
                     <span className="text-sm font-black text-[#E2E8F0] tabular-nums">{entities.length.toString().padStart(2, '0')}</span>
                  </div>
                  <div className="px-4 py-2 flex flex-col items-center justify-center min-w-[80px]">
                     <span className="text-[7px] font-black text-[#FF3B3B]/40 uppercase mb-0.5 tracking-widest">Danger</span>
                     <span className="text-sm font-black text-[#FF3B3B] tabular-nums">{entities.filter(e => e.type === 'high').length.toString().padStart(2, '0')}</span>
                  </div>
               </div>
            </div>
            {/* DECORATIVE LINE */}
            <div className="absolute bottom-[-1px] left-0 w-24 h-[1px] bg-[#00F5FF] shadow-[0_0_10px_#00F5FF]" />
         </div>

         {/* TACTICAL GRID */}
         <div className="grow overflow-y-auto px-4 lg:px-6 pb-6 custom-scrollbar">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3 content-start">
               {entities.map((ent, i) => (
                  <div
                     key={i}
                     onClick={async () => {
                        const eid = ent.id.split('-')[1];
                        setHighlight(eid);
                        setActiveTab('LIVE FEED');
                        try {
                           await fetch(`${API_BASE}/api/highlight/${eid}`, { method: 'POST' });
                        } catch (e) { }
                     }}
                     className="relative group/card bg-[#030B17]/60 border border-white/5 p-3 flex flex-col gap-3 hover:border-[#00F5FF]/40 transition-all cursor-pointer overflow-hidden group/card"
                  >
                     {/* HUD ELEMENTS */}
                     <div className="absolute top-0 left-0 w-1.5 h-1.5 border-t border-l border-[#00F5FF]/30 group-hover/card:border-[#00F5FF]" />
                     <div className="absolute top-0 right-0 w-1.5 h-1.5 border-t border-r border-[#00F5FF]/30 group-hover/card:border-[#00F5FF]" />
                     <div className="absolute bottom-0 left-0 w-1.5 h-1.5 border-b border-l border-[#00F5FF]/30 group-hover/card:border-[#00F5FF]" />
                     <div className="absolute bottom-0 right-0 w-1.5 h-1.5 border-b border-r border-[#00F5FF]/30 group-hover/card:border-[#00F5FF]" />

                     {/* COMPACT HEADER */}
                     <div className="flex justify-between items-start z-10">
                        <div className="flex flex-col">
                           <div className="flex items-center gap-1.5">
                              <Activity size={10} className={ent.type === 'high' ? 'text-[#FF3B3B]' : 'text-[#00F5FF]'} />
                              <span className="text-[#00F5FF] text-[11px] font-black tracking-widest leading-none">{ent.id}</span>
                           </div>
                           <span className="text-[7px] font-bold text-[#94A3B8]/40 uppercase tracking-widest mt-1">Status: {ent.status}</span>
                        </div>
                        <div className={`px-1.5 py-0.5 text-[7px] font-black uppercase tracking-widest ${ent.type === 'high' ? 'bg-[#FF3B3B] text-white' : 'bg-white/5 text-[#94A3B8]/60'}`}>
                           {ent.type === 'high' ? 'P-1' : 'TRK'}
                        </div>
                     </div>

                     {/* SCANNER BAR */}
                     <div className="flex items-end justify-between gap-3 z-10">
                        <div className="flex flex-col grow">
                           <div className="flex justify-between text-[7px] font-black text-[#94A3B8]/30 mb-1 uppercase tracking-tighter">
                              <span>Threat_Coeff</span>
                              <span className={ent.type === 'high' ? 'text-[#FF3B3B]' : 'text-[#00F5FF]'}>{(ent.score / 100).toFixed(2)}</span>
                           </div>
                           <div className="w-full h-[2px] bg-white/5 overflow-hidden">
                              <div
                                 className={`h-full transition-all duration-1000 ${ent.type === 'high' ? 'bg-[#FF3B3B]' : ent.type === 'mid' ? 'bg-[#FFD60A]' : 'bg-[#00F5FF]'}`}
                                 style={{ width: `${ent.score}%` }}
                              />
                           </div>
                        </div>
                        <div className={`text-2xl font-black tabular-nums leading-none tracking-tighter ${ent.type === 'high' ? 'text-[#FF3B3B]' : 'text-[#E2E8F0]'}`}>
                           {(ent.score / 100).toFixed(2)}
                        </div>
                     </div>

                     {/* DATA STRIP */}
                     <div className="grid grid-cols-2 gap-2 z-10 pt-3 border-t border-white/5">
                        <div className="flex flex-col">
                           <span className="text-[6px] font-black text-[#94A3B8]/30 uppercase tracking-widest">Range</span>
                           <span className="text-[9px] font-black text-[#E2E8F0] tracking-widest leading-none mt-1 truncate">{ent.distance ? `${ent.distance}m` : 'SCANNING'}</span>
                        </div>
                        <div className="flex flex-col items-end">
                           <span className="text-[6px] font-black text-[#94A3B8]/30 uppercase tracking-widest">Behavior</span>
                           <span className="text-[9px] font-black text-[#E2E8F0] tracking-widest tabular-nums mt-1 leading-none">{ent.status}</span>
                        </div>
                     </div>

                     {ent.weapon && (
                        <div className="bg-[#FF3B3B]/10 border border-[#FF3B3B]/20 p-1.5 flex items-center justify-center gap-2 animate-pulse rounded-sm">
                           <AlertCircle size={10} className="text-[#FF3B3B]" />
                           <span className="text-[8px] font-black text-[#FF3B3B] uppercase tracking-[0.1em]">WEAPON_DETECTED</span>
                        </div>
                     )}

                     {/* HOVER INTERACTION */}
                     <div className="absolute inset-0 bg-[#00F5FF]/5 opacity-0 group-hover/card:opacity-100 flex items-center justify-center transition-all">
                        <button className="bg-[#00F5FF] text-black text-[10px] font-black px-4 py-1.5 uppercase tracking-widest shadow-[0_0_15px_#00F5FF]">Lock_Node</button>
                     </div>
                  </div>
               ))}

               {entities.length === 0 && (
                  <div className="col-span-full py-20 flex flex-col items-center justify-center opacity-20 border border-dashed border-white/5">
                     <Target size={32} className="mb-3 animate-pulse" />
                     <span className="text-[9px] font-black tracking-[0.4em] uppercase">Scanning_Subnets...</span>
                  </div>
               )}
            </div>
         </div>
      </div>
   );
};

export default EntityTracker;
