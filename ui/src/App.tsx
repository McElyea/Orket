import { useState, useEffect } from 'react';
import { Menu, FolderTree, Users, Activity, Terminal, Cpu, File, Folder, ChevronRight, ChevronLeft, Save, Play, Settings, Trello, Monitor, Rocket, Zap, CheckCircle2 } from 'lucide-react';
import Editor from '@monaco-editor/react';
import { LineChart, Line, ResponsiveContainer, CartesianGrid, YAxis, XAxis, ReferenceLine } from 'recharts';
import KanbanPlugin from './components/KanbanPlugin';

const API_BASE = "http://127.0.0.1:8082";

export default function App() {
  const [activeTab, setActiveTab] = useState<'traction' | 'workstation'>('traction');
  const [showTractionPlugin, setShowTractionPlugin] = useState(true);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [files, setFiles] = useState<any[]>([]);
  const [currentPath, setCurrentPath] = useState('.');
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [activeAssetType, setActiveAssetType] = useState<string | null>(null);
  const [activeIssueId, setActiveIssueId] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [metrics, setMetrics] = useState<any>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [activeMembers, setActiveMembers] = useState<any>({});
  const [backlog, setBacklog] = useState<any[]>([]);
  const [calendar, setCalendar] = useState<any>(null);
  const [isLaunching, setIsLaunching] = useState(false);
  
  const [selectedIssue, setSelectedIssue] = useState<any>(null);
  const [issueComments, setIssueComments] = useState<any[]>([]);
  const [newComment, setNewComment] = useState('');
  const [resolutionText, setResolutionText] = useState('');

  const [isExplorerOpen, setExplorerOpen] = useState(true);
  const [navigatorView, setNavigatorView] = useState<'traction_tree' | 'explorer' | 'members' | 'settings'>('traction_tree');
  const [boardHierarchy, setBoardHierarchy] = useState<any>(null);
  const [executeFilter] = useState(false);
  const [isMenuOpen, setMenuOpen] = useState(false);
  const [driverSteered, setDriverSteered] = useState(false);
  const [activeLogSource, setActiveLogSource] = useState('orket.log');
  const [availableLogs, setAvailableLogs] = useState<string[]>(['orket.log']);
  
  const [sidebarWidth] = useState(260);
  const [hudWidth, setHudWidth] = useState(window.innerWidth / 2);
  const [footerHeight, setFooterHeight] = useState(240);

  const [chatInput, setChatInput] = useState('');
  const [isChatting, setIsChatting] = useState(false);

  const [membersConfig, setMembersConfig] = useState<any>(null);
  const [settingsConfig, setSettingsConfig] = useState<any>(null);

  const fetchMembers = async () => {
    try {
      const teamsRes = await fetch(`${API_BASE}/system/explorer?path=model/core/teams`);
      const skillsRes = await fetch(`${API_BASE}/system/explorer?path=model/core/skills`);
      setMembersConfig({
        teams: (await teamsRes.json()).items || [],
        skills: (await skillsRes.json()).items || []
      });
    } catch (e) {}
  };

  const fetchSettings = async () => {
    try {
      const dialectsRes = await fetch(`${API_BASE}/system/explorer?path=model/core/dialects`);
      const envsRes = await fetch(`${API_BASE}/system/explorer?path=model/core/environments`);
      const rootRes = await fetch(`${API_BASE}/system/explorer?path=model/core`);
      const rootFiles = (await rootRes.json()).items || [];
      
      setSettingsConfig({
        dialects: (await dialectsRes.json()).items || [],
        environments: (await envsRes.json()).items || [],
        core: rootFiles.filter((f: any) => f.name.endsWith('.json'))
      });
    } catch (e) {}
  };

  const fetchComments = async (issueId: string) => {
    try {
      const res = await fetch(`${API_BASE}/backlog/${issueId}/comments`);
      setIssueComments(await res.json());
    } catch (e) {}
  };

  const addComment = async () => {
    if (!selectedIssue || !newComment) return;
    try {
      await fetch(`${API_BASE}/backlog/${selectedIssue.id}/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: newComment, author: 'User' })
      });
      setNewComment('');
      fetchComments(selectedIssue.id);
    } catch (e) {}
  };

  const submitResolution = async () => {
    if (!selectedIssue || !resolutionText) return;
    try {
      await fetch(`${API_BASE}/backlog/${selectedIssue.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resolution: resolutionText, status: 'done' })
      });
      setResolutionText('');
      setSelectedIssue(null);
      if (activeSessionId) fetchBacklog(activeSessionId);
    } catch (e) {}
  };

  const openIssueDetail = (issue: any) => {
    setSelectedIssue(issue);
    setResolutionText(issue.resolution || '');
    fetchComments(issue.id);
  };

  const fetchBoard = async () => {
    try {
      const res = await fetch(`${API_BASE}/system/board`);
      setBoardHierarchy(await res.json());
    } catch (e) {}
  };

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

  const fetchAvailableLogs = async () => {
    try {
      const res = await fetch(`${API_BASE}/system/explorer?path=workspace/default/agents`);
      const data = await res.json();
      const agentLogs = (data.items || []).map((f: any) => `agents/${f.name}`);
      setAvailableLogs(['orket.log', ...agentLogs]);
    } catch (e) {}
  };

  const fetchLogs = async () => {
    try {
      const logPath = activeLogSource === 'orket.log' ? 'workspace/default/orket.log' : `workspace/default/${activeLogSource}`;
      const res = await fetch(`${API_BASE}/system/read?path=${logPath}`);
      const data = await res.json();
      if (data.content) {
        const lines = data.content.trim().split('\n');
        const historicalLogs = lines.map((l: string) => {
            try { return JSON.parse(l); } catch(e) { return { event: 'LOG', role: 'RAW', data: { msg: l }, timestamp: new Date().toISOString() }; }
        }).filter((l: any) => l !== null);
        setLogs(historicalLogs.slice(-100));
      }
    } catch (e) {}
  };

  const chatWithDriver = async () => {
    if (!chatInput) return;
    const userMsg = chatInput;
    setChatInput('');
    setLogs(p => [...p, {role: 'USER', event: 'PROMPT', data: {msg: userMsg}, timestamp: new Date().toISOString()}]);
    setIsChatting(true);
    try {
      const res = await fetch(`${API_BASE}/system/chat-driver`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg })
      });
      const data = await res.json();
      setLogs(p => [...p, {role: 'DRIVER', event: 'REACTION', data: {msg: data.response}, timestamp: new Date().toISOString()}]);
      fetchBoard();
    } catch (e: any) {
        alert("Driver Error: " + e.message);
        console.error("Driver Chat Failed", e);
    }
    finally { setIsChatting(false); }
  };

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
        fetchAvailableLogs();
        fetchLogs();
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

  useEffect(() => {
    const itv = setInterval(fetchLogs, 3000);
    return () => clearInterval(itv);
  }, [activeLogSource]);

  // 2. EXPLORER & BOARD
  useEffect(() => {
    if (activeTab === 'workstation' || activeTab === 'traction') {
        if (navigatorView === 'explorer') {
            const fetchFiles = async () => {
                try {
                  const res = await fetch(`${API_BASE}/system/explorer?path=${currentPath}`);
                  const data = await res.json();
                  setFiles(data.items || []);
                } catch (e) {}
            };
            fetchFiles();
        } else if (navigatorView === 'traction_tree') {
            fetchBoard();
        } else if (navigatorView === 'members') {
            fetchMembers();
        } else if (navigatorView === 'settings') {
            fetchSettings();
        }
    }
  }, [currentPath, activeTab, navigatorView]);

  const updateStatus = async (issueId: string, status: string) => {
    try {
      await fetch(`${API_BASE}/backlog/${issueId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
      });
      if (activeSessionId) fetchBacklog(activeSessionId);
    } catch (e) {}
  };

  const openFile = async (f: any) => {
    const fullPath = f.name.startsWith('model/') ? f.name : (currentPath === '.' ? f.name : `${currentPath}/${f.name}`);
    try {
      const res = await fetch(`${API_BASE}/system/read?path=${fullPath}`);
      const data = await res.json();
      setActiveFile(fullPath);
      setActiveAssetType(f.asset_type);
      setActiveIssueId(f.issue_id || null);
      setFileContent(data.content || '');
      setActiveTab('workstation');
    } catch (e) {
        console.error("Open File Error:", e);
    }
  };

  const runActiveAsset = async () => {
    if (!activeFile && !activeIssueId) return;
    setIsLaunching(true);
    console.log(`[RIG] Launching: ${activeIssueId || activeFile}`);
    try {
      const res = await fetch(`${API_BASE}/system/run-active`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            path: activeFile, 
            type: activeAssetType,
            issue_id: activeIssueId,
            driver_steered: driverSteered 
        })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setActiveSessionId(data.session_id);
      if (showTractionPlugin) setActiveTab('traction'); 
      console.log(`[RIG] Session Started: ${data.session_id}`);
    } catch (e: any) { 
        alert(`Launch Failed: ${e.message}`); 
    } finally {
        setIsLaunching(false);
    }
  };

  const previewActiveAsset = async () => {
    if (!activeFile && !activeIssueId) return;
    try {
      const res = await fetch(`${API_BASE}/system/preview-asset?path=${activeFile}&issue_id=${activeIssueId || ''}`);
      const data = await res.json();
      setFileContent(JSON.stringify(data, null, 2));
      setActiveAssetType('preview');
    } catch (e: any) {
        alert("Preview Failed: " + e.message);
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

  const getRoleColor = (role: string) => {
    if (!role) return 'text-slate-500';
    const r = role.toLowerCase();
    if (r.includes('driver')) return 'text-green-400';
    if (r.includes('architect')) return 'text-purple-400';
    if (r.includes('developer') || r.includes('specialist')) return 'text-blue-400';
    if (r.includes('owner') || r.includes('manager')) return 'text-orange-400';
    if (r.includes('user')) return 'text-cyan-400';
    return 'text-slate-200';
  };

  return (
    <div className="h-screen w-screen bg-[#020617] text-slate-300 flex flex-col overflow-hidden font-sans select-none text-[13px]">
      
      {/* LAUNCH OVERLAY */}
      {isLaunching && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-[1000] flex items-center justify-center">
              <div className="flex flex-col items-center gap-4">
                  <div className="h-12 w-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                  <div className="text-white font-black tracking-widest uppercase text-xs animate-pulse">Orkestrating Unit...</div>
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
                    <button onClick={() => setShowTractionPlugin(!showTractionPlugin)} className="w-full text-left px-4 py-2 text-xs hover:bg-blue-600 hover:text-white flex items-center gap-2">
                      <Zap size={12}/> {showTractionPlugin ? 'Shelve Traction' : 'Unshelve Traction'}
                    </button>
                    <div className="border-t border-slate-800 my-1"></div>
                    <button className="w-full text-left px-4 py-2 text-xs hover:bg-blue-600 hover:text-white flex items-center gap-2"><Settings size={12}/> Rig Settings</button>
                </div>
            )}
          </div>
          
          <span className="font-black tracking-[0.4em] text-xs text-slate-100 uppercase">Orket</span>

          <div className="flex bg-black/40 p-1 rounded-lg border border-slate-800 ml-4">
            {showTractionPlugin && (
              <button 
                  onClick={() => setActiveTab('traction')}
                  className={`flex items-center gap-2 px-3 py-1 rounded text-[10px] font-bold transition-all ${activeTab === 'traction' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' : 'text-slate-500 hover:text-slate-300'}`}>
                  <Trello size={12}/> TRACTION BOARD
              </button>
            )}
            <button 
                onClick={() => setActiveTab('workstation')}
                className={`flex items-center gap-2 px-3 py-1 rounded text-[10px] font-bold transition-all ${activeTab === 'workstation' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' : 'text-slate-500 hover:text-slate-300'}`}>
                <Monitor size={12}/> WORKSTATION
            </button>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
            <span className="text-[10px] text-slate-500 font-mono tracking-tighter uppercase">{activeSessionId ? `SESSION: ${activeSessionId.slice(0,8)}` : 'RIG_IDLE'}</span>
            
            {activeAssetType === 'epic' && backlog.length > 0 && backlog.every(i => i.status === 'done' || i.status === 'canceled') && (
              <button 
                onClick={async () => {
                    const res = await fetch(`${API_BASE}/system/archive-session`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ session_id: activeSessionId })
                    });
                    if (res.ok) { alert("Epic Archived."); fetchBoard(); }
                }}
                className="bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] font-black px-4 py-1.5 rounded-sm uppercase tracking-widest flex items-center gap-2 transition-all border border-slate-700 shadow-xl">
                <CheckCircle2 size={10} /> ARCHIVE & CLOSE EPIC
              </button>
            )}

            <button 
                onClick={() => setDriverSteered(!driverSteered)}
                className={`text-[10px] font-black px-3 py-1.5 rounded-sm uppercase tracking-widest flex items-center gap-2 transition-all ${driverSteered ? 'bg-purple-600 text-white shadow-lg shadow-purple-900/40' : 'bg-slate-800 text-slate-500 border border-slate-700'}`}>
                <Activity size={10} /> STEERED
            </button>

            <button 
                onClick={previewActiveAsset}
                disabled={!activeAssetType || activeAssetType === 'preview' || isLaunching}
                className={`text-[10px] font-black px-4 py-1.5 rounded-sm uppercase tracking-widest flex items-center gap-2 transition-all ${activeAssetType && activeAssetType !== 'preview' && !isLaunching ? 'bg-slate-700 hover:bg-slate-600 text-white' : 'bg-slate-800 text-slate-600 cursor-not-allowed opacity-50'}`}>
                <File size={10} /> PREVIEW
            </button>

            <button 
                onClick={runActiveAsset}
                disabled={(!activeAssetType && !activeIssueId) || isLaunching}
                className={`text-[10px] font-black px-4 py-1.5 rounded-sm uppercase tracking-widest flex items-center gap-2 transition-all ${ (activeAssetType || activeIssueId) && !isLaunching ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/40' : 'bg-slate-800 text-slate-600 cursor-not-allowed opacity-50'}`}>
                <Play size={10} fill="currentColor" /> {isLaunching ? 'ORKESTRATING...' : `ORKESTRATE ${activeAssetType?.toUpperCase() || 'CARD'}`}
            </button>
        </div>
      </div>

      {/* BODY */}
      <div className="flex-grow flex overflow-hidden min-h-0" style={{ marginBottom: footerHeight }}>
        
        {activeTab === 'workstation' ? (
          <div className="flex-grow flex min-w-0">
            {/* LEFT 50%: NAVIGATOR + IDE */}
            <div className="flex flex-row overflow-hidden border-r border-slate-800" style={{ width: `calc(100vw - ${hudWidth}px)` }}>
                
                {/* NAVIGATOR */}
                <div style={{ width: isExplorerOpen ? sidebarWidth : 40 }} className="flex bg-slate-950 border-r border-slate-800 transition-all duration-300 overflow-hidden shrink-0 relative shadow-2xl">
                    <div className="flex flex-col w-full h-full">
                        <div className="p-2 border-b border-slate-800 flex items-center justify-between bg-black/20 shrink-0 h-12 overflow-x-auto no-scrollbar">
                            {isExplorerOpen && (
                                <div className="flex bg-black/40 rounded-lg border border-slate-800 p-1 gap-1">
                                    <button onClick={() => setNavigatorView('traction_tree')} className={`flex items-center gap-2 px-3 py-1 rounded text-[10px] font-bold transition-all ${navigatorView === 'traction_tree' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}>
                                        <Trello size={14}/> TRACTION
                                    </button>
                                    <button onClick={() => setNavigatorView('explorer')} className={`flex items-center gap-2 px-3 py-1 rounded text-[10px] font-bold transition-all ${navigatorView === 'explorer' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}>
                                        <FolderTree size={14}/> FILES
                                    </button>
                                    <button onClick={() => setNavigatorView('members')} className={`flex items-center gap-2 px-3 py-1 rounded text-[10px] font-bold transition-all ${navigatorView === 'members' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}>
                                        <Users size={14}/> MEMBERS
                                    </button>
                                    <button onClick={() => setNavigatorView('settings')} className={`flex items-center gap-2 px-3 py-1 rounded text-[10px] font-bold transition-all ${navigatorView === 'settings' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}>
                                        <Settings size={14}/> SETTINGS
                                    </button>
                                </div>
                            )}
                            <button onClick={() => setExplorerOpen(!isExplorerOpen)} className="text-slate-500 hover:text-blue-500 p-1 shrink-0">
                                {isExplorerOpen ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
                            </button>
                        </div>
                        {isExplorerOpen && (
                            <div className="flex-grow overflow-auto p-2 scrollbar-hide">
                                {navigatorView === 'explorer' ? (
                                    <>
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
                                    </>
                                ) : navigatorView === 'traction_tree' ? (
                                    <div className="space-y-4 p-1">
                                        {boardHierarchy?.rocks.filter((r: any) => r.status !== 'done' && r.status !== 'archived').map((rock: any) => (
                                            <div key={rock.id} className="space-y-1">
                                                <div 
                                                    onClick={() => openFile({name: `model/core/rocks/${rock.id}.json`, asset_type: 'rock'})}
                                                    className="text-[10px] font-black text-blue-500 uppercase tracking-tighter flex items-center gap-2 cursor-pointer hover:text-blue-400 group">
                                                    <Zap size={12} className="group-hover:fill-blue-500/20"/> {rock.name}
                                                </div>
                                                {rock.epics.filter((e: any) => e.status !== 'done' && e.status !== 'archived').map((epic: any) => (
                                                    <div key={epic.id} className="ml-2 pl-2 border-l border-slate-800 space-y-1">
                                                        <div 
                                                            onClick={() => openFile({name: `model/core/epics/${epic.id}.json`, asset_type: 'epic'})}
                                                            className="text-[11px] font-bold text-slate-300 uppercase tracking-tight cursor-pointer hover:text-white">{epic.name}</div>
                                                        {epic.issues.map((issue: any) => (
                                                            <div key={issue.id} 
                                                                onClick={() => openFile({name: `model/core/epics/${epic.id}.json`, asset_type: 'issue', issue_id: issue.id})}
                                                                className="ml-2 text-[10px] text-slate-500 hover:text-blue-400 cursor-pointer transition-colors flex items-center gap-1">
                                                                <span className="opacity-30">#</span> {issue.name}
                                                            </div>
                                                        ))}
                                                    </div>
                                                ))}
                                            </div>
                                        ))}
                                        {(boardHierarchy?.orphaned_epics.filter((e: any) => e.status !== 'done' && e.status !== 'archived').length > 0 || boardHierarchy?.orphaned_issues.length > 0) && (
                                            <div className="mt-4 pt-4 border-t border-slate-800 space-y-3">
                                                <div className="text-[10px] font-black text-red-500 uppercase flex items-center gap-2 animate-pulse"><Zap size={12}/> Orphanage</div>
                                                {boardHierarchy.orphaned_epics.filter((e: any) => e.status !== 'done' && e.status !== 'archived').map((epic: any) => (
                                                    <div key={epic.id} onClick={() => openFile({name: `model/core/epics/${epic.id}.json`, asset_type: 'epic'})} className="text-[11px] text-slate-400 pl-2 cursor-pointer hover:text-white border-l border-red-900/50 ml-2">{epic.name}</div>
                                                ))}
                                                {boardHierarchy.orphaned_issues.map((issue: any) => (
                                                    <div key={issue.id} onClick={() => openIssueDetail(issue)} className="text-[10px] text-slate-500 pl-2 cursor-pointer hover:text-blue-400 border-l border-red-900/50 ml-2">[{issue.id}] {issue.name}</div>
                                                ))}
                                            </div>
                                        )}
                                        {boardHierarchy?.artifacts?.length > 0 && (
                                            <div className="mt-4 pt-4 border-t border-slate-800 space-y-2">
                                                <div className="text-[10px] font-black text-cyan-500 uppercase flex items-center gap-2"><Zap size={12}/> Artifacts</div>
                                                {boardHierarchy.artifacts.map((art: string) => (
                                                    <div key={art} onClick={() => openFile({name: `model/core/artifacts/${art}`, asset_type: 'artifact'})} className="text-[11px] text-slate-400 pl-2 cursor-pointer hover:text-white border-l border-cyan-900/50 ml-2">{art}</div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                ) : navigatorView === 'members' ? (
                                    <div className="space-y-6 p-1">
                                        <div className="space-y-2">
                                            <div className="text-[10px] font-black text-blue-500 uppercase tracking-widest flex items-center gap-2 opacity-70"><Users size={12}/> Teams</div>
                                            {membersConfig?.teams.map((t: any) => (
                                                <div key={t.name} onClick={() => openFile({name: `model/core/teams/${t.name}`, asset_type: 'team'})} className="text-[11px] text-slate-400 pl-2 cursor-pointer hover:text-white border-l border-slate-800 ml-1">{t.name}</div>
                                            ))}
                                        </div>
                                        <div className="space-y-2">
                                            <div className="text-[10px] font-black text-purple-500 uppercase tracking-widest flex items-center gap-2 opacity-70"><Cpu size={12}/> Skills</div>
                                            {membersConfig?.skills.map((s: any) => (
                                                <div key={s.name} onClick={() => openFile({name: `model/core/skills/${s.name}`, asset_type: 'skill'})} className="text-[11px] text-slate-400 pl-2 cursor-pointer hover:text-white border-l border-slate-800 ml-1">{s.name}</div>
                                            ))}
                                        </div>
                                    </div>
                                ) : (
                                    <div className="space-y-6 p-1">
                                        <div className="space-y-2">
                                            <div className="text-[10px] font-black text-blue-500 uppercase tracking-widest flex items-center gap-2 opacity-70"><Activity size={12}/> Dialects</div>
                                            {settingsConfig?.dialects.map((d: any) => (
                                                <div key={d.name} onClick={() => openFile({name: `model/core/dialects/${d.name}`, asset_type: 'dialect'})} className="text-[11px] text-slate-400 pl-2 cursor-pointer hover:text-white border-l border-slate-800 ml-1">{d.name}</div>
                                            ))}
                                        </div>
                                        <div className="space-y-2">
                                            <div className="text-[10px] font-black text-green-500 uppercase tracking-widest flex items-center gap-2 opacity-70"><Monitor size={12}/> Environments</div>
                                            {settingsConfig?.environments.map((e: any) => (
                                                <div key={e.name} onClick={() => openFile({name: `model/core/environments/${e.name}`, asset_type: 'environment'})} className="text-[11px] text-slate-400 pl-2 cursor-pointer hover:text-white border-l border-slate-800 ml-1">{e.name}</div>
                                            ))}
                                        </div>
                                        <div className="space-y-2">
                                            <div className="text-[10px] font-black text-orange-500 uppercase tracking-widest flex items-center gap-2 opacity-70"><Settings size={12}/> Core Configs</div>
                                            {settingsConfig?.core.map((c: any) => (
                                                <div key={c.name} onClick={() => openFile({name: `model/core/${c.name}`, asset_type: 'config'})} className="text-[11px] text-slate-400 pl-2 cursor-pointer hover:text-white border-l border-slate-800 ml-1">{c.name}</div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                {/* IDE */}
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
            </div>

            {/* RIGHT 50%: HUD (WIDE) */}
            <div style={{ width: hudWidth }} className="bg-slate-950 border-l border-slate-800 flex flex-col shrink-0 relative shadow-2xl overflow-hidden">
                <div onMouseDown={() => {
                    const onMove = (me: MouseEvent) => setHudWidth(Math.max(200, Math.min(600, window.innerWidth - me.clientX)));
                    const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
                    document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp);
                }} className="absolute top-0 left-0 w-1 h-full cursor-col-resize hover:bg-blue-600 transition-colors z-50" />
                
                <div className="p-3 border-b border-slate-800 flex items-center gap-2 bg-slate-900/40 shrink-0 uppercase tracking-widest font-black text-[10px] text-slate-500">
                    <Users size={14} className="text-blue-500" /> Member HUD
                </div>
                <div className="flex-grow overflow-auto p-4 bg-black/10">
                    <div className={`grid gap-4 ${
                        Object.keys(activeMembers).length <= 4 ? 'grid-cols-1' : 
                        Object.keys(activeMembers).length <= 8 ? 'grid-cols-2' : 'grid-cols-3'
                    }`}>
                        {Object.entries(activeMembers).map(([role, stats]: [string, any]) => (
                        <div key={role} className="bg-slate-900/60 border border-slate-800 p-4 rounded-lg border-l-4 border-l-blue-600 group hover:border-blue-500 transition-all shadow-xl h-fit">
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
                            {stats.detail && (
                                <div className="mt-3 bg-blue-950/20 border border-blue-900/30 p-2 rounded text-[9px] font-mono text-blue-300 truncate">
                                    <span className="opacity-50 mr-1">DETAIL:</span> {stats.detail}
                                </div>
                            )}
                        </div>
                        ))}
                    </div>
                </div>
            </div>
          </div>
        ) : (
          <KanbanPlugin 
            backlog={backlog} 
            calendar={calendar} 
            updateStatus={updateStatus} 
            openIssueDetail={(issue: any) => {
                let epicId = "";
                boardHierarchy?.rocks.forEach((r: any) => {
                    r.epics.forEach((e: any) => {
                        if (e.issues.some((i: any) => i.id === issue.id)) epicId = e.id;
                    });
                });
                if (epicId) openFile({name: `model/core/epics/${epicId}.json`, asset_type: 'epic'});
                else openIssueDetail(issue);
            }} 
          />
        )}
      </div>

      {/* FOOTER */}
      <div style={{ height: footerHeight }} className="fixed bottom-0 left-0 w-full border-t border-slate-800 bg-slate-950 flex flex-col z-40 shadow-[0_-15px_50px_rgba(0,0,0,0.7)]">
        <div onMouseDown={() => {
            const onMove = (me: MouseEvent) => setFooterHeight(Math.max(100, Math.min(600, window.innerHeight - me.clientY)));
            const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
            document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp);
        }} className="h-1 w-full cursor-row-resize hover:bg-blue-600 transition-colors z-50 shrink-0" />
        
        <div className="flex-grow flex overflow-hidden">
            <div className="w-[450px] border-r border-slate-800 p-3 flex flex-col bg-black/20 overflow-hidden shrink-0">
                <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2 opacity-40 text-blue-500 uppercase text-[9px] font-black tracking-widest"><Terminal size={12} /> System Event Stream</div>
                    <select 
                        value={activeLogSource} 
                        onChange={(e) => setActiveLogSource(e.target.value)}
                        className="bg-slate-900 text-[8px] font-black text-slate-400 border border-slate-800 rounded px-1 outline-none cursor-pointer hover:border-blue-600 transition-colors">
                        {availableLogs.map(l => <option key={l} value={l}>{l.split('/').pop()}</option>)}
                    </select>
                </div>
                <div className="flex-grow overflow-auto font-mono text-[9px] text-slate-400 space-y-1 select-text scrollbar-hide px-2 border-l border-slate-900">
                    {logs.map((l, i) => (
                        <div key={i} className="group hover:bg-slate-900/50 transition-colors rounded px-1 flex items-start gap-2">
                            <span className="text-blue-600 font-bold shrink-0">[{l.timestamp?.split('T')[1]?.split('.')[0] || '...'}]</span>
                            <span className={`uppercase font-black shrink-0 ${getRoleColor(l.role)}`}>{l.role || 'SYS'}</span>
                            <span className="text-slate-600 shrink-0">»</span>
                            <div className="flex-grow">
                                <span className="text-slate-200 font-bold">{l.event}</span>
                                <span className="text-slate-500 ml-2 opacity-80 break-all">
                                    {l.event === 'reasoning' ? (
                                        <span className="italic text-slate-400 opacity-60">"{(l.data?.thought || '').slice(0, 300)}..."</span>
                                    ) : l.event === 'tool_call' ? `EXECUTING ${l.data?.tool} (${l.data?.args?.path || l.data?.args?.issue_id || ''})` : 
                                     l.event === 'PROMPT' ? l.data?.msg : 
                                     l.event === 'REACTION' ? l.data?.msg :
                                     JSON.stringify(l.data).slice(0, 120)}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* CHAT WITH DRIVER PANEL */}
            <div className="flex-grow border-r border-slate-800 bg-black/40 flex flex-col p-3 overflow-hidden">
                <div className="flex items-center gap-2 mb-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">
                    <Activity size={14} className="text-green-500" /> Driver Chat
                </div>
                <div className="flex-grow overflow-auto mb-2 space-y-2 no-scrollbar">
                    {logs.filter(l => l.role === 'DRIVER' || l.role === 'USER').map((l, i) => (
                        <div key={i} className={`p-2 rounded text-[11px] ${l.role === 'USER' ? 'bg-blue-900/20 text-blue-300 ml-4 border-l-2 border-blue-500' : 'bg-slate-900/40 text-slate-300 mr-4 border-l-2 border-green-500'}`}>
                            <div className="flex justify-between opacity-50 text-[8px] font-black mb-1">
                                <span>{l.role}</span>
                                <span>{l.timestamp?.split('T')[1]?.split('.')[0]}</span>
                            </div>
                            <div className="whitespace-pre-wrap">{l.data?.msg}</div>
                        </div>
                    ))}
                    {isChatting && (
                        <div className="text-[10px] text-green-500 animate-pulse flex items-center gap-2">
                            <Zap size={10} fill="currentColor" /> Driver is architecting...
                        </div>
                    )}
                    {logs.filter(l => l.role === 'DRIVER' || l.role === 'USER').length === 0 && (
                        <div className="text-[11px] text-slate-500 italic">
                            Talk to the Driver to generate new Rocks, Epics, or Issues...
                        </div>
                    )}
                </div>
                <div className="flex gap-2">
                    <input 
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && chatWithDriver()}
                        placeholder="e.g. 'Add a new feature for data export...'"
                        className="flex-grow bg-slate-900 border border-slate-800 rounded-lg px-4 py-2 text-xs outline-none focus:border-blue-600 transition-colors"
                    />
                    <button 
                        onClick={chatWithDriver}
                        disabled={isChatting}
                        className={`bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg transition-all ${isChatting ? 'opacity-50 animate-pulse' : ''}`}>
                        <Play size={14} fill="currentColor" />
                    </button>
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

      {/* ISSUE DETAIL MODAL */}
      {selectedIssue && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-xl z-[2000] flex items-center justify-center p-8">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[80vh] flex flex-col shadow-2xl overflow-hidden">
                  <div className="p-6 border-b border-slate-800 flex justify-between items-center bg-black/20">
                      <div>
                          <span className="text-[10px] font-black text-blue-500 uppercase tracking-[0.3em]">{selectedIssue.id}</span>
                          <h2 className="text-xl font-black text-slate-100 uppercase tracking-tight">{selectedIssue.summary}</h2>
                      </div>
                      <button onClick={() => setSelectedIssue(null)} className="text-slate-500 hover:text-white p-2">✕</button>
                  </div>
                  
                  <div className="flex-grow flex overflow-hidden">
                      {/* LEFT: DETAILS */}
                      <div className="w-2/3 p-6 overflow-y-auto border-r border-slate-800 space-y-6">
                          <section>
                              <h4 className="text-[10px] font-black text-slate-500 uppercase mb-2 tracking-widest">Description</h4>
                              <div className="text-slate-300 text-[14px] leading-relaxed bg-black/20 p-4 rounded-lg border border-slate-800/50">
                                  {selectedIssue.note || 'No description provided.'}
                              </div>
                          </section>

                          {(selectedIssue.status === 'done' || selectedIssue.status === 'canceled' || resolutionText) && (
                              <section>
                                  <h4 className="text-[10px] font-black text-blue-500 uppercase mb-2 tracking-widest">Resolution</h4>
                                  <textarea 
                                      value={resolutionText}
                                      onChange={(e) => setResolutionText(e.target.value)}
                                      placeholder="Explain how this issue was resolved or why it was canceled..."
                                      className="w-full bg-black/40 border border-slate-800 rounded-lg p-4 text-[13px] text-slate-200 min-h-[120px] focus:border-blue-600 outline-none transition-colors"
                                  />
                                  <button 
                                      onClick={submitResolution}
                                      className="mt-2 bg-blue-600 hover:bg-blue-500 text-white text-[10px] font-black px-4 py-2 rounded uppercase tracking-widest shadow-lg shadow-blue-900/20">
                                      Save Resolution
                                  </button>
                              </section>
                          )}

                          <section>
                              <h4 className="text-[10px] font-black text-slate-500 uppercase mb-2 tracking-widest">Comments</h4>
                              <div className="space-y-4 mb-4">
                                  {issueComments.map((c, i) => (
                                      <div key={i} className="bg-black/20 p-3 rounded border border-slate-800/50">
                                          <div className="flex justify-between text-[9px] mb-1">
                                              <span className="font-black text-blue-400 uppercase">{c.author}</span>
                                              <span className="text-slate-600">{new Date(c.created_at).toLocaleString()}</span>
                                          </div>
                                          <p className="text-slate-300 text-[12px]">{c.content}</p>
                                      </div>
                                  ))}
                              </div>
                              <div className="flex gap-2">
                                  <input 
                                      value={newComment}
                                      onChange={(e) => setNewComment(e.target.value)}
                                      placeholder="Add a comment..."
                                      className="flex-grow bg-black/40 border border-slate-800 rounded p-2 text-xs outline-none focus:border-blue-600"
                                  />
                                  <button onClick={addComment} className="bg-slate-800 hover:bg-slate-700 p-2 rounded text-blue-400"><Play size={14}/></button>
                              </div>
                          </section>
                      </div>

                      {/* RIGHT: METRICS */}
                      <div className="w-1/3 p-6 bg-black/10 space-y-6">
                          <div>
                              <h4 className="text-[10px] font-black text-slate-500 uppercase mb-2 tracking-widest">Status</h4>
                              <span className="px-2 py-1 bg-blue-900/30 border border-blue-800 text-blue-400 rounded text-[10px] font-black uppercase">{selectedIssue.status}</span>
                          </div>
                          <div>
                              <h4 className="text-[10px] font-black text-slate-500 uppercase mb-2 tracking-widest">Credits Spent</h4>
                              <div className="text-3xl font-black text-slate-100 font-mono">{(selectedIssue.credits_spent || 0).toFixed(2)}<span className="text-sm text-blue-500 ml-1">c</span></div>
                          </div>
                          <div>
                              <h4 className="text-[10px] font-black text-slate-500 uppercase mb-2 tracking-widest">Assignee</h4>
                              <div className="text-[13px] font-bold text-slate-300 uppercase">{selectedIssue.assignee || 'Unassigned'}</div>
                          </div>
                          <div>
                              <h4 className="text-[10px] font-black text-slate-500 uppercase mb-2 tracking-widest">Priority</h4>
                              <span className={`text-[10px] font-black px-2 py-1 rounded uppercase ${selectedIssue.priority === 'Critical' ? 'bg-red-900/30 text-red-400 border border-red-800' : 'bg-slate-800 text-slate-400'}`}>
                                  {selectedIssue.priority}
                              </span>
                          </div>
                      </div>
                  </div>
              </div>
          </div>
      )}
    </div>
  );
}