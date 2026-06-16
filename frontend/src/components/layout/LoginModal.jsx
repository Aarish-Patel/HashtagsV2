import React, { useState } from 'react';
import { API_BASE } from '../../config';
import Lock from 'lucide-react/dist/esm/icons/lock';

export default function LoginModal({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    try {
      const res = await fetch(`${API_BASE}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      
      const data = await res.json();
      
      if (res.ok && data.token) {
        localStorage.setItem('token', data.token);
        localStorage.setItem('role', data.role);
        onLogin(data.token, data.role);
      } else {
        setError(data.error || 'Login failed');
      }
    } catch (err) {
      setError('Could not connect to server');
    }
  };

  return (
    <div className="fixed inset-0 z-[999] flex items-center justify-center bg-[#020617]/90 backdrop-blur-md">
      <div className="w-[380px] bg-[#030B17] border border-[#00F5FF]/30 p-8 shadow-2xl shadow-[#00F5FF]/10 flex flex-col items-center">
        <div className="w-12 h-12 rounded-full bg-[#00F5FF]/10 border border-[#00F5FF]/30 flex items-center justify-center mb-6">
          <Lock className="text-[#00F5FF]" size={24} />
        </div>
        
        <h2 className="text-[#00F5FF] text-xl font-black tracking-[0.2em] uppercase mb-1">HASHTAG V2</h2>
        <p className="text-slate-500 text-xs font-bold tracking-widest uppercase mb-8">AUTHENTICATION REQUIRED</p>
        
        <form onSubmit={handleSubmit} className="w-full flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-[9px] text-[#00F5FF]/70 font-black tracking-widest uppercase">OPERATOR ID</label>
            <input 
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="bg-black border border-white/10 text-xs p-2.5 px-3 text-white placeholder-slate-600 outline-none focus:border-[#00F5FF]/50 transition-colors"
              placeholder="e.g. commander"
              required
            />
          </div>
          
          <div className="flex flex-col gap-1">
            <label className="text-[9px] text-[#00F5FF]/70 font-black tracking-widest uppercase">ACCESS CODE</label>
            <input 
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="bg-black border border-white/10 text-xs p-2.5 px-3 text-white placeholder-slate-600 outline-none focus:border-[#00F5FF]/50 transition-colors"
              placeholder="••••••••"
              required
            />
          </div>
          
          {error && <div className="text-[#FF3B3B] text-[10px] font-bold tracking-wider text-center">{error}</div>}
          
          <button 
            type="submit" 
            className="mt-4 w-full bg-[#00F5FF]/20 text-[#00F5FF] border border-[#00F5FF]/30 py-3 text-xs font-black uppercase tracking-[0.2em] hover:bg-[#00F5FF]/30 transition-colors"
          >
            AUTHORIZE
          </button>
        </form>
        
        <div className="mt-8 flex flex-col items-center gap-1 opacity-50">
           <span className="text-[8px] text-slate-400 font-bold tracking-widest uppercase">Default Credentials:</span>
           <span className="text-[8px] text-slate-500 font-bold tracking-widest uppercase">operator / op123</span>
           <span className="text-[8px] text-slate-500 font-bold tracking-widest uppercase">commander / cmd123</span>
        </div>
      </div>
    </div>
  );
}
