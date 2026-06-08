import React from 'react';
import { Menu, X, Activity, Cpu } from 'lucide-react';

const Header = ({ entities, time, isRecording, sidebarOpen, setSidebarOpen, system }) => {
  return (
    <header className="h-12 lg:h-10 bg-[#030B17] border-b border-[#E2E8F0]/5 px-4 lg:px-6 flex items-center shrink-0 z-50 justify-between relative overflow-hidden">
      
      {/* SCANLINE EFFECT */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.03] bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_2px,3px_100%]" />

      <div className="flex items-center gap-4 z-10">
         <button 
           onClick={() => setSidebarOpen(!sidebarOpen)}
           className="lg:hidden text-[#00F5FF] hover:bg-[#00F5FF]/10 p-1.5 rounded transition-all active:scale-95"
         >
            {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
         </button>
         
         <div className="flex items-baseline gap-2">
            <span className="text-[#00F5FF] text-[11px] lg:text-[13px] font-black tracking-[0.2em] uppercase">HASHTAGS</span>
            <span className="hidden sm:inline text-[#94A3B8]/30 font-light text-[11px]">//</span>
            <span className="hidden sm:inline text-[#94A3B8] text-[9px] lg:text-[10px] font-medium tracking-[0.3em] uppercase">AI-SENSOR_FEED</span>
         </div>
      </div>
      
      <div className="hidden xl:flex items-center gap-8 z-10">
         <div className="flex items-center gap-2 group cursor-help">
            <Cpu size={12} className="text-[#00F5FF]/60 group-hover:text-[#00F5FF] transition-colors" />
            <div className="flex flex-col">
               <span className="text-[7px] font-black text-[#94A3B8]/40 uppercase tracking-widest">Sys_Load</span>
               <span className="text-[8px] font-black tracking-[0.1em] text-[#94A3B8] uppercase">CPU: {system.cpu}% <span className="mx-1 text-[#94A3B8]/20">|</span> MEM: {system.memory}%</span>
            </div>
         </div>
         <div className="flex items-center gap-2 group">
            <Activity size={12} className="text-[#00FF9C]/60" />
            <div className="flex flex-col">
               <span className="text-[7px] font-black text-[#94A3B8]/40 uppercase tracking-widest">Detection_Net</span>
               <span className="text-[8px] font-black tracking-[0.1em] text-[#94A3B8] uppercase">ENTITIES: <span className="text-[#00FF9C]">{entities.length} TRACKED</span></span>
            </div>
         </div>
      </div>

      <div className="flex items-center gap-3 lg:gap-4 z-10">
         <div className="flex flex-col items-end sm:flex-row sm:items-center gap-1 sm:gap-4">
            <span className="text-[10px] lg:text-[11px] font-black text-[#00F5FF] tabular-nums tracking-widest">{time}</span>
            <div className="flex items-center gap-1.5 sm:gap-2">
               <div className="flex items-center gap-1 px-2 py-0.5 lg:px-3 lg:py-1 bg-[#00FF9C]/10 border border-[#00FF9C]/20 rounded-sm">
                  <div className="w-1 lg:w-1.5 h-1 lg:h-1.5 rounded-full bg-[#00FF9C] shadow-[0_0_8px_#00FF9C]" />
                  <span className="text-[7px] lg:text-[8px] font-black tracking-[0.2em] text-[#00FF9C]">LIVE</span>
               </div>
               {isRecording && (
                 <div className="flex items-center gap-1 px-2 py-0.5 lg:px-3 lg:py-1 bg-[#FF3B3B]/10 border border-[#FF3B3B]/20 rounded-sm animate-pulse shadow-[0_0_10px_#FF3B3B22]">
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
