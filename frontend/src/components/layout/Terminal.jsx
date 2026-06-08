import React from 'react';
import ChevronDown from 'lucide-react/dist/esm/icons/chevron-down';
import ChevronUp from 'lucide-react/dist/esm/icons/chevron-up';
import TerminalIcon from 'lucide-react/dist/esm/icons/terminal';

const Terminal = ({ logs, terminalOpen, setTerminalOpen }) => {
  return (
    <div className={`flex flex-col shrink-0 bg-[#020408] border-t border-[#00F5FF]/10 transition-all duration-500 ease-in-out ${terminalOpen ? 'h-[120px]' : 'h-7'}`}>
       
       {/* TACTICAL TOGGLE BAR */}
       <div 
         onClick={() => setTerminalOpen(!terminalOpen)}
         className="h-7 border-b border-white/5 flex items-center justify-between px-4 cursor-pointer hover:bg-white/[0.02] transition-colors group"
       >
          <div className="flex items-center gap-2">
             <TerminalIcon size={12} className={terminalOpen ? 'text-[#00F5FF]' : 'text-[#94A3B8]/40'} />
             <span className={`text-[9px] font-black tracking-[0.2em] uppercase transition-colors ${terminalOpen ? 'text-[#E2E8F0]' : 'text-[#94A3B8]/30'}`}>
                {terminalOpen ? 'System_Console_Active' : 'Console_Minimized // logs_buffered'}
             </span>
          </div>
          <div className="flex items-center gap-3">
             {!terminalOpen && (
                <div className="flex gap-1">
                   {[1, 2, 3].map(i => (
                      <div key={i} className="w-1 h-1 rounded-full bg-[#00FF9C]/20 animate-pulse" style={{ animationDelay: `${i * 200}ms` }} />
                   ))}
                </div>
             )}
             {terminalOpen ? <ChevronDown size={14} className="text-[#94A3B8]/40 group-hover:text-[#00F5FF]" /> : <ChevronUp size={14} className="text-[#94A3B8]/40 group-hover:text-[#00F5FF]" />}
          </div>
       </div>

       {/* LOG VIEW */}
       <div className={`grow bg-transparent font-mono text-[9px] flex flex-col overflow-hidden group py-1 transition-opacity duration-300 ${terminalOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
          <div className="grow overflow-y-auto custom-scrollbar flex flex-col gap-[1px]">
            {logs.map((log, i) => (
              <div key={i} className="flex gap-4 items-center tracking-widest pl-4 pr-4 border-l-2 border-transparent hover:border-[#94A3B8]/30 transition-all cursor-default py-0.5">
                <span className="text-[#94A3B8] opacity-50 font-bold tabular-nums shrink-0">{log.time}</span>
                <span className={`${log.color} font-bold whitespace-nowrap`}>{log.txt}</span>
              </div>
            ))}
            {logs.length === 0 && <span className="text-[#94A3B8]/30 px-4 py-2 uppercase tracking-widest text-[8px]">Ready_For_Input...</span>}
          </div>
       </div>
    </div>
  );
};

export default Terminal;
