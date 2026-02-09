import { useState, useEffect, useRef } from 'react';
import { 
  Menu, FolderTree, Users, Activity, Terminal, Cpu, File, Folder, 
  ChevronRight, ChevronLeft, Save, Play, Settings, Trello, Monitor, 
  Rocket, Zap, CheckCircle2, MessageSquare, Code, LayoutGrid, Package, 
  Search, Binoculars, Microscope, AlertCircle, Glasses, Trash2
} from 'lucide-react';
import Editor from '@monaco-editor/react';
import { LineChart, Line, ResponsiveContainer, CartesianGrid, YAxis, XAxis, ReferenceLine } from 'recharts';
import KanbanPlugin from './components/KanbanPlugin';

const API_BASE = "http://127.0.0.1:8082";

export default function App() {
  const [activeTab, setActiveTab] = useState<'workstation' | 'verification'>('workstation');
  const [isBackendOnline, setIsBackendOnline] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [files, setFiles] = useState<any[]>([]);
  const [currentPath, setCurrentPath] = useState('.');
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [activeAssetType, setActiveAssetType] = useState<string | null>(null);
  const [activeIssueId, setActiveIssueId] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [lastRealContent, setLastRealContent] = useState('');
  const [metrics, setMetrics] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [activeMembers, setActiveMembers] = useState<any>({});
  const [boardHierarchy, setBoardHierarchy] = useState<any>({ rocks: [], orphaned_epics: [] });
  const [collapsedNodes, setCollapsedNodes] = useState<Record<string, boolean>>({});
  const [isLaunching, setIsLaunching] = useState(false);
  const [isMenuOpen, setMenuOpen] = useState(false);
  const [driverSteered, setDriverSteered] = useState(false);
  const [isExplorerOpen, setExplorerOpen] = useState(true);
  const [navigatorView, setNavigatorView] = useState<'traction_tree' | 'explorer' | 'members' | 'settings'>('traction_tree');
  const [activeLogSource, setActiveLogSource] = useState('orket.log');
  const [availableLogs, setAvailableLogs] = useState<string[]>(['orket.log']);
  const [membersConfig, setMembersConfig] = useState<any>({ teams: [], roles: [] });
  const [settingsConfig, setSettingsConfig] = useState<any>({ core: [] });

  const [sidebarWidth] = useState(260);
  const [hudWidth, setHudWidth] = useState(240); 
  const [telemetryWidth, setTelemetryWidth] = useState(300);
  const [footerHeight, setFooterHeight] = useState(280);
  
  const [panel1Width, setPanel1Width] = useState(window.innerWidth * 0.25);
  const [panel2Width, setPanel2Width] = useState(window.innerWidth * 0.25);
  const [panel3Width, setPanel3Width] = useState(window.innerWidth * 0.25);

  const [chatInput, setChatInput] = useState('');
  const [isChatting, setIsChatting] = useState(false);

  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const toggleNode = (id: string) => {
    if (!id) return;
    setCollapsedNodes(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const fetchBoard = async () => {
    try {
      const res = await fetch(`${API_BASE}/system/board`);
      if (res.ok) {
        const data = await res.json();
        setBoardHierarchy(data || { rocks: [], orphaned_epics: [] });
      }
    } catch (e) {}
  };

  const fetchMembers = async () => {
    try {
      const teamsRes = await fetch(`${API_BASE}/system/explorer?path=model/core/teams`);
      const rolesRes = await fetch(`${API_BASE}/system/explorer?path=model/core/roles`);
      if (teamsRes.ok && rolesRes.ok) {
        const tData = await teamsRes.json();
        const rData = await rolesRes.json();
        setMembersConfig({
          teams: tData?.items || [],
          roles: rData?.items || []
        });
      }
    } catch (e) {}
  };

  const fetchSettings = async () => {
    try {
      const rootRes = await fetch(`${API_BASE}/system/explorer?path=model/core`);
      if (rootRes.ok) {
        const rootFiles = (await rootRes.json()).items || [];
        setSettingsConfig({
          core: rootFiles.filter((f: any) => f.name?.endsWith('.json'))
        });
      }
    } catch (e) {}
  };

  const fetchLogs = async () => {
    try {
      const logPath = activeLogSource === 'orket.log' ? 'workspace/default/orket.log' : `workspace/default/${activeLogSource}`;
      const res = await fetch(`${API_BASE}/system/read?path=${logPath}`);
      if (res.ok) {
        const data = await res.json();
        if (data?.content) {
          const lines = data.content.trim().split('\n').map((l: string) => {
            try { return JSON.parse(l); } catch(e) { return null; }
          }).filter((l: any) => l !== null);
          setLogs(lines || []);
        } else {
          setLogs([]);
        }
      }
    } catch (e) {}
  };

  const fetchMemberMetrics = async (sid: string) => {
    if (!sid) return;
    try {
      const res = await fetch(`${API_BASE}/runs/${sid}/metrics`);
      if (res.ok) {
        const data = await res.json();
        if (data) {
          const activeOnly = Object.fromEntries(
            Object.entries(data).filter(([_, stats]: [any, any]) => stats && (stats.tokens > 0 || stats.last_action !== 'Idle'))
          );
          setActiveMembers(activeOnly || {});
        }
      }
    } catch (e) {}
  };

  const openFile = async (f: any) => {
    if (!f || !f.name) return;
    const fullPath = f.name.startsWith('model/') ? f.name : (currentPath === '.' ? f.name : `${currentPath}/${f.name}`);
    try {
      const res = await fetch(`${API_BASE}/system/read?path=${fullPath}`);
      if (res.ok) {
        const data = await res.json();
        setActiveFile(fullPath);
        setActiveAssetType(f.asset_type || 'file');
        setActiveIssueId(f.issue_id || null);
        setFileContent(data?.content || '');
        setLastRealContent(data?.content || '');
        localStorage.setItem('orket_last_file', JSON.stringify(f));
      }
    } catch (e) {}
  };

  useEffect(() => {
    const init = async () => {
      try {
        const res = await fetch(`${API_BASE}/runs`);
        if (res.ok) {
          const runs = await res.json();
          if (runs && runs?.length > 0) {
              const latestId = runs[0].id;
              setActiveSessionId(latestId);
              fetchMemberMetrics(latestId);
          }
        }
        
        const stored = localStorage.getItem('orket_last_file');
        if (stored) {
          try { openFile(JSON.parse(stored)); } 
          catch(e) { openFile({ name: 'model/organization.json', asset_type: 'organization' }); }
        } else {
          openFile({ name: 'model/organization.json', asset_type: 'organization' });
        }

        fetchBoard();
        fetchLogs();
      } catch (e) {}
    };
    init();
    
    const pulse = async () => {
      try {
        const res = await fetch(`${API_BASE}/system/heartbeat`);
        if (res.ok) {
          const data = await res.json();
          setIsBackendOnline(data.status === 'online');
          if (data.active_tasks === 0) { setActiveMembers({}); setActiveSessionId(null); }
        } else { setIsBackendOnline(false); }

        if (activeSessionId) fetchMemberMetrics(activeSessionId);

        const metRes = await fetch(`${API_BASE}/system/metrics`);
        if (metRes.ok) {
          const metData = await metRes.json();
          if (metData) {
            setMetrics((prev: any) => [...prev.slice(-29), { 
              time: new Date().toLocaleTimeString(), 
              cpu: metData?.cpu_percent || 0, 
              vram: ((metData?.vram_gb_used || 0) / (metData?.vram_total_gb || 1)) * 100 
            }]);
          }
        }
      } catch (e) { setIsBackendOnline(false); }
    };
    const itv = setInterval(pulse, 2000);
    return () => clearInterval(itv);
  }, [activeSessionId]);

  useEffect(() => {
    const itv = setInterval(fetchLogs, 3000);
    return () => clearInterval(itv);
  }, [activeLogSource]);

  useEffect(() => {
    if (activeTab === 'workstation') {
        if (navigatorView === 'explorer') {
            const fetchFiles = async () => {
                try {
                  const res = await fetch(`${API_BASE}/system/explorer?path=${currentPath}`);
                  if (res.ok) {
                    const data = await res.json();
                    setFiles(data?.items || []);
                  }
                } catch (e) {}
            };
            fetchFiles();
        } else if (navigatorView === 'members') {
            fetchMembers();
        } else if (navigatorView === 'settings') {
            fetchSettings();
        } else if (navigatorView === 'traction_tree') {
            fetchBoard();
        }
    }
  }, [currentPath, activeTab, navigatorView]);

  const runActiveAsset = async () => {
    if (!activeFile && !activeIssueId) return;
    setIsLaunching(true);
    try {
      const res = await fetch(`${API_BASE}/system/run-active`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: activeFile, type: activeAssetType, issue_id: activeIssueId, driver_steered: driverSteered })
      });
      if (res.ok) {
        const data = await res.json();
        setActiveSessionId(data?.session_id);
      }
    } catch (e: any) { alert(`Launch Failed: ${e.message}`); } 
    finally { setIsLaunching(false); }
  };

  const previewActiveAsset = async () => {
    if (!activeFile && !activeIssueId) return;
    if (activeAssetType === 'preview') { setFileContent(lastRealContent); setActiveAssetType('file'); return; }
    setLastRealContent(fileContent);
    try {
      const res = await fetch(`${API_BASE}/system/preview-asset?path=${activeFile}&issue_id=${activeIssueId || ''}`);
      if (res.ok) {
        const data = await res.json();
        if (data) {
          setFileContent(JSON.stringify(data, null, 2));
          setActiveAssetType('preview');
        }
      }
    } catch (e: any) { alert("Preview Failed: " + e.message); }
  };

  const saveFile = async () => {
    if (!activeFile) return;
    try {
      await fetch(`${API_BASE}/system/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: activeFile, content: fileContent })
      });
    } catch (e) {}
  };

  const goBack = () => {
    if (currentPath === '.') return;
    const parts = currentPath.split('/');
    parts.pop();
    setCurrentPath(parts.length === 0 ? '.' : parts.join('/'));
  };

  const latestMetrics = (metrics || []).length > 0 ? metrics[metrics.length - 1] : { cpu: 0, vram: 0 };

  const getRoleColor = (role: string) => {
    if (!role) return 'text-slate-500';
    const r = String(role).toLowerCase();
    if (r.includes('driver')) return 'text-green-400';
    if (r.includes('architect')) return 'text-purple-400';
    if (r.includes('developer') || r.includes('specialist') || r.includes('coder')) return 'text-blue-400';
    return 'text-slate-200';
  };

  const chatWithDriver = async () => {
    if (!chatInput) return;
    const userMsg = chatInput;
    setChatInput('');
    setIsChatting(true);
    try {
      const res = await fetch(`${API_BASE}/system/chat-driver`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg })
      });
      if (res.ok) { fetchBoard(); }
    } catch (e) {}
    finally { setIsChatting(false); }
  };

  return (
    <div className="h-screen w-screen bg-[#020617] text-slate-300 flex flex-col overflow-hidden font-sans select-none text-[13px]">
      {isLaunching && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-[1000] flex items-center justify-center">
              <div className="flex flex-col items-center gap-4">
                  <div className="h-12 w-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                  <div className="text-white font-black tracking-widest uppercase text-xs animate-pulse">Executing Unit...</div>
              </div>
          </div>
      )}

      {/* HEADER */}
      <div className="h-11 bg-slate-900 border-b border-slate-800 flex items-center px-4 justify-between shrink-0 z-50 shadow-xl">
        <div className="flex items-center gap-6">
          <button onClick={() => setMenuOpen(!isMenuOpen)} className="p-1 hover:bg-slate-800 rounded text-blue-500 transition-colors"><Menu size={20} /></button>
          
          <div className="flex items-center gap-2">
            <span className="font-black tracking-[0.4em] text-xs text-slate-100 uppercase">Orket</span>
            <div className={`h-1.5 w-1.5 rounded-full ${isBackendOnline ? 'bg-green-500 shadow-[0_0_8px_#22c55e]' : 'bg-red-500 animate-pulse'}`}></div>
          </div>

          <div className="flex bg-black/40 p-1 rounded-lg border border-slate-800 ml-4">
            <button onClick={() => setActiveTab('workstation')} className={`flex items-center gap-2 px-3 py-1 rounded text-[10px] font-bold transition-all ${activeTab === 'workstation' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' : 'text-slate-500 hover:text-slate-300'}`}><Monitor size={12}/></button>
            <button onClick={() => setActiveTab('verification')} className={`flex items-center gap-2 px-3 py-1 rounded text-[10px] font-bold transition-all ${activeTab === 'verification' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' : 'text-slate-500 hover:text-slate-300'}`}><Microscope size={12}/></button>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
            <span className="text-[10px] text-slate-500 font-mono tracking-tighter uppercase">{activeSessionId ? `SESSION: ${activeSessionId.slice(0,8)}` : 'RIG_IDLE'}</span>
            <button onClick={() => setDriverSteered(!driverSteered)} className={`text-[10px] font-black px-3 py-1.5 rounded-sm uppercase tracking-widest flex items-center gap-2 transition-all ${driverSteered ? 'bg-purple-600 text-white shadow-lg shadow-purple-900/40' : 'bg-slate-800 text-slate-500 border border-slate-700'}`}><Activity size={10} /> STEERED</button>
            <button onClick={runActiveAsset} disabled={(!activeFile && !activeIssueId) || isLaunching} className={`text-[10px] font-black px-4 py-1.5 rounded-sm uppercase tracking-widest flex items-center gap-2 transition-all ${ (activeAssetType || activeIssueId) && !isLaunching ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/40' : 'bg-slate-800 text-slate-600 cursor-not-allowed opacity-50'}`}><Play size={10} fill="currentColor" /> {isLaunching ? 'EXECUTING...' : `EXECUTE`}</button>
        </div>
      </div>

      <div className="flex-grow flex overflow-hidden min-h-0" style={{ marginBottom: footerHeight }}>
        {activeTab === 'workstation' ? (
          <div className="flex-grow flex min-w-0">
            <div className="w-12 bg-slate-950 border-r border-slate-800 flex flex-col items-center py-4 gap-4 shrink-0">
                <button onClick={() => { setNavigatorView('traction_tree'); setExplorerOpen(true); }} className={`p-2 rounded-lg transition-all ${navigatorView === 'traction_tree' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'text-slate-500 hover:bg-slate-900 hover:text-slate-300'}`}><Trello size={20} /></button>
                <button onClick={() => { setNavigatorView('explorer'); setExplorerOpen(true); }} className={`p-2 rounded-lg transition-all ${navigatorView === 'explorer' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'text-slate-500 hover:bg-slate-900 hover:text-slate-300'}`}><FolderTree size={20} /></button>
                <button onClick={() => { setNavigatorView('members'); setExplorerOpen(true); }} className={`p-2 rounded-lg transition-all ${navigatorView === 'members' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'text-slate-500 hover:text-slate-900 hover:text-slate-300'}`}><Users size={20} /></button>
                <button onClick={() => { setNavigatorView('settings'); setExplorerOpen(true); }} className={`p-2 rounded-lg transition-all ${navigatorView === 'settings' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'text-slate-500 hover:text-slate-900 hover:text-slate-300'}`}><Settings size={20} /></button>
            </div>

            <div className="flex-grow flex flex-row overflow-hidden border-r border-slate-800">
                {isExplorerOpen && (
                <div style={{ width: sidebarWidth }} className="flex bg-slate-950 border-r border-slate-800 transition-all duration-300 overflow-hidden shrink-0 relative shadow-2xl">
                    <div className="flex flex-col w-full h-full">
                        <div className="p-3 border-b border-slate-800 flex items-center justify-between bg-black/20 shrink-0 h-12 uppercase tracking-widest font-black text-[10px] text-slate-500">
                            {navigatorView.replace('_', ' ')}
                            <button onClick={() => setExplorerOpen(false)} className="text-slate-500 hover:text-blue-500"><ChevronLeft size={14}/></button>
                        </div>
                        <div className="flex-grow overflow-auto p-2 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent hover:scrollbar-thumb-blue-600/50">
                            {navigatorView === 'explorer' ? (
                                <>
                                    {currentPath !== '.' && ( <div onClick={goBack} className="flex items-center gap-2 py-1 px-3 text-[11px] text-blue-400 hover:bg-slate-900 cursor-pointer rounded mb-1 font-bold group"><ChevronLeft size={12} className="group-hover:-translate-x-1 transition-transform" /> .. [Back]</div> )}
                                    {(files || []).map(f => (
                                        <div key={f.name} onClick={() => f.is_dir ? setCurrentPath(currentPath === '.' ? f.name : `${currentPath}/${f.name}`) : openFile(f)}
                                            className={`flex items-center gap-2 py-1.5 px-3 text-[11px] rounded cursor-pointer transition-colors ${activeFile?.includes(f.name) ? 'bg-blue-600/20 text-blue-400 border-l-2 border-blue-500 shadow-lg' : 'hover:bg-slate-900 hover:text-slate-100'}`}>
                                            {f.is_dir ? <Folder size={12} className="text-blue-500 fill-blue-500/10" /> : <File size={12} className="text-slate-500" />}
                                            <span className="truncate">{f.name}</span>
                                        </div>
                                    ))}
                                </>
                            ) : navigatorView === 'traction_tree' ? (
                                <div className="space-y-4 p-1">
                                    {(boardHierarchy?.rocks || []).map((rock: any) => {
                                        const hasEpics = rock?.epics && rock.epics?.length > 0;
                                        return (
                                            <div key={rock.id} className="space-y-1">
                                                <div className="flex items-center gap-2 group">
                                                    {hasEpics ? ( <button onClick={(e) => { e.stopPropagation(); toggleNode(rock.id); }} className="w-4 h-4 flex items-center justify-center text-slate-600 hover:text-blue-400 font-bold text-[14px]">{collapsedNodes[rock.id] ? '+' : '-'}</button> ) : ( <div className="w-4" /> )}
                                                    <div onClick={() => openFile({name: `model/core/rocks/${rock.id}.json`, asset_type: 'rock'})} className="text-[10px] font-black text-blue-500 uppercase tracking-tighter cursor-pointer hover:text-blue-400"><Trello size={12} className="inline mr-1" /> {rock.name}</div>
                                                </div>
                                                {!collapsedNodes[rock.id] && (rock.epics || []).map((epic: any) => {
                                                    const hasIssues = epic?.issues && epic.issues?.length > 0;
                                                    return (
                                                        <div key={epic.id} className="ml-4 pl-2 border-l border-slate-800 space-y-1">
                                                            <div className="flex items-center gap-2 group">
                                                                {hasIssues ? ( <button onClick={(e) => { e.stopPropagation(); toggleNode(epic.id); }} className="w-3 h-3 flex items-center justify-center text-slate-600 hover:text-white font-bold text-[12px]">{collapsedNodes[epic.id] ? '+' : '-'}</button> ) : ( <div className="w-3" /> )}
                                                                <div onClick={() => openFile({name: `model/core/epics/${epic.id}.json`, asset_type: 'epic'})} className="text-[11px] font-bold text-slate-300 uppercase tracking-tight cursor-pointer hover:text-white">{epic.name}</div>
                                                            </div>
                                                            {!collapsedNodes[epic.id] && (epic.issues || []).map((issue: any) => (
                                                                <div key={issue.id} onClick={() => openFile({name: `model/core/epics/${epic.id}.json`, asset_type: 'issue', issue_id: issue.id})} className="ml-5 text-[10px] text-slate-500 hover:text-blue-400 cursor-pointer transition-colors flex items-center gap-1"><span className="opacity-30">#</span> {issue.name}</div>
                                                            ))}
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        );
                                    })}
                                    {(boardHierarchy?.orphaned_epics || []).length > 0 && (
                                        <div className="mt-6 space-y-2">
                                            <div className="flex items-center gap-2 border-b border-slate-900 pb-1">
                                                <button onClick={() => toggleNode('orphans')} className="w-4 h-4 flex items-center justify-center text-slate-600 hover:text-orange-400 font-bold text-[14px]">{collapsedNodes['orphans'] ? '+' : '-'}</button>
                                                <div className="text-[9px] font-black text-slate-600 uppercase tracking-[0.2em]">Orphaned Epics</div>
                                            </div>
                                            {!collapsedNodes['orphans'] && (boardHierarchy.orphaned_epics || []).map((epic: any) => (
                                                <div key={epic.id} className="space-y-1 ml-4">
                                                    <div onClick={() => openFile({name: `model/core/epics/${epic.id}.json`, asset_type: 'epic'})} className="text-[11px] font-bold text-orange-400/70 uppercase tracking-tight cursor-pointer hover:text-orange-400">{epic.name}</div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ) : navigatorView === 'members' ? (
                                <div className="space-y-4 p-1">
                                    <div className="text-[9px] font-black text-slate-600 uppercase tracking-widest border-b border-slate-900 pb-1">Teams</div>
                                    {(membersConfig?.teams || []).map((t: any) => (
                                        <div key={t.name} onClick={() => openFile({name: `model/core/teams/${t.name}`, asset_type: 'team'})} className="text-[11px] font-bold text-slate-300 uppercase cursor-pointer hover:text-white px-2 py-1 rounded hover:bg-slate-900 flex items-center gap-2"><Users size={12} className="text-blue-500"/> {String(t.name || 'Team').split('.')[0]}</div>
                                    ))}
                                    <div className="text-[9px] font-black text-slate-600 uppercase tracking-widest border-b border-slate-900 pb-1 mt-6">Atomic Roles</div>
                                    {(membersConfig?.roles || []).map((r: any) => (
                                        <div key={r.name} onClick={() => openFile({name: `model/core/roles/${r.name}`, asset_type: 'role'})} className="text-[10px] font-bold text-slate-500 uppercase cursor-pointer hover:text-blue-400 px-2 py-1 rounded hover:bg-slate-900 flex items-center gap-2"><Cpu size={12}/> {String(r.name || 'Role').split('.')[0]}</div>
                                    ))}
                                </div>
                            ) : navigatorView === 'settings' ? (
                                <div className="space-y-4 p-1">
                                    <div className="text-[9px] font-black text-slate-600 uppercase tracking-widest border-b border-slate-900 pb-1">Core System</div>
                                    {(settingsConfig?.core || []).map((f: any) => (
                                        <div key={f.name} onClick={() => openFile({name: `model/core/${f.name}`, asset_type: 'settings'})} className="text-[11px] font-bold text-slate-300 uppercase cursor-pointer hover:text-white px-2 py-1 rounded hover:bg-slate-900 flex items-center gap-2"><Settings size={12}/> {String(f.name || 'Setting').split('.')[0]}</div>
                                    ))}
                                    <div onClick={() => openFile({name: 'user_settings.json', asset_type: 'settings'})} className="text-[11px] font-bold text-blue-400 uppercase cursor-pointer hover:text-white px-2 py-4 border-t border-slate-900 flex items-center gap-2 mt-4"><Activity size={12}/> Local Overrides</div>
                                </div>
                            ) : null}
                        </div>
                    </div>
                </div>
                )}

                <div className="flex-grow flex flex-col bg-slate-950 min-w-0 relative">
                    <div className="h-8 bg-slate-900/30 border-b border-slate-800 flex items-center px-4 justify-between shrink-0">
                        <span className="text-[10px] font-mono text-slate-500">{activeFile || 'IDLE_IDE'}</span>
                        <div className="flex items-center gap-3">
                            <button onClick={previewActiveAsset} disabled={!activeFile || isLaunching} className={`transition-colors ${activeFile ? 'text-blue-500 hover:text-blue-400' : 'text-slate-700 cursor-not-allowed'}`}><Binoculars size={14} /></button>
                            <button onClick={saveFile} disabled={!activeFile} className={`transition-colors ${activeFile ? 'text-blue-500 hover:text-blue-400' : 'text-slate-700 cursor-not-allowed'}`}><Save size={14} /></button>
                            <span className={`text-[8px] font-black px-1.5 py-0.5 border rounded uppercase tracking-[0.2em] ${activeAssetType ? 'text-blue-400 border-blue-900/50 bg-blue-950/20' : 'text-slate-600 border-slate-800'}`}>{activeAssetType || 'Read-Only'}</span>
                        </div>
                    </div>
                    <div className="flex-grow relative overflow-hidden">
                        <Editor height="100%" theme="vs-dark" value={fileContent} onChange={(v) => setFileContent(v || '')} options={{ fontSize: 13, minimap: { enabled: false }, automaticLayout: true, fontFamily: 'Fira Code, monospace', lineHeight: 1.6 }} />
                    </div>
                </div>
            </div>

            <div style={{ width: telemetryWidth }} className="bg-slate-950 border-l border-slate-800 flex flex-col shrink-0 relative shadow-xl overflow-hidden">
                <div onMouseDown={() => { const onMove = (me: MouseEvent) => setTelemetryWidth(Math.max(150, Math.min(500, me.clientX - 600))); const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); }; document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp); }} className="absolute top-0 left-0 w-1 h-full cursor-col-resize hover:bg-blue-600 transition-colors z-50" />
                <div className="p-3 border-b border-slate-800 flex items-center gap-2 bg-slate-900/40 shrink-0 uppercase tracking-widest font-black text-[10px] text-slate-500"><Activity size={14} className="text-blue-500" /> Project Telemetry</div>
                <div className="flex-grow p-4 space-y-4">
                    <div className="bg-blue-900/10 border border-blue-900/30 p-4 rounded-lg shadow-inner">
                        <div className="text-[10px] font-black text-blue-500 uppercase mb-2">Active Epic</div>
                        <div className="text-xs font-bold text-white uppercase truncate">{(boardHierarchy?.rocks?.[0]?.epics?.[0]?.name) || 'Live Engine'}</div>
                    </div>
                </div>
            </div>

            <div style={{ width: hudWidth }} className="bg-slate-950 border-l border-slate-800 flex flex-col shrink-0 relative shadow-2xl overflow-hidden">
                <div onMouseDown={() => { const onMove = (me: MouseEvent) => setHudWidth(Math.max(150, Math.min(400, window.innerWidth - me.clientX))); const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); }; document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp); }} className="absolute top-0 left-0 w-1 h-full cursor-col-resize hover:bg-blue-600 transition-colors z-50" />
                <div className="p-3 border-b border-slate-800 flex items-center gap-2 bg-slate-900/40 shrink-0 uppercase tracking-widest font-black text-[10px] text-slate-500"><Users size={14} className="text-blue-500" /> Member HUD</div>
                <div className="flex-grow overflow-auto p-2 bg-black/10 scrollbar-hide">
                    <div className="flex flex-col gap-2">
                        {Object.entries(activeMembers || {}).map(([role, stats]: [string, any]) => {
                            const density = (stats && stats?.tokens > 0) ? (stats.lines_written * 1000 / stats.tokens).toFixed(1) : "0.0";
                            const lastAction = stats?.last_action || "";
                            const isRunning = lastAction !== "Idle";
                            return (
                                <div key={role} className={`bg-slate-900/60 border ${isRunning ? 'border-blue-500 shadow-lg shadow-blue-900/20' : 'border-slate-800'} p-3 rounded-lg border-l-2 border-l-blue-600 transition-all`}>
                                    <div className="flex justify-between items-center mb-2">
                                        <div className="flex items-center gap-2">
                                            {isRunning && <span className="text-blue-400 animate-pulse text-[10px]">●</span>}
                                            <span className="text-slate-100 font-bold text-[10px] uppercase tracking-tighter truncate">{String(role || 'Agent').replace('_', ' ')}</span>
                                        </div>
                                        <div className="flex items-center gap-1.5 text-[8px] font-black text-slate-500 uppercase">
                                            {lastAction === 'Idle' ? '' : `[${lastAction}]`}
                                        </div>
                                    </div>
                                    <div className="flex justify-between text-[9px] font-mono text-slate-500 bg-black/20 p-1.5 rounded"><span>Logic Density</span><span className="text-blue-400">{density}</span></div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
          </div>
        ) : (
            <div className="flex-grow flex flex-col p-8 gap-8 overflow-auto bg-[#020617]">
              <header className="flex justify-between items-end">
                  <div><h1 className="text-3xl font-black text-white uppercase tracking-tighter">Verification Center</h1><p className="text-slate-500 text-sm mt-1">Empirical FIT-style results.</p></div>
                  <div className="flex gap-4"><div className="bg-slate-900 border border-slate-800 px-4 py-2 rounded-lg text-center"><div className="text-[10px] font-black text-slate-500 uppercase">Pass Rate</div><div className="text-xl font-mono text-green-400">92.4%</div></div></div>
              </header>
              <div className="grid grid-cols-1 gap-4">{(boardHierarchy?.rocks || []).map((rock: any) => (rock?.epics || []).map((epic: any) => (
                      <div key={epic.id} className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
                          <div className="p-4 border-b border-slate-800 bg-black/20 flex justify-between items-center"><div className="flex items-center gap-3"><Package size={16} className="text-blue-500" /><span className="font-bold text-slate-200 uppercase tracking-tight">{epic.name}</span></div><span className="text-[10px] font-mono text-slate-500">{epic.id}</span></div>
                          <div className="p-0"><table className="w-full text-left text-[12px]"><thead className="bg-black/40 text-slate-500 uppercase text-[9px] font-black tracking-widest"><tr><th className="px-6 py-3">Unit / Issue</th><th className="px-6 py-3">Last Run</th><th className="px-6 py-3">Scenarios</th><th className="px-6 py-3 text-right">Status</th></tr></thead><tbody className="divide-y divide-slate-800/50">{(epic?.issues || []).map((issue: any) => (
                                          <tr key={issue.id} className="hover:bg-blue-600/5 transition-colors group cursor-pointer" onClick={() => openFile({name: `model/core/epics/${epic.id}.json`, asset_type: 'issue', issue_id: issue.id})}><td className="px-6 py-4"><div className="font-bold text-slate-300">{issue.name}</div><div className="text-[10px] text-slate-600 font-mono mt-0.5">{issue.id}</div></td><td className="px-6 py-4 text-slate-500 font-mono">{issue.last_verification?.timestamp ? new Date(issue.last_verification.timestamp).toLocaleString() : 'Never'}</td><td className="px-6 py-4"><div className="flex items-center gap-2"><div className="h-1.5 w-24 bg-slate-800 rounded-full overflow-hidden"><div className="h-full bg-blue-500" style={{ width: `${(issue?.scenarios?.length || 0) * 20}%` }}></div></div><span className="text-[10px] text-slate-500">{issue?.scenarios?.length || 0}</span></div></td><td className="px-6 py-4 text-right"><div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded font-black uppercase text-[9px] ${issue.status === 'done' ? 'bg-green-950/30 text-green-400 border border-green-900/50' : issue.status === 'code_review' ? 'bg-blue-950/30 text-blue-400 border border-blue-900/50' : 'bg-slate-800/50 text-slate-500'}`}>{issue.status === 'done' ? <CheckCircle2 size={10} /> : <Activity size={10} />}{issue.status}</div></td></tr>
                                      ))}</tbody></table></div></div>)))}</div>
            </div>
        )}
      </div>

      <div style={{ height: footerHeight }} className="fixed bottom-0 left-0 w-full border-t border-slate-800 bg-slate-950 flex flex-col z-40 shadow-[0_-15px_50px_rgba(0,0,0,0.7)]">
        <div onMouseDown={() => { const onMove = (me: MouseEvent) => setFooterHeight(Math.max(100, Math.min(600, window.innerHeight - me.clientY))); const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); }; document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp); }} className="h-1 w-full cursor-row-resize hover:bg-blue-600 transition-colors z-50 shrink-0" />
        <div className="flex-grow flex overflow-hidden">
            <div style={{ width: panel1Width }} className="border-r border-slate-800 p-3 flex flex-col bg-black/20 overflow-hidden shrink-0">
                <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2 opacity-40 text-blue-500 uppercase text-[9px] font-black tracking-widest"><Terminal size={12} /> System Event Stream</div>
                    <select value={activeLogSource} onChange={(e) => setActiveLogSource(e.target.value)} className="bg-slate-900 text-[8px] font-black text-slate-400 border border-slate-800 rounded px-1 outline-none cursor-pointer hover:border-blue-600 transition-colors">
                        {(availableLogs || []).map(l => <option key={l} value={l}>{String(l || 'log')?.split('/')?.pop() || 'log'}</option>)}
                    </select>
                </div>
                <div className="flex-grow overflow-auto font-mono text-[9px] text-slate-400 space-y-1 select-text px-2 border-l border-slate-900 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent hover:scrollbar-thumb-blue-600/50 flex flex-col-reverse">
                    <div ref={logEndRef} />
                    {(logs || []).slice().reverse().map((l, i) => (
                        <div key={i} className="group hover:bg-slate-900/50 transition-colors rounded px-1 flex items-start gap-2">
                            <span className="text-blue-600 font-bold shrink-0">[{l?.timestamp?.split('T')?.[1]?.split('.')?.[0] || '...'}]</span>
                            <span className={`uppercase font-black shrink-0 ${getRoleColor(l?.role)}`}>{l?.role || 'SYS'}</span>
                            <span className="text-slate-600 shrink-0">»</span>
                            <div className="flex-grow">
                                <span className="text-slate-200 font-bold">{l?.event}</span>
                                <span className="text-slate-500 ml-2 opacity-80 break-all">{l?.event === 'reasoning' ? ( <span className="italic text-slate-400 opacity-60">"{(l.data?.thought || '').slice(0, 300)}..."</span> ) : l?.event === 'tool_call' ? `EXECUTING ${l.data?.tool} (${l.data?.args?.path || l.data?.args?.issue_id || ''})` : l?.event === 'PROMPT' ? l.data?.msg : l?.event === 'REACTION' ? l.data?.msg : JSON.stringify(l?.data)?.slice(0, 120)}</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div onMouseDown={() => { const onMove = (me: MouseEvent) => setPanel1Width(Math.max(100, me.clientX)); const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); }; document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp); }} className="w-1 h-full cursor-col-resize hover:bg-blue-600 transition-colors z-50 shrink-0 bg-slate-800/50" />

            <div style={{ width: panel2Width }} className="border-r border-slate-800 bg-black/10 flex flex-col p-3 overflow-hidden shadow-inner shrink-0">
                <div className="flex items-center gap-2 mb-2 text-[10px] font-black text-blue-500 uppercase tracking-widest"><MessageSquare size={14} className="text-blue-500" /> Unit Execution Flow</div>
                <div className="flex-grow overflow-auto space-y-4 px-2 scrollbar-hide flex flex-col-reverse">
                    {(logs || []).filter(l => l?.event === 'member_message').slice().reverse().map((l, i) => (
                        <div key={i} className="bg-slate-900/40 border border-slate-800/50 rounded-xl p-4 shadow-xl border-l-4 border-l-blue-600 animate-in fade-in slide-in-from-bottom-2">
                            <div className="flex justify-between items-center mb-3">
                                <div className="flex items-center gap-2"><span className={`text-[11px] font-black uppercase tracking-tighter ${getRoleColor(l?.role)}`}>{l?.role}</span><span className="text-[9px] text-slate-600 font-mono">» UNIT: {l.data?.issue_id}</span></div>
                                <span className="text-[8px] text-slate-700 font-mono">{l?.timestamp?.split('T')?.[1]?.split('.')?.[0]}</span>
                            </div>
                            {l.data?.thought && ( <div className="mb-3 bg-blue-950/20 border border-blue-900/20 p-3 rounded-lg text-[11px] text-blue-300 italic leading-relaxed"> {l.data.thought}</div> )}
                            <div className="text-[13px] text-slate-200 leading-relaxed whitespace-pre-wrap font-sans select-text">{l.data?.content}</div>
                            {l.data?.tools?.length > 0 && ( <div className="mt-4 flex flex-wrap gap-2">{l.data.tools.map((tn: string, ti: number) => ( <div key={ti} className="flex items-center gap-1.5 bg-black/40 border border-slate-800 px-2 py-1 rounded text-[9px] font-black text-slate-500 uppercase tracking-widest"><Code size={10} className="text-blue-500" /> {tn}</div> ))}</div> )}
                        </div>
                    ))}
                </div>
            </div>

            <div onMouseDown={() => { const onMove = (me: MouseEvent) => setPanel2Width(Math.max(100, me.clientX - panel1Width)); const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); }; document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp); }} className="w-1 h-full cursor-col-resize hover:bg-blue-600 transition-colors z-50 shrink-0 bg-slate-800/50" />

            <div style={{ width: panel3Width }} className="border-r border-slate-800 bg-black/40 flex flex-col p-3 overflow-hidden shrink-0">
                <div className="flex items-center gap-2 mb-2 text-[10px] font-black text-green-500 uppercase tracking-widest"><Activity size={14} className="text-green-500" /> Driver Chat</div>
                <div className="flex-grow overflow-auto mb-2 space-y-2 scrollbar-hide flex flex-col-reverse">
                    {(logs || []).filter(l => l?.role === 'DRIVER' || l?.role === 'USER').slice().reverse().map((l, i) => (
                        <div key={i} className={`p-2 rounded text-[11px] ${l?.role === 'USER' ? 'bg-blue-900/20 text-blue-300 ml-4 border-l-2 border-blue-500' : 'bg-slate-900/40 text-slate-300 mr-4 border-l-2 border-green-500'}`}><div className="whitespace-pre-wrap">{l.data?.msg}</div></div>
                    ))}
                    {isChatting && ( <div className="text-[10px] text-green-500 animate-pulse flex items-center gap-2"><Activity size={10} fill="currentColor" /> Driver is architecting...</div> )}
                </div>
                <div className="flex gap-2">
                    <input value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && chatWithDriver()} placeholder="Driver command..." className="flex-grow bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-[11px] outline-none focus:border-blue-600 transition-colors" />
                    <button onClick={chatWithDriver} disabled={isChatting} className={`bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-lg transition-all ${isChatting ? 'opacity-50 animate-pulse' : ''}`}><Play size={12} fill="currentColor" /></button>
                </div>
            </div>

            <div onMouseDown={() => { const onMove = (me: MouseEvent) => setPanel3Width(Math.max(100, me.clientX - panel1Width - panel2Width)); const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); }; document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp); }} className="w-1 h-full cursor-col-resize hover:bg-blue-600 transition-colors z-50 shrink-0 bg-slate-800/50" />

            <div className="flex-grow p-3 flex flex-col bg-black/40 overflow-hidden relative">
                <div className="flex items-center gap-2 mb-2 opacity-40 text-blue-500 uppercase text-[9px] font-black tracking-widest"><Cpu size={12} /> Pulse Meter</div>
                <div className="flex-grow relative">
                    <div className="absolute top-0 right-0 flex gap-4 text-[9px] font-black tracking-tighter text-slate-500 z-10 p-1 bg-slate-950/80 rounded">
                        <div className="flex items-center gap-1"><div className="h-1.5 w-1.5 rounded-full bg-[#3b82f6]"></div> CPU {latestMetrics?.cpu?.toFixed(1) || 0}%</div>
                        <div className="flex items-center gap-1"><div className="h-1.5 w-1.5 rounded-full bg-[#0ea5e9]"></div> VRAM {latestMetrics?.vram?.toFixed(1) || 0}%</div>
                    </div>
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={metrics} margin={{ top: 20, right: 10, left: -20, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                            <XAxis dataKey="time" hide /><YAxis domain={[0, 100]} hide />
                            <ReferenceLine y={80} stroke="#ef4444" strokeDasharray="3 3" opacity={0.3} label={{ value: 'HIGH', position: 'insideRight', fill: '#ef4444', fontSize: 8, opacity: 0.5 }} />
                            <Line name="CPU" type="monotone" dataKey="cpu" stroke="#3b82f6" strokeWidth={2} dot={false} isAnimationActive={false} />
                            <Line name="VRAM" type="monotone" dataKey="vram" stroke="#0ea5e9" strokeWidth={2} dot={false} isAnimationActive={false} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
      </div>
    </div>
  );
}
