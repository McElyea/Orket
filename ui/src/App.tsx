import { useState, useEffect } from 'react';
import { Menu, FolderTree, Users, Activity, Terminal, Cpu, File, Folder, ChevronRight, ChevronLeft, Save, Play, Settings, Trello, Monitor, Rocket, Zap, CheckCircle2, MessageSquare, Code, LayoutGrid, Package, Search, Binoculars } from 'lucide-react';
import Editor from '@monaco-editor/react';
import { LineChart, Line, ResponsiveContainer, CartesianGrid, YAxis, XAxis, ReferenceLine } from 'recharts';
import KanbanPlugin from './components/KanbanPlugin';

const API_BASE = "http://127.0.0.1:8082";

export default function App() {
  const [activeTab, setActiveTab] = useState<'traction' | 'workstation'>('workstation');
  const [showTractionPlugin, setShowTractionPlugin] = useState(true);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [files, setFiles] = useState<any[]>([]);
  const [currentPath, setCurrentPath] = useState('.');
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [activeAssetType, setActiveAssetType] = useState<string | null>(null);
  const [activeIssueId, setActiveIssueId] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [lastRealContent, setLastRealContent] = useState('');
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
  const [collapsedNodes, setCollapsedNodes] = useState<Record<string, boolean>>({});

  const toggleNode = (id: string) => {
    setCollapsedNodes(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const executeFilter = false;
  const [isMenuOpen, setMenuOpen] = useState(false);
  const [driverSteered, setDriverSteered] = useState(false);
  const [activeLogSource, setActiveLogSource] = useState('orket.log');
  const [availableLogs, setAvailableLogs] = useState<string[]>(['orket.log']);
  
  const [sidebarWidth] = useState(260);
  const [hudWidth, setHudWidth] = useState(window.innerWidth / 2);
  const [footerHeight, setFooterHeight] = useState(280);
  
  // Footer Panel Widths
  const [panel1Width, setPanel1Width] = useState(window.innerWidth * 0.25);
  const [panel2Width, setPanel2Width] = useState(window.innerWidth * 0.25);
  const [panel3Width, setPanel3Width] = useState(window.innerWidth * 0.25);

  const [chatInput, setChatInput] = useState('');
  const [isChatting, setIsChatting] = useState(false);

  const [membersConfig, setMembersConfig] = useState<any>(null);
  const [settingsConfig, setSettingsConfig] = useState<any>(null);

  // Tooltip Delay logic
  const [tooltipText, setTooltipText] = useState<string | null>(null);
  const [tooltipTimer, setTooltipId] = useState<any>(null);

  const showTooltip = (text: string) => {
    const timer = setTimeout(() => setTooltipText(text), 3000); // 3s delay
    setTooltipId(timer);
  };

  const clearTooltip = () => {
    if (tooltipTimer) clearTimeout(tooltipTimer);
    setTooltipText(null);
  };

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
        setLogs(historicalLogs.slice(-150));
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

        // Load Last File or Organization Default
        const stored = localStorage.getItem('orket_last_file');
        if (stored) {
          try {
            const f = JSON.parse(stored);
            const fullPath = f.name.startsWith('model/') ? f.name : (currentPath === '.' ? f.name : `${currentPath}/${f.name}`);
            const res = await fetch(`${API_BASE}/system/read?path=${fullPath}`);
            const data = await res.json();
            setActiveFile(fullPath);
            setActiveAssetType(f.asset_type || 'file');
            setActiveIssueId(f.issue_id || null);
            setFileContent(data.content || '');
          } catch(e) {
            openFile({ name: 'model/organization.json', asset_type: 'organization' });
          }
        } else {
          openFile({ name: 'model/organization.json', asset_type: 'organization' });
        }
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
      setActiveAssetType(f.asset_type || 'file');
      setActiveIssueId(f.issue_id || null);
      setFileContent(data.content || '');
      setLastRealContent(data.content || '');
      localStorage.setItem('orket_last_file', JSON.stringify(f));
      setActiveTab('workstation');
    } catch (e) {
        console.error("Open File Error:", e);
    }
  };

  const runActiveAsset = async () => {
    if (!activeFile && !activeIssueId) return;
    setIsLaunching(true);
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
    } catch (e: any) { 
        alert(`Launch Failed: ${e.message}`); 
    } finally {
        setIsLaunching(false);
    }
  };

  const previewActiveAsset = async () => {
    if (!activeFile && !activeIssueId) return;

    if (activeAssetType === 'preview') {
        setFileContent(lastRealContent);
        setActiveAssetType('file'); 
        return;
    }

    setLastRealContent(fileContent); 
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
      const res = await fetch(`${API_BASE}/system/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: activeFile, content: fileContent })
      });
      if (res.ok) {
        setLogs(p => [...p, {role: 'SYS', event: 'COMMIT_SUCCESS', data: {file: activeFile}, timestamp: new Date().toISOString()}]);
      } else {
        alert("Failed to save file.");
      }
    } catch (e) { console.error("Save Error", e); }
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
                  <div className="text-white font-black tracking-widest uppercase text-xs animate-pulse">Executing Unit...</div>
              </div>
          </div>
      )}

      {/* DELAYED TOOLTIP */}
      {tooltipText && (
        <div className="fixed top-12 left-14 bg-slate-900 border border-slate-800 text-white px-3 py-1.5 rounded-md text-[10px] font-black uppercase tracking-widest z-[1000] shadow-2xl animate-in fade-in zoom-in-95">
          {tooltipText}
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
                    {!isExplorerOpen && (
                        <button onClick={() => { setExplorerOpen(true); setMenuOpen(false); }} className="w-full text-left px-4 py-2 text-xs hover:bg-blue-600 hover:text-white flex items-center gap-2"><LayoutGrid size={12}/> Restore Navigator</button>
                    )}
                    <button className="w-full text-left px-4 py-2 text-xs hover:bg-blue-600 hover:text-white flex items-center gap-2"><FolderTree size={12}/> Open Project</button>
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
            <button 
                onMouseEnter={() => showTooltip('Workstation')}
                onMouseLeave={clearTooltip}
                onClick={() => setActiveTab('workstation')}
                className={`flex items-center gap-2 px-3 py-1 rounded text-[10px] font-bold transition-all ${activeTab === 'workstation' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' : 'text-slate-500 hover:text-slate-300'}`}>
                <Monitor size={12}/>
            </button>
            {showTractionPlugin && (
              <button 
                  onMouseEnter={() => showTooltip('Traction Board')}
                  onMouseLeave={clearTooltip}
                  onClick={() => setActiveTab('traction')}
                  className={`flex items-center gap-2 px-3 py-1 rounded text-[10px] font-bold transition-all ${activeTab === 'traction' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' : 'text-slate-500 hover:text-slate-300'}`}>
                  <Trello size={12}/>
              </button>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-4">
            <span className="text-[10px] text-slate-500 font-mono tracking-tighter uppercase">{activeSessionId ? `SESSION: ${activeSessionId.slice(0,8)}` : 'RIG_IDLE'}</span>
            
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
                <Play size={10} fill="currentColor" /> {isLaunching ? 'EXECUTING...' : `EXECUTE ${activeAssetType?.toUpperCase() || 'CARD'}`}
            </button>
        </div>
      </div>

      {/* BODY */}
      <div className="flex-grow flex overflow-hidden min-h-0" style={{ marginBottom: footerHeight }}>
        
        {activeTab === 'workstation' ? (
          <div className="flex-grow flex min-w-0">
            {/* NAVIGATOR (ICON ONLY) */}
            <div className="w-12 bg-slate-950 border-r border-slate-800 flex flex-col items-center py-4 gap-4 shrink-0">
                <button 
                  onMouseEnter={() => showTooltip('Card Tree')} 
                  onMouseLeave={clearTooltip}
                  onClick={() => { setNavigatorView('traction_tree'); setExplorerOpen(true); }}
                  className={`p-2 rounded-lg transition-all ${navigatorView === 'traction_tree' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'text-slate-500 hover:bg-slate-900 hover:text-slate-300'}`}>
                  <Trello size={20} />
                </button>
                <button 
                  onMouseEnter={() => showTooltip('File Explorer')}
                  onMouseLeave={clearTooltip}
                  onClick={() => { setNavigatorView('explorer'); setExplorerOpen(true); }}
                  className={`p-2 rounded-lg transition-all ${navigatorView === 'explorer' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'text-slate-500 hover:bg-slate-900 hover:text-slate-300'}`}>
                  <FolderTree size={20} />
                </button>
                <button 
                  onMouseEnter={() => showTooltip('Members & Teams')}
                  onMouseLeave={clearTooltip}
                  onClick={() => { setNavigatorView('members'); setExplorerOpen(true); }}
                  className={`p-2 rounded-lg transition-all ${navigatorView === 'members' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'text-slate-500 hover:bg-slate-900 hover:text-slate-300'}`}>
                  <Users size={20} />
                </button>
                <button 
                  onMouseEnter={() => showTooltip('Settings')}
                  onMouseLeave={clearTooltip}
                  onClick={() => { setNavigatorView('settings'); setExplorerOpen(true); }}
                  className={`p-2 rounded-lg transition-all ${navigatorView === 'settings' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'text-slate-500 hover:bg-slate-900 hover:text-slate-300'}`}>
                  <Settings size={20} />
                </button>
                
                <div className="mt-auto border-t border-slate-800 w-full pt-4 flex flex-col items-center gap-4">
                    <button onMouseEnter={() => showTooltip('Spinoff Apps')} onMouseLeave={clearTooltip} className="p-2 text-slate-600 hover:text-cyan-400 transition-colors"><Package size={20}/></button>
                    <button onMouseEnter={() => showTooltip('System Utilities')} onMouseLeave={clearTooltip} className="p-2 text-slate-600 hover:text-purple-400 transition-colors"><LayoutGrid size={20}/></button>
                </div>
            </div>

            {/* LEFT 50%: NAVIGATOR PANEL + IDE */}
            <div className="flex flex-row overflow-hidden border-r border-slate-800 flex-grow">
                
                {/* NAVIGATOR PANEL */}
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
                                    <div className="text-[8px] text-slate-600 mb-2 px-2 uppercase font-bold tracking-widest opacity-50 truncate">Root: {currentPath}</div>
                                    {currentPath !== '.' && (
                                        <div onClick={goBack} className="flex items-center gap-2 py-1 px-3 text-[11px] text-blue-400 hover:bg-slate-900 cursor-pointer rounded mb-1 font-bold group">
                                            <ChevronLeft size={12} className="group-hover:-translate-x-1 transition-transform" /> .. [Back]
                                        </div>
                                    )}
                                    {files.map(f => (
                                        <div key={f.name} onClick={() => f.is_dir ? setCurrentPath(currentPath === '.' ? f.name : `${currentPath}/${f.name}`) : openFile(f)}
                                            className={`flex items-center gap-2 py-1.5 px-3 text-[11px] rounded cursor-pointer transition-colors ${activeFile?.includes(f.name) ? 'bg-blue-600/20 text-blue-400 border-l-2 border-blue-500 shadow-lg' : 'hover:bg-slate-900 hover:text-slate-100'}`}>
                                            {f.is_dir ? <Folder size={12} className="text-blue-500 fill-blue-500/10" /> : <File size={12} className={f.is_launchable ? "text-blue-400 font-bold" : "text-slate-500"} />}
                                            <span className="truncate">{f.name}</span>
                                        </div>
                                    ))}
                                </>
                            ) : navigatorView === 'traction_tree' ? (
                                <div className="space-y-4 p-1">
                                    {/* ROCKS & THEIR EPICS */}
                                    {boardHierarchy?.rocks?.filter((r: any) => r.status !== 'done' && r.status !== 'archived').map((rock: any) => {
                                        const hasEpics = rock.epics && rock.epics.length > 0;
                                        return (
                                            <div key={rock.id} className="space-y-1">
                                                <div className="flex items-center gap-2 group">
                                                    {hasEpics ? (
                                                        <button 
                                                            onClick={(e) => { e.stopPropagation(); toggleNode(rock.id); }}
                                                            className="w-4 h-4 flex items-center justify-center text-slate-600 hover:text-blue-400 font-bold text-[14px]">
                                                            {collapsedNodes[rock.id] ? '+' : '-'}
                                                        </button>
                                                    ) : (
                                                        <div className="w-4" />
                                                    )}
                                                    <div onClick={() => openFile({name: `model/core/rocks/${rock.id}.json`, asset_type: 'rock'})}
                                                        className="text-[10px] font-black text-blue-500 uppercase tracking-tighter cursor-pointer hover:text-blue-400">
                                                        <Trello size={12} className="inline mr-1" /> {rock.name}
                                                    </div>
                                                </div>
                                                
                                                {!collapsedNodes[rock.id] && rock.epics?.filter((e: any) => e.status !== 'done' && e.status !== 'archived').map((epic: any) => {
                                                    const hasIssues = epic.issues && epic.issues.length > 0;
                                                    return (
                                                        <div key={epic.id} className="ml-4 pl-2 border-l border-slate-800 space-y-1">
                                                            <div className="flex items-center gap-2 group">
                                                                {hasIssues ? (
                                                                    <button 
                                                                        onClick={(e) => { e.stopPropagation(); toggleNode(epic.id); }}
                                                                        className="w-3 h-3 flex items-center justify-center text-slate-600 hover:text-white font-bold text-[12px]">
                                                                        {collapsedNodes[epic.id] ? '+' : '-'}
                                                                    </button>
                                                                ) : (
                                                                    <div className="w-3" />
                                                                )}
                                                                <div onClick={() => openFile({name: `model/core/epics/${epic.id}.json`, asset_type: 'epic'})}
                                                                    className="text-[11px] font-bold text-slate-300 uppercase tracking-tight cursor-pointer hover:text-white">{epic.name}</div>
                                                            </div>
                                                            
                                                            {!collapsedNodes[epic.id] && epic.issues?.map((issue: any) => (
                                                                <div key={issue.id} onClick={() => openFile({name: `model/core/epics/${epic.id}.json`, asset_type: 'issue', issue_id: issue.id})}
                                                                    className="ml-5 text-[10px] text-slate-500 hover:text-blue-400 cursor-pointer transition-colors flex items-center gap-1">
                                                                    <span className="opacity-30">#</span> {issue.name}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        );
                                    })}

                                    {/* ORPHANED EPICS */}
                                    {boardHierarchy?.orphaned_epics?.length > 0 && (
                                        <div className="mt-6 space-y-2">
                                            <div className="flex items-center gap-2 border-b border-slate-900 pb-1">
                                                <button 
                                                    onClick={() => toggleNode('orphans')}
                                                    className="w-4 h-4 flex items-center justify-center text-slate-600 hover:text-orange-400 font-bold text-[14px]">
                                                    {collapsedNodes['orphans'] ? '+' : '-'}
                                                </button>
                                                <div className="text-[9px] font-black text-slate-600 uppercase tracking-[0.2em]">Orphaned Epics</div>
                                            </div>
                                            
                                            {!collapsedNodes['orphans'] && boardHierarchy.orphaned_epics.map((epic: any) => {
                                                const hasIssues = epic.issues && epic.issues.length > 0;
                                                return (
                                                    <div key={epic.id} className="space-y-1 ml-4">
                                                        <div className="flex items-center gap-2">
                                                            {hasIssues ? (
                                                                <button 
                                                                    onClick={() => toggleNode(epic.id)}
                                                                    className="w-3 h-3 flex items-center justify-center text-slate-600 hover:text-orange-400 font-bold text-[12px]">
                                                                    {collapsedNodes[epic.id] ? '+' : '-'}
                                                                </button>
                                                            ) : (
                                                                <div className="w-3" />
                                                            )}
                                                            <div onClick={() => openFile({name: `model/core/epics/${epic.id}.json`, asset_type: 'epic'})}
                                                                className="text-[11px] font-bold text-orange-400/70 uppercase tracking-tight cursor-pointer hover:text-orange-400">{epic.name}</div>
                                                        </div>
                                                        {!collapsedNodes[epic.id] && epic.issues?.map((issue: any) => (
                                                            <div key={issue.id} onClick={() => openFile({name: `model/core/epics/${epic.id}.json`, asset_type: 'issue', issue_id: issue.id})}
                                                                className="ml-5 text-[10px] text-slate-600 hover:text-blue-400 cursor-pointer transition-colors flex items-center gap-1">
                                                                <span className="opacity-30">#</span> {issue.name}
                                                            </div>
                                                        ))}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>
                            ) : null}
                        </div>
                    </div>
                </div>
                )}

                {/* IDE */}
                <div className="flex-grow flex flex-col bg-slate-950 min-w-0 relative">
                    <div className="h-8 bg-slate-900/30 border-b border-slate-800 flex items-center px-4 justify-between shrink-0">
                        <span className="text-[10px] font-mono text-slate-500">{activeFile || 'IDLE_IDE'}</span>
                        <div className="flex items-center gap-3">
                            <button 
                                onClick={previewActiveAsset}
                                disabled={!activeFile || isLaunching}
                                className={`transition-colors ${activeFile ? 'text-blue-500 hover:text-blue-400' : 'text-slate-700 cursor-not-allowed'}`}>
                                <Binoculars size={14} />
                            </button>
                            <button 
                                onClick={saveFile}
                                disabled={!activeFile}
                                className={`transition-colors ${activeFile ? 'text-blue-500 hover:text-blue-400' : 'text-slate-700 cursor-not-allowed'}`}>
                                <Save size={14} />
                            </button>
                            <span className={`text-[8px] font-black px-1.5 py-0.5 border rounded uppercase tracking-[0.2em] ${activeAssetType ? 'text-blue-400 border-blue-900/50 bg-blue-950/20' : 'text-slate-600 border-slate-800'}`}>
                                {activeAssetType || 'Read-Only'}
                            </span>
                        </div>
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
                    <div className={`grid gap-4 ${ Object.keys(activeMembers).length <= 4 ? 'grid-cols-1' : Object.keys(activeMembers).length <= 8 ? 'grid-cols-2' : 'grid-cols-3' }`}>
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
                        </div>
                        ))}
                    </div>
                </div>
            </div>
          </div>
        ) : (
          <KanbanPlugin backlog={backlog} calendar={calendar} updateStatus={updateStatus} openIssueDetail={(issue: any) => {
                let epicId = "";
                boardHierarchy?.rocks?.forEach((r: any) => r.epics?.forEach((e: any) => { if (e.issues?.some((i: any) => i.id === issue.id)) epicId = e.id; }));
                if (epicId) openFile({name: `model/core/epics/${epicId}.json`, asset_type: 'epic'}); else openIssueDetail(issue);
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
            {/* 1. SYSTEM EVENT STREAM */}
            <div style={{ width: panel1Width }} className="border-r border-slate-800 p-3 flex flex-col bg-black/20 overflow-hidden shrink-0">
                <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2 opacity-40 text-blue-500 uppercase text-[9px] font-black tracking-widest"><Terminal size={12} /> System Event Stream</div>
                    <select value={activeLogSource} onChange={(e) => setActiveLogSource(e.target.value)} className="bg-slate-900 text-[8px] font-black text-slate-400 border border-slate-800 rounded px-1 outline-none cursor-pointer hover:border-blue-600 transition-colors">
                        {availableLogs.map(l => <option key={l} value={l}>{l.split('/').pop()}</option>)}
                    </select>
                </div>
                <div className="flex-grow overflow-auto font-mono text-[9px] text-slate-400 space-y-1 select-text px-2 border-l border-slate-900 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent hover:scrollbar-thumb-blue-600/50">
                    {logs.map((l, i) => (
                        <div key={i} className="group hover:bg-slate-900/50 transition-colors rounded px-1 flex items-start gap-2">
                            <span className="text-blue-600 font-bold shrink-0">[{l.timestamp?.split('T')[1]?.split('.')[0] || '...'}]</span>
                            <span className={`uppercase font-black shrink-0 ${getRoleColor(l.role)}`}>{l.role || 'SYS'}</span>
                            <span className="text-slate-600 shrink-0">»</span>
                            <div className="flex-grow">
                                <span className="text-slate-200 font-bold">{l.event}</span>
                                <span className="text-slate-500 ml-2 opacity-80 break-all">
                                    {l.event === 'reasoning' ? ( <span className="italic text-slate-400 opacity-60">"{(l.data?.thought || '').slice(0, 300)}..."</span> ) : l.event === 'tool_call' ? `EXECUTING ${l.data?.tool} (${l.data?.args?.path || l.data?.args?.issue_id || ''})` : l.event === 'PROMPT' ? l.data?.msg : l.event === 'REACTION' ? l.data?.msg : JSON.stringify(l.data).slice(0, 120)}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* DIVIDER 1 */}
            <div onMouseDown={() => {
                const onMove = (me: MouseEvent) => setPanel1Width(Math.max(100, me.clientX));
                const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
                document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp);
            }} className="w-1 h-full cursor-col-resize hover:bg-blue-600 transition-colors z-50 shrink-0 bg-slate-800/50" />

            {/* 2. UNIT EXECUTION FLOW */}
            <div style={{ width: panel2Width }} className="border-r border-slate-800 bg-black/10 flex flex-col p-3 overflow-hidden shadow-inner shrink-0">
                <div className="flex items-center gap-2 mb-2 text-[10px] font-black text-blue-500 uppercase tracking-widest">
                    <MessageSquare size={14} className="text-blue-500" /> Unit Execution Flow
                </div>
                <div className="flex-grow overflow-auto space-y-4 px-2 no-scrollbar">
                    {logs.filter(l => l.event === 'member_message').map((l, i) => (
                        <div key={i} className="bg-slate-900/40 border border-slate-800/50 rounded-xl p-4 shadow-xl border-l-4 border-l-blue-600 animate-in fade-in slide-in-from-bottom-2">
                            <div className="flex justify-between items-center mb-3">
                                <div className="flex items-center gap-2">
                                    <span className={`text-[11px] font-black uppercase tracking-tighter ${getRoleColor(l.role)}`}>{l.role}</span>
                                    <span className="text-[9px] text-slate-600 font-mono">» UNIT: {l.data?.issue_id}</span>
                                </div>
                                <span className="text-[8px] text-slate-700 font-mono">{l.timestamp?.split('T')[1]?.split('.')[0]}</span>
                            </div>
                            {l.data?.thought && ( <div className="mb-3 bg-blue-950/20 border border-blue-900/20 p-3 rounded-lg text-[11px] text-blue-300 italic leading-relaxed"><Zap size={10} className="inline mr-2 mb-1" />{l.data.thought}</div> )}
                            <div className="text-[13px] text-slate-200 leading-relaxed whitespace-pre-wrap font-sans select-text">{l.data?.content}</div>
                            {l.data?.tools?.length > 0 && ( <div className="mt-4 flex flex-wrap gap-2">{l.data.tools.map((tn: string, ti: number) => ( <div key={ti} className="flex items-center gap-1.5 bg-black/40 border border-slate-800 px-2 py-1 rounded text-[9px] font-black text-slate-500 uppercase tracking-widest"><Code size={10} className="text-blue-500" /> {tn}</div> ))}</div> )}
                        </div>
                    ))}
                </div>
            </div>

            {/* DIVIDER 2 */}
            <div onMouseDown={() => {
                const onMove = (me: MouseEvent) => setPanel2Width(Math.max(100, me.clientX - panel1Width));
                const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
                document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp);
            }} className="w-1 h-full cursor-col-resize hover:bg-blue-600 transition-colors z-50 shrink-0 bg-slate-800/50" />

            {/* 3. DRIVER CHAT */}
            <div style={{ width: panel3Width }} className="border-r border-slate-800 bg-black/40 flex flex-col p-3 overflow-hidden shrink-0">
                <div className="flex items-center gap-2 mb-2 text-[10px] font-black text-slate-500 uppercase tracking-widest"><Activity size={14} className="text-green-500" /> Driver Chat</div>
                <div className="flex-grow overflow-auto mb-2 space-y-2 no-scrollbar">
                    {logs.filter(l => l.role === 'DRIVER' || l.role === 'USER').map((l, i) => (
                        <div key={i} className={`p-2 rounded text-[11px] ${l.role === 'USER' ? 'bg-blue-900/20 text-blue-300 ml-4 border-l-2 border-blue-500' : 'bg-slate-900/40 text-slate-300 mr-4 border-l-2 border-green-500'}`}>
                            <div className="whitespace-pre-wrap">{l.data?.msg}</div>
                        </div>
                    ))}
                    {isChatting && ( <div className="text-[10px] text-green-500 animate-pulse flex items-center gap-2"><Zap size={10} fill="currentColor" /> Driver is architecting...</div> )}
                </div>
                <div className="flex gap-2">
                    <input value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && chatWithDriver()} placeholder="Driver command..." className="flex-grow bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-[11px] outline-none focus:border-blue-600 transition-colors" />
                    <button onClick={chatWithDriver} disabled={isChatting} className={`bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-lg transition-all ${isChatting ? 'opacity-50 animate-pulse' : ''}`}><Play size={12} fill="currentColor" /></button>
                </div>
            </div>

            {/* DIVIDER 3 */}
            <div onMouseDown={() => {
                const onMove = (me: MouseEvent) => setPanel3Width(Math.max(100, me.clientX - panel1Width - panel2Width));
                const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
                document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp);
            }} className="w-1 h-full cursor-col-resize hover:bg-blue-600 transition-colors z-50 shrink-0 bg-slate-800/50" />

            {/* 4. PULSE METER */}
            <div className="flex-grow p-3 flex flex-col bg-black/40 overflow-hidden relative">
                <div className="flex items-center gap-2 mb-2 opacity-40 text-blue-500 uppercase text-[9px] font-black tracking-widest"><Cpu size={12} /> Pulse Meter</div>
                <div className="flex-grow relative">
                    <div className="absolute top-0 right-0 flex gap-4 text-[9px] font-black tracking-tighter text-slate-500 z-10 p-1 bg-slate-950/80 rounded">
                        <div className="flex items-center gap-1"><div className="h-1.5 w-1.5 rounded-full bg-[#3b82f6]"></div> CPU {latestMetrics.cpu.toFixed(1)}%</div>
                        <div className="flex items-center gap-1"><div className="h-1.5 w-1.5 rounded-full bg-[#0ea5e9]"></div> VRAM {latestMetrics.vram.toFixed(1)}%</div>
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

      {selectedIssue && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-xl z-[2000] flex items-center justify-center p-8">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[80vh] flex flex-col shadow-2xl overflow-hidden">
                  <div className="p-6 border-b border-slate-800 flex justify-between items-center bg-black/20">
                      <div><span className="text-[10px] font-black text-blue-500 uppercase tracking-[0.3em]">{selectedIssue.id}</span><h2 className="text-xl font-black text-slate-100 uppercase tracking-tight">{selectedIssue.summary}</h2></div>
                      <button onClick={() => setSelectedIssue(null)} className="text-slate-500 hover:text-white p-2">✕</button>
                  </div>
                  <div className="flex-grow flex overflow-hidden">
                      <div className="w-2/3 p-6 overflow-y-auto border-r border-slate-800 space-y-6">
                          <section><h4 className="text-[10px] font-black text-slate-500 uppercase mb-2 tracking-widest">Description</h4><div className="text-slate-300 text-[14px] leading-relaxed bg-black/20 p-4 rounded-lg border border-slate-800/50">{selectedIssue.note || 'No description provided.'}</div></section>
                          {(selectedIssue.status === 'done' || selectedIssue.status === 'canceled' || resolutionText) && (
                              <section><h4 className="text-[10px] font-black text-blue-500 uppercase mb-2 tracking-widest">Resolution</h4><textarea value={resolutionText} onChange={(e) => setResolutionText(e.target.value)} placeholder="Explain how this issue was resolved..." className="w-full bg-black/40 border border-slate-800 rounded-lg p-4 text-[13px] text-slate-200 min-h-[120px] focus:border-blue-600 outline-none transition-colors" /><button onClick={submitResolution} className="mt-2 bg-blue-600 hover:bg-blue-500 text-white text-[10px] font-black px-4 py-2 rounded uppercase tracking-widest shadow-lg shadow-blue-900/20">Save Resolution</button></section>
                          )}
                          <section><h4 className="text-[10px] font-black text-slate-500 uppercase mb-2 tracking-widest">Comments</h4><div className="space-y-4 mb-4">{issueComments.map((c, i) => ( <div key={i} className="bg-black/20 p-3 rounded border border-slate-800/50"><div className="flex justify-between text-[9px] mb-1"><span className="font-black text-blue-400 uppercase">{c.author}</span><span className="text-slate-600">{new Date(c.created_at).toLocaleString()}</span></div><p className="text-slate-300 text-[12px]">{c.content}</p></div> ))}</div><div className="flex gap-2"><input value={newComment} onChange={(e) => setNewComment(e.target.value)} placeholder="Add a comment..." className="flex-grow bg-black/40 border border-slate-800 rounded p-2 text-xs outline-none focus:border-blue-600" /><button onClick={addComment} className="bg-slate-800 hover:bg-slate-700 p-2 rounded text-blue-400"><Play size={14}/></button></div></section>
                      </div>
                      <div className="w-1/3 p-6 bg-black/10 space-y-6"><div><h4 className="text-[10px] font-black text-slate-500 uppercase mb-2 tracking-widest">Status</h4><span className="px-2 py-1 bg-blue-900/30 border border-blue-800 text-blue-400 rounded text-[10px] font-black uppercase">{selectedIssue.status}</span></div><div><h4 className="text-[10px] font-black text-slate-500 uppercase mb-2 tracking-widest">Assignee</h4><div className="text-[13px] font-bold text-slate-300 uppercase">{selectedIssue.assignee || 'Unassigned'}</div></div></div>
                  </div>
              </div>
          </div>
      )}
    </div>
  );
}