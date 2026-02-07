import React from 'react';
import { Trello, Calendar, PlayCircle, CheckCircle2 } from 'lucide-react';

interface KanbanPluginProps {
  backlog: any[];
  calendar: any;
  updateStatus: (id: string, status: string) => void;
  openIssueDetail: (issue: any) => void;
}

const KanbanPlugin: React.FC<KanbanPluginProps> = ({ backlog, calendar, updateStatus, openIssueDetail }) => {
  const statuses = ['ready', 'blocked', 'ready_for_testing', 'waiting_for_developer', 'done', 'canceled'];

  return (
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
        {statuses.map(status => (
          <div key={status} className="w-[320px] shrink-0 flex flex-col bg-slate-900/40 border border-slate-800/50 rounded-xl overflow-hidden shadow-2xl backdrop-blur-sm">
            <div className="p-3 border-b border-slate-800 flex items-center justify-between bg-black/40 h-10">
              <span className="text-[9px] font-black uppercase tracking-[0.2em] text-slate-500">{status.replace(/_/g, ' ')}</span>
              <span className="text-[10px] font-mono text-slate-600 bg-black/40 px-2 rounded-full border border-slate-800">
                {backlog.filter(s => s.status === status).length}
              </span>
            </div>
            <div className="flex-grow overflow-y-auto p-3 space-y-3 scrollbar-hide">
              {backlog.filter(s => s.status === status).map(issue => (
                <div key={issue.id} 
                  onClick={() => openIssueDetail(issue)}
                  className="bg-slate-900/80 border border-slate-800 p-4 rounded-lg shadow-xl hover:border-blue-500/50 transition-all group relative cursor-pointer">
                  <div className={`absolute top-0 right-0 w-1 h-12 rounded-tr-lg rounded-br-lg ${issue.priority === 'Critical' ? 'bg-red-600' : issue.priority === 'High' ? 'bg-orange-500' : 'bg-blue-500'}`}></div>
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex flex-col">
                      <span className="text-[10px] font-black text-blue-600 uppercase tracking-widest">{issue.id}</span>
                      <span className="text-[9px] text-slate-600 font-bold">{issue.sprint}</span>
                    </div>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {status !== 'ready' && <button onClick={(e) => { e.stopPropagation(); updateStatus(issue.id, 'ready'); }} className="p-1 hover:bg-blue-600 rounded text-slate-500 hover:text-white"><PlayCircle size={14}/></button>}
                      {status !== 'done' && <button onClick={(e) => { e.stopPropagation(); updateStatus(issue.id, 'done'); }} className="p-1 hover:bg-green-600 rounded text-slate-500 hover:text-white"><CheckCircle2 size={14}/></button>}
                    </div>
                  </div>
                  <div className="text-[13px] font-black text-slate-100 uppercase mb-1 tracking-tight truncate">{issue.summary || issue.seat.replace(/_/g, ' ')}</div>
                  <div className="text-[11px] text-slate-500 italic leading-relaxed line-clamp-2">{issue.note}</div>
                  <div className="flex justify-between items-center mt-2 pt-2 border-t border-slate-800/50 text-[10px]">
                    <span className="text-slate-400 font-bold uppercase">{issue.assignee || 'Unassigned'}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-blue-500 font-mono">{(issue.credits_spent || 0).toFixed(1)}c</span>
                      <span className={`font-bold px-1.5 rounded ${issue.priority === 'Critical' ? 'text-red-400 bg-red-950/20' : 'text-slate-500'}`}>{issue.priority}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default KanbanPlugin;
