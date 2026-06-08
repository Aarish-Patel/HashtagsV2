import React from 'react';

const Footer = ({ entities, uptime, alerts, incidents, formatUptime }) => {
  return (
    <footer className="h-8 bg-transparent border-y border-[#E2E8F0]/5 px-6 flex items-center overflow-x-auto overflow-y-hidden select-none shrink-0 border-l border-l-white/5 custom-scrollbar-hide">
       <div className="flex items-center gap-8 min-w-max">
          <div className="flex items-center gap-2 whitespace-nowrap">
             <span className="text-[#94A3B8] font-bold text-[8px] uppercase tracking-[0.2em]">Entities</span>
             <span className="text-[#00F5FF] font-black text-[10px]">{entities.length}</span>
          </div>
          <div className="flex items-center gap-2 whitespace-nowrap">
             <span className="text-[#94A3B8] font-bold text-[8px] uppercase tracking-[0.2em]">Weapons</span>
             <span className="text-[#FF3B3B] font-black text-[10px]">{entities.some(e => e.weapon) ? 'DETECTED' : 'CLEAR'}</span>
          </div>
          <div className="flex items-center gap-2 whitespace-nowrap">
             <span className="text-[#94A3B8] font-bold text-[8px] uppercase tracking-[0.2em]">Uptime</span>
             <span className="text-[#00FF9C] font-black text-[10px] tabular-nums">{formatUptime(uptime)}</span>
          </div>
          <div className="flex items-center gap-2 whitespace-nowrap">
             <span className="text-[#94A3B8] font-bold text-[8px] uppercase tracking-[0.2em]">Alerts</span>
             <span className="text-[#FFD60A] font-black text-[10px]">{alerts.length}</span>
          </div>
          <div className="flex items-center gap-2 whitespace-nowrap">
             <span className="text-[#94A3B8] font-bold text-[8px] uppercase tracking-[0.2em]">Clips Saved</span>
             <span className="text-[#00F5FF] font-black text-[10px]">{incidents.length}</span>
          </div>
       </div>
    </footer>
  );
};

export default Footer;
