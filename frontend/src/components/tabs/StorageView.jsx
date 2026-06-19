import React, { useState } from 'react';
import Video from 'lucide-react/dist/esm/icons/video';
import X from 'lucide-react/dist/esm/icons/x';
import Fingerprint from 'lucide-react/dist/esm/icons/fingerprint-pattern';
import Activity from 'lucide-react/dist/esm/icons/activity';
import Radio from 'lucide-react/dist/esm/icons/radio';
import Box from 'lucide-react/dist/esm/icons/box';
import Search from 'lucide-react/dist/esm/icons/search';
import FileJson from 'lucide-react/dist/esm/icons/file-json';
import Trash2 from 'lucide-react/dist/esm/icons/trash-2';
import { API_BASE } from '../../config';

const StorageView = ({
   incidents
}) => {
   const [selectedClip, setSelectedClip] = useState(null);
   const [reportLoading, setReportLoading] = useState(false);
   
   const selectedIncident = incidents.find(i => i.filename === selectedClip);
   const selectedReport = selectedIncident?.report || null;
   const [searchTerm, setSearchTerm] = useState('');
   const videoUrl = selectedClip ? `${API_BASE}/clips/${selectedClip}` : null;

   const filteredIncidents = incidents.filter(inc =>
      inc.filename.toLowerCase().includes(searchTerm.toLowerCase())
   );

   const handleDelete = async (e, filename) => {
      e.stopPropagation();
      if (window.confirm(`PERMANENTLY DELETE FORENSIC INCIDENT: ${filename}?`)) {
         try {
            await fetch(`${API_BASE}/api/incidents/${filename}`, { 
               method: 'DELETE',
               headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
            });
            if (selectedClip === filename) setSelectedClip(null);
         } catch (err) {
            console.error("Delete failed", err);
         }
      }
   };

   const handleClearAll = async () => {
      if (window.confirm("PERMANENTLY DELETE ALL REPLAYS? This action cannot be undone.")) {
         try {
            await fetch(`${API_BASE}/api/clips/clear`, { 
               method: 'DELETE',
               headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
            });
            setSelectedClip(null);
            // Parent should fetch incidents, but it updates periodically anyway
         } catch (err) {
            console.error("Clear all failed", err);
         }
      }
   };

   return (
      <div className="w-full h-full flex flex-col lg:flex-row animate-in fade-in duration-500 overflow-hidden bg-[#020617]">

         {/* UNIFIED SIDEBAR: INCIDENT MANIFEST */}
         <div className="w-full lg:w-[320px] h-[280px] lg:h-full shrink-0 border-b lg:border-r border-white/5 flex flex-col bg-[#030B17]/60 shadow-2xl">
            <div className="p-4 border-b border-white/5 bg-[#00F5FF]/[0.02] flex flex-col gap-3">
               <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                     <Radio size={14} className="text-[#00F5FF] animate-pulse" />
                     <span className="text-[10px] font-black tracking-[0.2em] text-[#E2E8F0] uppercase">FORENSIC_MANIFEST</span>
                  </div>
                  <div className="flex items-center gap-2">
                     <span className="text-[9px] font-black text-[#00F5FF] tabular-nums bg-black/40 border border-[#00F5FF]/20 px-2 py-0.5 rounded-sm shadow-[0_0_10px_#00F5FF22]">{filteredIncidents.length}</span>
                     <button
                        onClick={handleClearAll}
                        className="text-[9px] font-black tracking-widest text-[#FF3B3B] uppercase bg-[#FF3B3B]/10 hover:bg-[#FF3B3B]/20 border border-[#FF3B3B]/30 px-2 py-0.5 rounded transition-colors flex items-center gap-1"
                        title="Delete All Recordings"
                     >
                        <Trash2 size={10} /> CLEAR ALL
                     </button>
                  </div>
               </div>

               <div className="relative">
                  <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]/20" />
                  <input
                     type="text"
                     value={searchTerm}
                     onChange={(e) => setSearchTerm(e.target.value)}
                     placeholder="SEARCH_BY_ID_OR_TIME..."
                     className="w-full bg-black/40 border border-white/5 pl-8 pr-3 py-1.5 text-[9px] text-[#E2E8F0] font-black tracking-widest focus:border-[#00F5FF]/30 outline-none placeholder:text-[#94A3B8]/20"
                  />
               </div>
            </div>

            {/* COMPACT GRID OF CLIP THUMBNAILS */}
            <div className="grow overflow-y-auto custom-scrollbar p-2 grid grid-cols-3 gap-1.5 bg-[#020408]/40 content-start">
               {filteredIncidents.map((inc, i) => {
                  const isSelected = selectedClip === inc.filename;
                  return (
                     <div
                        key={i}
                        onClick={() => setSelectedClip(inc.filename)}
                        className={`group relative flex flex-col aspect-video transition-all cursor-pointer border rounded-xs overflow-hidden ${isSelected ? 'bg-[#00F5FF]/10 border-[#00F5FF]/40 shadow-[0_0_10px_#00F5FF22]' : 'bg-[#030B17]/40 border-white/5 hover:bg-white/[0.03] hover:border-white/10'}`}
                     >
                        {/* SIMULATED THUMBNAIL OVERLAY */}
                        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent z-0" />

                        {/* DELETE BUTTON */}
                        <button
                           onClick={(e) => handleDelete(e, inc.filename)}
                           className="absolute top-1 right-1 p-1.5 bg-black/60 hover:bg-red-500/80 text-white/40 hover:text-white rounded-sm opacity-0 group-hover:opacity-100 transition-all z-20"
                        >
                           <Trash2 size={10} />
                        </button>

                        <div className="mt-auto p-2 relative z-10">
                           <span className="text-[8px] font-black text-[#00F5FF] block truncate mb-0.5">
                              {inc.filename.split('_')[1] || 'INC-00'}
                           </span>
                           <span className="text-[7px] font-bold text-[#E2E8F0]/40 block tabular-nums">
                              {(() => {
                                 if (inc.time) return new Date(inc.time * 1000).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit' });
                                 return '--:--';
                              })()}
                           </span>
                        </div>
                     </div>
                  );
               })}
               {incidents.length === 0 && (
                  <div className="col-span-2 flex flex-col items-center justify-center py-20 bg-[#030B17]/20 border border-dashed border-white/5 rounded-sm">
                     <Box size={24} className="text-[#94A3B8]/20 mb-2" />
                     <span className="text-[8px] font-black text-[#94A3B8]/20 uppercase tracking-[0.2em]">Storage_Null</span>
                  </div>
               )}
            </div>
         </div>

         {/* MAIN VIEWER: ANALYTICS THEATER */}
         <div className="grow flex flex-col min-w-0 min-h-0 bg-[#000408]">
            {selectedClip ? (
               <div className="grow flex flex-col overflow-y-auto custom-scrollbar min-h-0 p-4 lg:p-6 gap-6">

                  {/* COMPACT STAGE */}
                  <div className="w-full bg-black border border-white/5 relative shadow-2xl overflow-hidden group flex-shrink-0" style={{ aspectRatio: '16/9', minHeight: '300px' }}>
                     <video
                        key={videoUrl}
                        controls
                        autoPlay
                        muted
                        playsInline
                        className="w-full h-full object-contain bg-black"
                     >
                        <source src={videoUrl} type="video/mp4" />
                        Your browser does not support the video tag.
                     </video>
                     <div className="absolute top-3 right-3 flex flex-col items-end gap-1.5 pointer-events-none">
                        <div className="bg-black/60 backdrop-blur-md border border-[#FF3B3B]/30 px-2 py-0.5 text-[7px] font-black text-[#FF3B3B] tracking-widest uppercase flex items-center gap-1.5">
                           <div className="w-1 h-1 rounded-full bg-[#FF3B3B] animate-pulse" /> [LIVE_REC]
                        </div>
                        <div className="bg-black/40 backdrop-blur-md border border-[#00F5FF]/20 px-2 py-0.5 text-[7px] font-black text-[#00F5FF] tracking-widest uppercase">
                           CH: P-ENG_06
                        </div>
                        <div className="bg-black/40 backdrop-blur-md border border-white/5 px-2 py-0.5 text-[6px] font-black text-[#94A3B8] tracking-widest uppercase">
                           {selectedClip.slice(0, 15)}...
                        </div>
                     </div>
                  </div>

                  {/* FORENSIC INTELLIGENCE GRID */}
                  <div className={`flex flex-col gap-4 animate-in slide-in-from-bottom duration-500 relative ${reportLoading ? 'opacity-30' : 'opacity-100'}`}>
                     {reportLoading && (
                        <div className="absolute inset-x-0 -top-2 flex items-center justify-center z-10">
                           <div className="flex items-center gap-3 bg-[#030B17] border border-[#00F5FF]/20 px-4 py-2 shadow-2xl">
                              <Radio size={12} className="text-[#00F5FF] animate-spin" />
                              <span className="text-[10px] font-black text-[#00F5FF] tracking-[0.3em] uppercase">Syncing_Telemetry...</span>
                           </div>
                        </div>
                     )}

                     <div className="flex flex-col md:flex-row justify-between items-start md:items-end border-b border-[#00F5FF]/10 pb-4 gap-4">
                        <div className="flex flex-col">
                           <div className="flex items-center gap-2">
                              <Fingerprint size={16} className="text-[#00F5FF]" />
                              <h3 className="text-lg font-black text-[#E2E8F0] tracking-tight uppercase leading-none">Intelligence_Summary</h3>
                           </div>
                           <span className="text-[9px] font-black text-[#00F5FF]/40 uppercase tracking-[0.4em] mt-2">Target_ID: ENT-{selectedReport?.entity_id || 'UNK'} // Type: {selectedReport?.incident_type || 'GENERAL'}</span>
                        </div>

                        <a
                           href={`${API_BASE}/clips/${selectedClip.replace('.mp4', '_report.json')}`}
                           target="_blank"
                           rel="noreferrer"
                           className="flex items-center gap-2 bg-[#00F5FF]/10 hover:bg-[#00F5FF]/20 border border-[#00F5FF]/20 px-3 py-1.5 transition-all group"
                        >
                           <FileJson size={12} className="text-[#00F5FF]" />
                           <span className="text-[9px] font-black text-[#00F5FF] uppercase tracking-widest">Open_Raw_JSON</span>
                        </a>
                     </div>

                     {/* COMPACT METRIC STRIP */}
                     <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-0.5 bg-white/5 border border-white/5 p-0.5 shadow-inner">
                        {[
                           { label: 'Threat_Score', val: selectedReport?.threat_score || 0, col: selectedReport?.threat_score >= 70 ? 'text-[#FF3B3B]' : 'text-[#FFD60A]' },
                           { label: 'Record_Stamp', val: selectedReport?.timestamp || '--', col: 'text-[#E2E8F0]' },
                           { label: 'Observed_ID', val: `ENT-${selectedReport?.entity_id}`, col: 'text-[#00F5FF]' },
                           { label: 'Velocity_Avg', val: (selectedReport?.motion?.avg_speed_px_frame || 0).toFixed(1) + ' px/f', col: 'text-[#94A3B8]' },
                           { label: 'Analysis_Sts', val: 'VERIFIED', col: 'text-[#00FF9C]' }
                        ].map((m, i) => (
                           <div key={i} className="bg-[#030B17] p-3 flex flex-col gap-1">
                              <span className="text-[7px] font-black text-[#94A3B8]/30 uppercase tracking-[0.2em]">{m.label}</span>
                              <span className={`text-sm font-black tabular-nums ${m.col}`}>{m.val}</span>
                           </div>
                        ))}
                     </div>

                     <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                        <div className="bg-[#030B17]/60 border border-white/5 p-4 flex flex-col gap-4">
                           <div className="flex items-center gap-2 border-b border-white/5 pb-2">
                              <Activity size={12} className="text-[#00F5FF]" />
                              <span className="text-[9px] font-black text-[#E2E8F0] uppercase tracking-widest">Incident_Dynamics</span>
                           </div>
                           <div className="flex flex-col gap-3">
                              <div className="flex justify-between items-center bg-black/20 p-2 border-l border-[#00F5FF]">
                                 <span className="text-[8px] font-black text-[#94A3B8]/40 uppercase">Detected_Behavior</span>
                                 <span className="text-[10px] font-black text-[#E2E8F0] uppercase tracking-tighter">{selectedReport?.incident_type}</span>
                              </div>
                              <div className="flex justify-between items-center bg-black/20 p-2 border-l border-[#FFD60A]">
                                 <span className="text-[8px] font-black text-[#94A3B8]/40 uppercase">Timeline_Ref</span>
                                 <span className="text-[10px] font-black text-[#E2E8F0] uppercase tracking-tighter">{selectedReport?.motion?.current_time}</span>
                              </div>
                           </div>
                        </div>

                        <div className="bg-[#030B17]/60 border border-white/5 p-4 flex flex-col gap-4">
                           <div className="flex items-center gap-2 border-b border-white/5 pb-2">
                              <Fingerprint size={12} className="text-[#FF3B3B]" />
                              <span className="text-[9px] font-black text-[#E2E8F0] uppercase tracking-widest">Forensic_Telemetry</span>
                           </div>
                           <div className="space-y-3">
                              <div className="text-[8px] text-[#94A3B8] leading-relaxed">
                                 This incident was automatically captured following a Level 3 (High) threat trigger.
                                 The video contains 6 seconds of pre-buffer activity and 8 seconds of post-trigger surveillance.
                              </div>
                              <div className="flex items-center gap-4 py-2 border-t border-white/5">
                                 <div className="flex flex-col">
                                    <span className="text-[7px] text-[#94A3B8]/40 uppercase font-black">Status</span>
                                    <span className="text-[9px] text-[#00FF9C] font-black">ARCHIVED</span>
                                 </div>
                                 <div className="flex flex-col">
                                    <span className="text-[7px] text-[#94A3B8]/40 uppercase font-black">Encryption</span>
                                    <span className="text-[9px] text-[#E2E8F0] font-black">AES-256</span>
                                 </div>
                              </div>
                           </div>
                        </div>
                     </div>
                  </div>
               </div>
            ) : (
               <div className="grow flex flex-col items-center justify-center opacity-10 bg-[#030B17]/10">
                  <div className="w-32 h-32 border border-dashed border-white/10 rounded-full flex items-center justify-center animate-[spin_20s_linear_infinite] mb-6">
                     <Video size={32} className="text-white" />
                  </div>
                  <span className="text-[12px] font-black tracking-[0.5em] text-white uppercase">Waiting_For_Input</span>
                  <span className="text-[8px] font-bold uppercase tracking-[0.2em] mt-3 text-[#94A3B8]">Initialize Manifest Selection Sequence</span>
               </div>
            )}
         </div>
      </div>
   );
};

export default StorageView;
