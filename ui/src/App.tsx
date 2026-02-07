import { useState, useEffect } from 'react';
import { Menu, FolderTree, Users, Activity, Terminal, Cpu, File, Folder, ChevronRight, ChevronLeft, Save, Play, Settings, Trello, Monitor, Rocket, CheckCircle2, PlayCircle, Filter, Calendar, Zap } from 'lucide-react';
import Editor from '@monaco-editor/react';
import { LineChart, Line, ResponsiveContainer, CartesianGrid, YAxis, XAxis, Tooltip, ReferenceLine, Legend } from 'recharts';

const API_BASE = "http://127.0.0.1:8082";
const WS_BASE = "ws://127.0.0.1:8082";

export default function App() {
  const [activeTab, setActiveTab] = useState<'workstation' | 'traction'>('workstation');
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [files, setFiles] = useState<any[]>([]);
  const [currentPath, setCurrentPath] = useState('.');
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [activeAssetType, setActiveAssetType] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [metrics, setMetrics] = useState<any>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [activeMembers, setActiveMembers] = useState<any>({});
  const [backlog, setBacklog] = useState<any[]>([]);
  const [calendar, setCalendar] = useState<any>(null);
  const [isLaunching, setIsLaunching] = useState(false);
  
  const [isExplorerOpen, setExplorerOpen] = useState(true);
  const [executeFilter, setExecuteFilter] = useState(false);
  const [isMenuOpen, setMenuOpen] = useState(false);
  
  const [sidebarWidth, setSidebarWidth] = useState(240);
  const [hudWidth, setHudWidth] = useState(380);
  const [footerHeight, setFooterHeight] = useState(240);

  // 1. DATA INIT
  useEffect(() => {
    const init = async () => {
      try {
        const res = await fetch(`${API_BASE}/runs`);
        const runs = await res.json();
        if (runs.length > 0) {
            const latestId = runs[0].id;
            setActiveSessionId(latestId);
            fetchBacklog(latestId);
            fetchMemberMetrics(latestId);
        }
        const calRes = await fetch(`${API_BASE}/system/calendar`);
        setCalendar(await calRes.json());
      } catch (e) { console.error("API Link Offline", e); }
    };
    init();
    
    const pulse = async () => {
      try {
        const res = await fetch(`${API_BASE}/system/metrics`);
        const data = await res.json();
        setMetrics((prev: any) => [...prev.slice(-29), { 
          time: new Date().toLocaleTimeString(), 
          cpu: data.cpu_percent || 0, 
          vram: ((data.vram_gb_used || 0) / (data.vram_total_gb || 1)) * 100 
        }]);
      } catch (e) {}
    };
    const itv = setInterval(pulse, 2000);
    return () => clearInterval(itv);
  }, []);

  // 2. EXPLORER
  useEffect(() => {
    const fetchFiles = async () => {
      try {
        const res = await fetch(`${API_BASE}/system/explorer?path=${currentPath}`);
        const data = await res.json();
        setFiles(data.items || []);
      } catch (e) {}
    };
    if (activeTab === 'workstation') fetchFiles();
  }, [currentPath, activeTab]);

  // 3. WS & STATE SYNC
  useEffect(() => {
    let socket: WebSocket;
    const connect = () => {
      socket = new WebSocket(`${WS_BASE}/ws/events`);
      socket.onmessage = (event) => {
        const record = JSON.parse(event.data);
        setLogs((prev) => [...prev.slice(-100), record]);
        if (activeSessionId) {
            fetchMemberMetrics(activeSessionId);
            fetchBacklog(activeSessionId);
        }
      };
      socket.onclose = () => setTimeout(connect, 3000);
    };
    connect();
    return () => socket?.close();
  }, [activeSessionId]);

  const fetchMemberMetrics = async (sid: string) => {
    try {
      const res = await fetch(`${API_BASE}/runs/${sid}/metrics`);
      const data = await res.json();
      setActiveMembers(data || {});
    } catch (e) {}
  };

  const fetchBacklog = async (sid: string) => {
    try {
      const res = await fetch(`${API_BASE}/runs/${sid}/backlog`);
      const data = await res.json();
      setBacklog(data || []);
    } catch (e) {}
  };

  const updateStatus = async (bookId: string, status: string) => {
    try {
      await fetch(`${API_BASE}/backlog/${bookId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
      });
      if (activeSessionId) fetchBacklog(activeSessionId);
    } catch (e) {}
  };

  const openFile = async (f: any) => {
    const fullPath = currentPath === '.' ? f.name : `${currentPath}/${f.name}`;
    try {
      const res = await fetch(`${API_BASE}/system/read?path=${fullPath}`);
      const data = await res.json();
      setActiveFile(fullPath);
      setActiveAssetType(f.asset_type);
      setFileContent(data.content || '');
    } catch (e) {
        console.error("Open File Error:", e);
    }
  };

  const runActiveAsset = async () => {
    if (!activeFile) return;
    setIsLaunching(true);
    console.log(`[RIG] Launching: ${activeFile}`);
    try {
      const res = await fetch(`${API_BASE}/system/run-active`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: activeFile })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setActiveSessionId(data.session_id);
      setActiveTab('traction'); // Switch to board so user sees cards appearing
      console.log(`[RIG] Session Started: ${data.session_id}`);
    } catch (e: any) { 
        alert(`Launch Failed: ${e.message}`); 
    } finally {
        setIsLaunching(false);
    }
  };

  const saveFile = async () => {
    if (!activeFile) return;
    try {
      await fetch(`${API_BASE}/system/save?path=${activeFile}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: fileContent })
      });
      setLogs(p => [...p, {role: 'SYS', event: 'COMMIT_SUCCESS', data: {file: activeFile}}]);
    } catch (e) {}
  };

  const goBack = () => {
    if (currentPath === '.') return;
    const parts = currentPath.split('/');
    parts.pop();
    setCurrentPath(parts.length === 0 ? '.' : parts.join('/'));
  };

  const latestMetrics = metrics.length > 0 ? metrics[metrics.length - 1] : { cpu: 0, vram: 0 };

  return (
    <div className="h-screen w-screen bg-[#020617] text-slate-300 flex flex-col overflow-hidden font-sans select-none text-[13px]">
      
      {/* LAUNCH OVERLAY */}
      {isLaunching && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-[1000] flex items-center justify-center">
              <div className="flex flex-col items-center gap-4">
                  <div className="h-12 w-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                  <div className="text-white font-black tracking-widest uppercase text-xs animate-pulse">Igniting Engine...</div>
              </div>
          </div>
      )}

      {/* HEADER */}
      <div className="h-11 bg-slate-900 border-b border-slate-800 flex items-center px-4 justify-between shrink-0 z-50 shadow-xl">
        <div className="flex items-center gap-6">
          <div className="relative">
            <button onClick={() => setMenuOpen(!isMenuOpen)} className="p-1 hover:bg-slate-800 rounded text-blue-500 transition-colors">
                <Menu size={20} />
            </button>
            {isMenuOpen && (
                <div className="absolute top-10 left-0 w-56 bg-slate-900 border border-slate-800 shadow-2xl rounded-md py-1 z-[100] border-t-2 border-t-blue-600">
                    <button className="w-full text-left px-4 py-2 text-xs hover:bg-blue-600 hover:text-white flex items-center gap-2"><FolderTree size={12}/> Open Project</button>
                    <button onClick={saveFile} className="w-full text-left px-4 py-2 text-xs hover:bg-blue-600 hover:text-white flex items-center gap-2"><Save size={12}/> Save</button>
                    <div className="border-t border-slate-800 my-1"></div>
                    <button className="w-full text-left px-4 py-2 text-xs hover:bg-blue-600 hover:text-white flex items-center gap-2"><Settings size={12}/> Rig Settings</button>
                </div>
            )}
          </div>
          
          <span className="font-black tracking-[0.4em] text-xs text-slate-100 uppercase">Orket</span>

          <div className="flex bg-black/40 p-1 rounded-lg border border-slate-800 ml-4">
            <button 
                onClick={() => setActiveTab('workstation')}
                className={`flex items-center gap-2 px-3 py-1 rounded text-[10px] font-bold transition-all ${activeTab === 'workstation' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' : 'text-slate-500 hover:text-slate-300'}`}>
                <Monitor size={12}/> WORKSTATION
            </button>
            <button 
                onClick={() => setActiveTab('traction')}
                className={`flex items-center gap-2 px-3 py-1 rounded text-[10px] font-bold transition-all ${activeTab === 'traction' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' : 'text-slate-500 hover:text-slate-300'}`}>
                <Trello size={12}/> TRACTION BOARD
            </button>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
            <span className="text-[10px] text-slate-500 font-mono tracking-tighter uppercase">{activeSessionId ? `SESSION: ${activeSessionId.slice(0,8)}` : 'RIG_IDLE'}</span>
            <button 
                onClick={runActiveAsset}
                disabled={!activeAssetType || isLaunching}
                className={`text-[10px] font-black px-4 py-1.5 rounded-sm uppercase tracking-widest flex items-center gap-2 transition-all ${activeAssetType && !isLaunching ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/40' : 'bg-slate-800 text-slate-600 cursor-not-allowed opacity-50'}`}>
                <Zap size={10} fill="currentColor" /> {isLaunching ? 'IGNITING...' : activeAssetType ? `IGNITE ${activeAssetType.toUpperCase()}` : 'LAUNCH_READY'}
            </button>
        </div>
      </div>

      {/* BODY */}
      <div className="flex-grow flex overflow-hidden min-h-0" style={{ marginBottom: footerHeight }}>
        
        {/* NAVIGATOR */}
        {activeTab === 'workstation' && (
            <div style={{ width: isExplorerOpen ? 240 : 40 }} className="flex bg-slate-950 border-r border-slate-800 transition-all duration-300 overflow-hidden shrink-0 relative shadow-2xl">
                <div className="flex flex-col w-full h-full">
                    <div className="p-3 border-b border-slate-800 flex items-center justify-between bg-black/20 shrink-0 h-10">
                        {isExplorerOpen && <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest flex items-center gap-2"><FolderTree size={12}/> Navigator</span>}
                        <div className="flex items-center gap-2">
                            {isExplorerOpen && (
                                <button onClick={() => setExecuteFilter(!executeFilter)} className={`p-1 rounded transition-colors ${executeFilter ? 'text-blue-400 bg-blue-900/20' : 'text-slate-600 hover:text-slate-400'}`}>
                                    <Filter size={12} />
                                </button>
                            )}
                            <button onClick={() => setExplorerOpen(!isExplorerOpen)} className="text-slate-500 hover:text-blue-500">
                                {isExplorerOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
                            </button>
                        </div>
                    </div>
                    {isExplorerOpen && (
                        <div className="flex-grow overflow-auto p-2 scrollbar-hide">
                            <div className="text-[8px] text-slate-600 mb-2 px-2 uppercase font-bold tracking-widest opacity-50 truncate flex justify-between">
                                <span>Root: {currentPath}</span>
                                {executeFilter && <span className="text-blue-500 animate-pulse"><Rocket size={8}/> PLAYLIST</span>}
                            </div>
                            {currentPath !== '.' && !executeFilter && (
                                <div onClick={goBack} className="flex items-center gap-2 py-1 px-3 text-[11px] text-blue-400 hover:bg-slate-900 cursor-pointer rounded mb-1 font-bold group">
                                    <ChevronLeft size={12} className="group-hover:-translate-x-1 transition-transform" /> .. [Back]
                                </div>
                            )}
                            {files.filter(f => !executeFilter || f.is_launchable || f.is_dir).map(f => (
                                <div key={f.name} onClick={() => f.is_dir ? setCurrentPath(currentPath === '.' ? f.name : `${currentPath}/${f.name}`) : openFile(f)}
                                    className={`flex items-center gap-2 py-1.5 px-3 text-[11px] rounded cursor-pointer transition-colors ${activeFile?.includes(f.name) ? 'bg-blue-600/20 text-blue-400 border-l-2 border-blue-500 shadow-lg' : 'hover:bg-slate-900 hover:text-slate-100'}`}>
                                    {f.is_dir ? <Folder size={12} className="text-blue-500 fill-blue-500/10" /> : <File size={12} className={f.is_launchable ? "text-blue-400 font-bold" : "text-slate-500"} />}
                                    <span className={`truncate ${f.is_launchable ? 'font-black' : ''}`}>{f.name}</span>
                                    {f.is_launchable && <Rocket size={10} className="ml-auto text-blue-500 opacity-50" />}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        )}

        {/* CONTENT AREA */}
        <div className="flex-grow flex min-w-0 bg-slate-950">
            {activeTab === 'workstation' ? (
                <div className="flex-grow flex overflow-hidden">
                    <div className="flex-grow flex flex-col bg-slate-950 min-w-0 relative">
                        <div className="h-8 bg-slate-900/30 border-b border-slate-800 flex items-center px-4 justify-between shrink-0">
                            <span className="text-[10px] font-mono text-slate-500">{activeFile || 'IDLE_IDE'}</span>
                            <span className={`text-[8px] font-black px-1.5 py-0.5 border rounded uppercase tracking-[0.2em] ${activeAssetType ? 'text-blue-400 border-blue-900/50 bg-blue-950/20' : 'text-slate-600 border-slate-800'}`}>
                                {activeAssetType || 'Read-Only'}
                            </span>
                        </div>
                        <div className="flex-grow relative overflow-hidden">
                            <Editor height="100%" theme="vs-dark" value={fileContent} onChange={(v) => setFileContent(v || '')} options={{ fontSize: 13, minimap: { enabled: false }, automaticLayout: true, fontFamily: 'Fira Code, monospace', lineHeight: 1.6 }} />
                        </div>
                    </div>

                    {/* HUD (WIDE) */}
                    <div style={{ width: hudWidth }} className="bg-slate-950 border-l border-slate-800 flex flex-col shrink-0 relative shadow-2xl overflow-hidden">
                        <div onMouseDown={(e) => {
                            const onMove = (me: MouseEvent) => setHudWidth(Math.max(200, Math.min(600, window.innerWidth - me.clientX)));
                            const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
                            document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp);
                        }} className="absolute top-0 left-0 w-1 h-full cursor-col-resize hover:bg-blue-600 transition-colors z-50" />
                        
                        <div className="p-3 border-b border-slate-800 flex items-center gap-2 bg-slate-900/40 shrink-0 uppercase tracking-widest font-black text-[10px] text-slate-500">
                            <Users size={14} className="text-blue-500" /> Member HUD
                        </div>
                        <div className="flex-grow overflow-auto p-4 space-y-4 bg-black/10">
                            {Object.entries(activeMembers).map(([role, stats]: [string, any]) => (
                            <div key={role} className="bg-slate-900/60 border border-slate-800 p-4 rounded-lg border-l-4 border-l-blue-600 group hover:border-blue-500 transition-all shadow-xl">
                                <div className="flex justify-between items-center mb-4">
                                    <span className="text-slate-100 font-bold text-[11px] uppercase tracking-tighter">{role.replace('_', ' ')}</span>
                                    <div className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.5)]"></div>
                                </div>
                                <div className="grid grid-cols-2 gap-3 text-center text-slate-400">
                                    <div className="bg-black/40 p-2.5 rounded border border-slate-800/50">
                                        <div className="text-[7px] uppercase font-black mb-1">Compute</div>
                                        <div className="text-xs font-mono">{(stats.tokens/1000).toFixed(1)}k</div>
                                    </div>
                                    <div className="bg-black/40 p-2.5 rounded border border-slate-800/50">
                                        <div className="text-[7px] uppercase font-black mb-1">Traction</div>
                                        <div className="text-xs font-mono text-blue-400">+{stats.lines_written}</div>
                                    </div>
                                </div>
                            </div>
                            ))}
                        </div>
                    </div>
                </div>
            ) : (
                /* TRACTION BOARD */
                <div className="flex-grow flex flex-col bg-[#020617] overflow-hidden">
                    <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/20 shrink-0">
                        <div className="flex items-center gap-4">
                            <h4 className="text-sm font-black tracking-widest text-slate-100 uppercase flex items-center gap-2">
                                <Trello size={18} className="text-blue-500"/> The Traction Board
                            </h4>
                            <div className="h-6 w-[1px] bg-slate-800"></div>
                            {calendar && (
                                <div className="flex items-center gap-2 text-blue-500 font-black text-[10px] tracking-widest uppercase">
                                    <Calendar size={14}/> {calendar.current_sprint} <span className="opacity-30">({calendar.sprint_start} to {calendar.sprint_end})</span>
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="flex-grow flex gap-4 p-4 overflow-x-auto overflow-y-hidden bg-black/20">
                        {['ready', 'blocked', 'ready_for_testing', 'waiting_for_developer', 'done', 'canceled'].map(status => (
                            <div key={status} className="w-[320px] shrink-0 flex flex-col bg-slate-900/40 border border-slate-800/50 rounded-xl overflow-hidden shadow-2xl backdrop-blur-sm">
                                <div className="p-3 border-b border-slate-800 flex items-center justify-between bg-black/40 h-10">
                                    <span className="text-[9px] font-black uppercase tracking-[0.2em] text-slate-500">{status.replace(/_/g, ' ')}</span>
                                    <span className="text-[10px] font-mono text-slate-600 bg-black/40 px-2 rounded-full border border-slate-800">{backlog.filter(s => s.status === status).length}</span>
                                </div>
                                <div className="flex-grow overflow-y-auto p-3 space-y-3 scrollbar-hide">
                                    {backlog.filter(s => s.status === status).map(book => (
                                        <div key={book.id} className="bg-slate-900/80 border border-slate-800 p-4 rounded-lg shadow-xl hover:border-blue-500/50 transition-all group relative">
                                            <div className={`absolute top-0 right-0 w-1 h-12 rounded-tr-lg rounded-br-lg ${book.priority === 'Critical' ? 'bg-red-600' : book.priority === 'High' ? 'bg-orange-500' : 'bg-blue-500'}`}></div>
                                            <div className="flex justify-between items-start mb-3">
                                                <div className="flex flex-col">
                                                    <span className="text-[8px] font-black text-blue-600 uppercase tracking-widest">{book.id}</span>
                                                    <span className="text-[7px] text-slate-600 font-bold">{book.sprint}</span>
                                                </div>
                                                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                    {status !== 'ready' && <button onClick={() => updateStatus(book.id, 'ready')} className="p-1 hover:bg-blue-600 rounded text-slate-500 hover:text-white"><PlayCircle size={12}/></button>}
                                                    {status !== 'done' && <button onClick={() => updateStatus(book.id, 'done')} className="p-1 hover:bg-green-600 rounded text-slate-500 hover:text-white"><CheckCircle2 size={12}/></button>}
                                                </div>
                                            </div>
                                            <div className="text-[11px] font-black text-slate-100 uppercase mb-1 tracking-tight truncate">{book.summary || book.seat.replace(/_/g, ' ')}</div>
                                            <div className="text-[10px] text-slate-500 italic leading-relaxed line-clamp-2">{book.note}</div>
                                            <div className="flex justify-between items-center mt-2 pt-2 border-t border-slate-800/50 text-[9px]">
                                                <span className="text-slate-400 font-bold uppercase">{book.assignee || 'Unassigned'}</span>
                                                <span className={`font-bold px-1.5 rounded ${book.priority === 'Critical' ? 'text-red-400 bg-red-950/20' : 'text-slate-500'}`}>{book.priority}</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
      </div>

      {/* FOOTER */}
      <div style={{ height: footerHeight }} className="fixed bottom-0 left-0 w-full border-t border-slate-800 bg-slate-950 flex flex-col z-40 shadow-[0_-15px_50px_rgba(0,0,0,0.7)]">
        <div onMouseDown={(e) => {
            const onMove = (me: MouseEvent) => setFooterHeight(Math.max(100, Math.min(600, window.innerHeight - me.clientY)));
            const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
            document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp);
        }} className="h-1 w-full cursor-row-resize hover:bg-blue-600 transition-colors z-50 shrink-0" />
        
        <div className="flex-grow flex overflow-hidden">
            <div className="flex-grow border-r border-slate-800 p-3 flex flex-col bg-black/20 overflow-hidden">
                <div className="flex items-center gap-2 mb-2 opacity-40 text-blue-500 uppercase text-[9px] font-black tracking-widest"><Terminal size={12} /> System Event Stream</div>
                <div className="flex-grow overflow-auto font-mono text-[9px] text-slate-400 space-y-1 select-text scrollbar-hide px-2 border-l border-slate-900">
                    {logs.map((l, i) => (
                        <div key={i} className="group hover:bg-slate-900/50 transition-colors rounded px-1">
                            <span className="text-blue-600 mr-2 font-bold">[{l.timestamp?.split('T')[1]?.split('.')[0] || '...'}]</span>
                            <span className={l.role ? "text-slate-200 uppercase font-bold" : "text-slate-500"}>{l.role || 'SYS'}</span>
                            <span className="text-slate-500 mx-1">:</span>
                            <span className="text-slate-300">{l.event}</span>
                            <span className="text-slate-600 ml-2 italic opacity-0 group-hover:opacity-100 transition-opacity text-[8px]">({JSON.stringify(l.data).slice(0,80)}...)</span>
                        </div>
                    ))}
                </div>
            </div>
            <div className="w-[450px] border-r border-slate-800 p-3 flex flex-col bg-black/40 overflow-hidden shrink-0 relative">
                <div className="flex items-center gap-2 mb-2 opacity-40 text-blue-500 uppercase text-[9px] font-black tracking-widest"><Cpu size={12} /> i9-13900K / RTX 4090 Pulse</div>
                <div className="flex-grow relative">
                    <div className="absolute top-0 right-0 flex gap-4 text-[9px] font-black tracking-tighter text-slate-500 z-10 p-1 bg-slate-950/80 rounded">
                        <div className="flex items-center gap-1"><div className="h-1.5 w-1.5 rounded-full bg-[#3b82f6]"></div> CPU {latestMetrics.cpu.toFixed(1)}%</div>
                        <div className="flex items-center gap-1"><div className="h-1.5 w-1.5 rounded-full bg-[#0ea5e9]"></div> VRAM {latestMetrics.vram.toFixed(1)}%</div>
                    </div>
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={metrics} margin={{ top: 20, right: 10, left: -20, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                            <XAxis dataKey="time" hide />
                            <YAxis domain={[0, 100]} hide />
                            <ReferenceLine y={80} stroke="#ef4444" strokeDasharray="3 3" opacity={0.3} label={{ value: 'HIGH', position: 'insideRight', fill: '#ef4444', fontSize: 8, opacity: 0.5 }} />
                            <ReferenceLine y={20} stroke="#22c55e" strokeDasharray="3 3" opacity={0.3} label={{ value: 'IDLE', position: 'insideRight', fill: '#22c55e', fontSize: 8, opacity: 0.5 }} />
                            <Line name="CPU" type="monotone" dataKey="cpu" stroke="#3b82f6" strokeWidth={2} dot={false} isAnimationActive={false} />
                            <Line name="VRAM" type="monotone" dataKey="vram" stroke="#0ea5e9" strokeWidth={2} dot={false} isAnimationActive={false} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>
            <div className="w-64 p-3 flex flex-col items-center justify-center bg-blue-600/5 shrink-0 text-blue-500">
                <Activity className="text-blue-500/20 mb-2" size={32} />
                <div className="text-center">
                    <div className="text-3xl font-black font-mono tracking-tighter">
                        {Object.values(activeMembers).reduce((acc: number, curr: any) => acc + (Number(curr.tokens) || 0), 0)}
                    </div>
                    <div className="text-[8px] opacity-40 tracking-[0.2em] font-black uppercase mt-1 text-slate-100">Global Tokens</div>
                </div>
            </div>
        </div>
      </div>
    </div>
  );
}
