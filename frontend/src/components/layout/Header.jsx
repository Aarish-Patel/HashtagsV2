import React from 'react';
import Menu from 'lucide-react/dist/esm/icons/menu';
import X from 'lucide-react/dist/esm/icons/x';
import Activity from 'lucide-react/dist/esm/icons/activity';
import Cpu from 'lucide-react/dist/esm/icons/cpu';
import ShieldAlert from 'lucide-react/dist/esm/icons/shield-alert';
import ShieldCheck from 'lucide-react/dist/esm/icons/shield-check';

const Header = ({ entities, time, isRecording, mode, sidebarOpen, setSidebarOpen, system, analyzeProgress }) => {
  const isAnalyzing = mode === 'ANALYZING';
  const isThreat = mode === 'THREAT';

  return (
    <header className={`h-12 lg:h-10 border-b px-4 lg:px-6 flex items-center shrink-0 z-50 justify-between relative overflow-hidden transition-colors duration-500
      ${isThreat ? 'bg-[#FF3B3B]/10 border-[#FF3B3B]/50' : 'bg-[#030B17] border-[#E2E8F0]/5'}
    `}>
      
      {/* SCANLINE EFFECT */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.03] bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_2px,3px_100%]" />

      <div className="flex items-center gap-4 z-10">
         <button 
           onClick={() => setSidebarOpen(!sidebarOpen)}
           className={`lg:hidden p-1.5 rounded transition-all active:scale-95 ${isThreat ? 'text-[#FF3B3B] hover:bg-[#FF3B3B]/10' : 'text-[#00F5FF] hover:bg-[#00F5FF]/10'}`}
         >
            {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
         </button>
         
         <div className="flex items-baseline gap-2">
            <span className={`text-[11px] lg:text-[13px] font-black tracking-[0.2em] uppercase ${isThreat ? 'text-[#FF3B3B]' : 'text-[#00F5FF]'}`}>HASHTAGS</span>
            <span className="hidden sm:inline text-[#94A3B8]/30 font-light text-[11px]">//</span>
            <span className="hidden sm:inline text-[#94A3B8] text-[9px] lg:text-[10px] font-medium tracking-[0.3em] uppercase">SURV-CMD</span>
         </div>

         {/* MODE BADGE */}
         <div className="hidden sm:flex items-center ml-4">
           {isThreat ? (
             <div className="flex items-center gap-1.5 px-3 py-1 bg-[#FF3B3B]/20 border border-[#FF3B3B] rounded-sm animate-pulse shadow-[0_0_15px_#FF3B3B44]">
               <ShieldAlert size={12} className="text-[#FF3B3B]" />
               <span className="text-[9px] font-black tracking-widest text-[#FF3B3B] uppercase">THREAT CONFIRMED</span>
             </div>
           ) : isAnalyzing ? (
             <div className="flex items-center gap-1.5 px-3 py-1 bg-yellow-500/20 border border-yellow-500/50 rounded-sm shadow-[0_0_10px_#EAB30833]">
               <Activity size={12} className="text-yellow-500 animate-spin" />
               <span className="text-[9px] font-black tracking-widest text-yellow-500 uppercase">
                 ANALYZING BUFFER... {analyzeProgress || 0}%
               </span>
               <div className="w-16 h-1.5 bg-black/50 ml-2 rounded-full overflow-hidden border border-yellow-500/30">
                 <div 
                   className="h-full bg-yellow-500 transition-all duration-300" 
                   style={{ width: `${Math.max(5, analyzeProgress || 0)}%` }} 
                 />
               </div>
             </div>
           ) : (
             <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-sm">
               <ShieldCheck size={12} className="text-emerald-500" />
               <span className="text-[9px] font-black tracking-widest text-emerald-500 uppercase">STANDBY</span>
             </div>
           )}
         </div>
      </div>
      
      <div className="hidden xl:flex items-center gap-8 z-10">

         <div className="flex items-center gap-2 group">
            <Activity size={12} className={isThreat ? 'text-[#FF3B3B]' : 'text-[#00FF9C]/60'} />
            <div className="flex flex-col">
               <span className="text-[7px] font-black text-[#94A3B8]/40 uppercase tracking-widest">Detection_Net</span>
               <span className="text-[8px] font-black tracking-[0.1em] text-[#94A3B8] uppercase">
                 ENTITIES: <span className={isThreat ? 'text-[#FF3B3B] font-bold' : 'text-[#00FF9C]'}>{entities.length} {isThreat ? 'THREATS' : 'TRACKED'}</span>
               </span>
            </div>
         </div>
      </div>

      <div className="flex items-center gap-3 lg:gap-4 z-10">
         <div className="flex flex-col items-end sm:flex-row sm:items-center gap-1 sm:gap-4">
            <span className={`text-[10px] lg:text-[11px] font-black tabular-nums tracking-widest ${isThreat ? 'text-white' : 'text-[#00F5FF]'}`}>{time}</span>
            <div className="flex items-center gap-1.5 sm:gap-2">
               <div className={`flex items-center gap-1 px-2 py-0.5 lg:px-3 lg:py-1 rounded-sm border ${isThreat ? 'bg-[#FF3B3B]/10 border-[#FF3B3B]/20' : 'bg-[#00FF9C]/10 border-[#00FF9C]/20'}`}>
                  <div className={`w-1 lg:w-1.5 h-1 lg:h-1.5 rounded-full shadow-[0_0_8px_currentColor] ${isThreat ? 'bg-[#FF3B3B] animate-pulse' : 'bg-[#00FF9C]'}`} />
                  <span className={`text-[7px] lg:text-[8px] font-black tracking-[0.2em] ${isThreat ? 'text-[#FF3B3B]' : 'text-[#00FF9C]'}`}>{isThreat ? 'ALARM' : 'LIVE'}</span>
               </div>
               {isRecording && (
                 <div className="flex items-center gap-1 px-2 py-0.5 lg:px-3 lg:py-1 bg-[#FF3B3B]/10 border border-[#FF3B3B]/20 rounded-sm shadow-[0_0_10px_#FF3B3B22]">
                    <div className="w-1 lg:w-1.5 h-1 lg:h-1.5 rounded-full bg-[#FF3B3B]" />
                    <span className="text-[7px] lg:text-[8px] font-black tracking-[0.2em] text-[#FF3B3B]">REC</span>
                 </div>
               )}
            </div>
         </div>
      </div>
    </header>
  );
};

export default Header;
