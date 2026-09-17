import React,{useState} from 'react';
import {useApp,api,Link,Icon,Button,Badge,Avatar,PageHeader,Empty,Notice,TrendChart,avg,percent,formatDate,latestEvidence,download} from './core';

function subjectRows(s){
  const rows={};
  for(const e of s.evidence||[]){
    rows[e.course]??={course:e.course, name:e.course, attendance:[], assessments:[]};
    rows[e.course].attendance.push(e);
    rows[e.course].assessments.push(e);
  }
  return Object.values(rows);
}
function activePlans(ws){return (ws.plans||ws.student?.plans||[]).filter(p=>p.status==='Active');}
function allTasks(ws){
  return activePlans(ws).flatMap(plan=>plan.data.activities.map((a,index)=>({...a,index,plan})));
}
function TaskCard({task,onDone}){
  const [open,setOpen]=useState(false), [difficulty,setDifficulty]=useState('Normal'), [saving,setSaving]=useState(false);
  const done=task.completed;
  async function complete(){
    setSaving(true);
    try{await onDone({plan_id:task.plan.id,index:task.index,completed:!done,difficulty});setOpen(false);}finally{setSaving(false);}
  }
  return <article className={`student-task ${done?'student-task-done':''}`}>
    <button className={`task-check-circle ${done?'checked':''}`} onClick={complete} disabled={saving} aria-label={done?'Mark task incomplete':'Mark task done'}>
      {done?<Icon name="check" size={16}/>:<span/>}
    </button>
    <div className="student-task-main">
      <div className="student-task-title"><h3>{task.title}</h3><span>{task.minutes} min</span></div>
      <p>{task.description}</p>
      <div className="student-task-meta"><span><Icon name="book" size={14}/>{task.plan.course}</span><span><Icon name="info" size={14}/>{task.topic||'Why this task? It is based on your latest performance check.'}</span></div>
      {!done&&<div className="student-task-actions"><Button variant="secondary" onClick={()=>setOpen(v=>!v)}>Mark as done</Button>{open&&<div className="difficulty-pick"><span>How difficult was this?</span>{['Easy','Normal','Difficult'].map(v=><button className={difficulty===v?'selected':''} key={v} onClick={()=>setDifficulty(v)}>{v}</button>)}<Button busy={saving} onClick={complete}>Save check-in</Button></div>}</div>}
    </div>
  </article>
}

export function StudentDashboard(){
  const {workspace,refresh,toast,openModal}=useApp(); const s=workspace.student; const tasks=allTasks(workspace).filter(t=>!t.completed).sort((a,b)=>a.due_on.localeCompare(b.due_on));
  const completed=allTasks(workspace).filter(t=>t.completed).length, total=allTasks(workspace).length;
  const plans=activePlans(workspace); const gap=s.target_cgpa!=null&&s.current_cgpa!=null?Math.max(0,Math.round((s.target_cgpa-s.current_cgpa)*100)/100):null;
  async function done(payload){await api('/student/tasks',payload,'PATCH');await refresh();toast('Task updated. Nice work!');}
  async function target(){openModal('studentTarget',{student:s});}
  return <><PageHeader eyebrow="STUDENT PORTAL" title={`Good Morning, ${s.name.split(' ')[0]}.`} description="Here is the academic work that matters most right now."/>
    <div className="student-summary-grid">
      <section className="student-status-card card"><div className="student-status-top"><div><span className="eyebrow">MY ACADEMIC STATUS</span><h2>{s.risk.level}</h2></div><span className={`status-orb status-${s.risk.level.toLowerCase().replaceAll(' ','-')}`}><Icon name={s.risk.level==='On Track'?'check':'target'} size={22}/></span></div><p>{s.risk.signals?.[0]||'Your current academic data does not show a specific concern.'}</p><div className="status-facts"><span><strong>{percent(s.risk.average)}</strong><small>Latest assessment</small></span><span><strong>{percent(s.risk.attendance)}</strong><small>Attendance</small></span><span><strong>{total?Math.round(completed/total*100):0}%</strong><small>Plan progress</small></span></div></section>
      <section className="target-card card"><div className="card-heading"><div><span className="eyebrow">MY TARGET</span><h2>Target CGPA</h2></div><Icon name="target"/></div><div className="target-number">{s.target_cgpa??'—'}</div><p>{gap===null?'Set a target to keep your study priorities clear.':gap===0?'You are at or above your target.':`${gap.toFixed(2)} points to your target CGPA.`}</p><Button variant="secondary" onClick={target}>Update target</Button></section>
    </div>
    <section className="card student-today"><div className="card-heading"><div><span className="eyebrow">TODAY'S FOCUS</span><h2>What You Need To Do Today</h2><p>Small, clear actions based on your marks, attendance and study plan.</p></div><span className="subtle-chip">{tasks.length} pending</span></div>
      <div className="student-task-list">{tasks.map(t=><TaskCard key={`${t.plan.id}-${t.index}`} task={t} onDone={done}/>)}</div>
      {!tasks.length&&<Empty icon="check" title="You are caught up" description="There are no pending tasks right now. Keep your momentum going."/>}
    </section>
    <section className="student-why card"><div className="student-why-icon"><Icon name="info"/></div><div><h3>Why these tasks?</h3><p>Nexora uses the academic records available to your faculty to highlight subjects and topics that need attention. Your faculty remains responsible for reviewing the plan.</p></div><Link to="/student/plan" className="text-link">View my study plan<Icon name="arrow" size={16}/></Link></section>
  </>;
}

export function StudentPerformance(){
  const {workspace}=useApp(); const s=workspace.student; const rows=subjectRows(s);
  const points=(s.evidence||[]).map(e=>({label:formatDate(e.recorded_on),score:e.score,attendance:e.attendance})).sort((a,b)=>a.label.localeCompare(b.label)).slice(-8);
  return <><PageHeader eyebrow="MY PERFORMANCE" title="See how your work is moving." description="Simple subject-by-subject view of the latest academic data your faculty has shared."/>
  <section className="detail-metrics"><div className="metric-card"><span className="metric-top">Current CGPA</span><strong className="metric-value">{s.current_cgpa??'—'}</strong><span className="metric-sub">From faculty records</span></div><div className="metric-card"><span className="metric-top">Target CGPA</span><strong className="metric-value">{s.target_cgpa??'—'}</strong><span className="metric-sub">My Target</span></div><div className="metric-card"><span className="metric-top">Attendance</span><strong className="metric-value">{percent(s.risk.attendance)}</strong><span className="metric-sub">Latest available</span></div><div className="metric-card"><span className="metric-top">Current semester</span><strong className="metric-value">{s.semester}</strong><span className="metric-sub">Section {s.section}</span></div></section>
  <div className="overview-middle"><section className="card trend-card"><div className="card-heading"><div><h2>Progress trend</h2><p>Latest recorded assessment and attendance values</p></div></div><TrendChart points={points}/></section>
  <section className="card"><div className="card-heading"><div><h2>Topics to improve</h2><p>Shown only where your latest records provide a reason.</p></div></div>{s.risk.signals?.length?<div className="signal-list">{s.risk.signals.slice(0,6).map((x,i)=><div key={i}><span className="signal-number">{i+1}</span><p>{x}</p></div>)}</div>:<Empty icon="check" title="Nothing specific flagged" description="Keep following your study plan and check back after new marks are added."/>}</section></div>
  <section className="card"><div className="card-heading"><div><h2>Subject performance</h2><p>Latest record available for each subject.</p></div></div><div className="table-scroll"><table><thead><tr><th>Subject</th><th>Latest assessment</th><th>Attendance</th><th>Assignments</th><th>Date</th></tr></thead><tbody>{rows.map(r=>{const e=[...r.assessments].sort((a,b)=>a.recorded_on.localeCompare(b.recorded_on)||a.id-b.id).at(-1);return <tr key={r.course}><td><strong>{workspace.courses[r.course]?.name||r.course}</strong><small>{r.course}</small></td><td>{percent(e?.score)}</td><td>{percent(e?.attendance)}</td><td>{percent(e?.completion)}</td><td>{formatDate(e?.recorded_on)}</td></tr>})}</tbody></table></div></section></>;
}

export function StudentMarks(){
  const {workspace}=useApp(); const s=workspace.student;
  const types=['MID-I','MID-II','Assignment','Semester','Assessment'];
  const latest=(course,type)=>[...(s.evidence||[])].filter(e=>e.course===course&&(e.assessment_type||'Assessment')===type).sort((a,b)=>a.recorded_on.localeCompare(b.recorded_on)||a.id-b.id).at(-1);
  const courses=Object.keys(workspace.courses).filter(c=>(s.evidence||[]).some(e=>e.course===c));
  return <><PageHeader eyebrow="MARKS" title="My marks" description="Assessment records shared by faculty. Missing assessment types are shown as dashes, not guessed."/><section className="card"><div className="table-scroll"><table><thead><tr><th>Subject</th>{types.map(t=><th key={t}>{t}</th>)}<th>Latest date</th></tr></thead><tbody>{courses.map(c=><tr key={c}><td><strong>{workspace.courses[c]?.name||c}</strong><small>{c}</small></td>{types.map(t=><td key={t}>{percent(latest(c,t)?.score)}</td>)}<td>{formatDate(latest(c,'MID-II')?.recorded_on||latest(c,'MID-I')?.recorded_on||latest(c,'Assessment')?.recorded_on)}</td></tr>)}</tbody></table></div></section></>;
}

export function StudentAttendance(){
  const {workspace}=useApp(); const s=workspace.student; const rows=Object.values(Object.fromEntries((s.evidence||[]).map(e=>[e.course,e])));
  return <><PageHeader eyebrow="ATTENDANCE" title="Keep your attendance visible." description="Latest attendance figures available in your academic records."/><section className="card"><div className="attendance-list">{rows.map(e=><div className="attendance-row" key={e.course}><div><strong>{workspace.courses[e.course]?.name||e.course}</strong><small>Updated {formatDate(e.recorded_on)}</small></div><strong>{percent(e.attendance)}</strong><div className="mini-track large"><i style={{width:`${e.attendance}%`}}/></div>)}</div></section><Notice icon="info">Attendance targets and university rules are not inferred here. Follow the academic requirements communicated by KITS/JNTUH and your faculty.</Notice></>;
}

export function StudentPlan(){
 const {workspace}=useApp(); const plans=activePlans(workspace); return <><PageHeader eyebrow="MY STUDY PLAN" title="Your plan, in plain English." description="Your faculty-approved study tasks, grouped by subject."/>
 {plans.length?plans.map(p=><section className="card student-plan-block" key={p.id}><div className="card-heading"><div><span className="eyebrow">{p.course}</span><h2>{p.data.title}</h2><p>{p.data.objective}</p></div><Badge>Active</Badge></div><div className="plan-rationale"><Icon name="info"/><p>{p.data.rationale}</p></div><div className="task-list">{p.data.activities.map((a,i)=><div className="task-item" key={i}><div className={`task-status-dot ${a.completed?'done':''}`}>{a.completed?<Icon name="check" size={13}/>:i+1}</div><div className="task-content"><div className="task-title"><h3>{a.title}</h3><span className="task-week">{a.minutes} min</span></div><p>{a.description}</p><div className="task-meta"><span>Week {a.week}</span><span>Due {formatDate(a.due_on)}</span>{a.difficulty&&<span>Check-in: {a.difficulty}</span>}</div></div></div>)}</div></section>):<Empty icon="layers" title="No active study plan yet" description="Your faculty can create and share a study plan after reviewing your academic records."/>}
 </>;
}

export function StudentReports(){
 const {workspace}=useApp(); const [open,setOpen]=useState(null);
 function exportReport(r){const d=JSON.parse(r.data||'{}');const lines=[`# ${r.title}`,`Generated: ${formatDate(r.created_at)}`,``, `## Student`,`${d.student.name} · ${d.student.roll}`,`Semester ${d.student.semester} · Section ${d.student.section}`,``,`## Academic status`,d.risk.level,`Assessment average: ${d.risk.average??'—'}%`,`Attendance: ${d.risk.attendance??'—'}%`,``,`## Recommendations`,d.plan?.objective||'No study plan attached.',``];download(lines.join('\n'),`nexora-report-${r.id}.md`,'text/markdown');}
 return <><PageHeader eyebrow="REPORTS / INBOX" title="My reports" description="Faculty-shared academic reports appear here first."/>
 <div className="report-list">{(workspace.reports||[]).length?(workspace.reports).map(r=><article className="card report-row" key={r.id}><div className="report-icon"><Icon name="file"/></div><div className="report-copy"><h3>{r.title}</h3><p>{r.shared_at?`Shared ${formatDate(r.shared_at)}`:`Generated ${formatDate(r.created_at)}`}</p></div><div className="report-actions"><Button variant="secondary" onClick={()=>setOpen(open===r.id?null:r.id)}>Open</Button><Button icon="download" onClick={()=>exportReport(r)}>Download</Button></div>{open===r.id&&<div className="report-preview">{(()=>{const d=JSON.parse(r.data||'{}');return <><div className="report-preview-head"><Badge>{d.risk?.level||'Report'}</Badge><span>{formatDate(d.generated_on)}</span></div><p>{d.plan?.objective||'This report does not include an active study plan.'}</p></>})()}</div>}</article>):<Empty icon="file" title="No reports yet" description="When faculty shares a report with you, it will appear here."/>}</div></>;
}

export function StudentFiles(){
 const {workspace}=useApp(); const files=workspace.files||[]; return <><PageHeader eyebrow="ACADEMIC FILES" title="Shared with you." description="Syllabus, study material and other files your faculty has made available."/><section className="card">{files.length?<div className="file-list">{files.map(f=><article className="file-row" key={f.id}><span className="file-row-icon"><Icon name="file"/></span><div><h3>{f.file_name}</h3><p>{f.category} · {Math.max(1,Math.round(f.size_bytes/1024))} KB</p></div><a className="btn btn-secondary btn-small" href={`/api/files/${f.id}/download`}><Icon name="download" size={16}/>Download</a></article>)}</div>:<Empty icon="file" title="No shared files yet" description="Faculty-uploaded syllabus and academic files will appear here when shared with you."/>}</section></>;
}

export function StudentSyllabus(){
 const {workspace}=useApp(); const files=(workspace.files||[]).filter(f=>String(f.category).toLowerCase()==='syllabus'); const courses=Object.values(workspace.courses);
 return <><PageHeader eyebrow="SYLLABUS" title={`Semester ${workspace.student.semester} reference`} description="Academic files shared by faculty plus the subject catalog available to the planning engine."/>
 <section className="card"><div className="card-heading"><div><h2>Shared syllabus files</h2><p>Open or download the files your faculty has shared.</p></div></div>{files.length?<div className="file-list">{files.map(f=><article className="file-row" key={f.id}><span className="file-row-icon"><Icon name="book"/></span><div><h3>{f.file_name}</h3><p>{f.category}</p></div><a className="btn btn-secondary btn-small" href={`/api/files/${f.id}/download`}><Icon name="download" size={16}/>Download</a></article>)}</div>:<Empty icon="book" title="No syllabus file shared yet" description="Ask faculty to upload the current course syllabus for your semester."/ >}</section>
 <div className="resource-grid">{courses.map(c=><article className="card resource-card" key={c.code}><span className="eyebrow">{c.code}</span><h2>{c.name}</h2><div className="topic-tags">{c.topics.map(t=><span key={t}>{t}</span>)}</div></article>)}</div></>;
}

export function StudentHistory(){
 const {workspace}=useApp(); const rows=allTasks(workspace).filter(t=>t.completed).sort((a,b)=>(b.completed_at||'').localeCompare(a.completed_at||'')); return <><PageHeader eyebrow="TASK HISTORY" title="Your study activity." description="A simple record of completed tasks and check-ins."/><section className="card">{rows.length?<div className="history-list">{rows.map(t=><div className="history-row" key={`${t.plan.id}-${t.index}`}><span className="history-check"><Icon name="check" size={14}/></span><div><strong>{t.title}</strong><small>{t.plan.course} · {formatDate(t.completed_at)} · {t.difficulty||'No difficulty check-in'}</small></div></div>)}</div>:<Empty icon="clock" title="No completed tasks yet" description="When you complete a study task, it will appear here."/ >}</section></>;
}

export function StudentInbox(){
 const {workspace,refresh}=useApp(); const notes=workspace.notifications||[]; async function read(n){if(n.read_at)return;await api(`/student/notifications/${n.id}`,{},'PATCH');await refresh();}
 return <><PageHeader eyebrow="INBOX" title="Your academic inbox." description="Reports, files and faculty updates delivered inside Nexora."/><section className="card"><div className="notification-list">{notes.length?notes.map(n=><button className={`notification-row ${!n.read_at?'unread':''}`} key={n.id} onClick={()=>read(n)}><span className="notification-icon"><Icon name={n.type==='report'?'file':n.type==='file'?'download':'bell'}/></span><span><strong>{n.title}</strong><small>{n.detail}</small><em>{formatDate(n.created_at)}</em></span></button>):<Empty icon="bell" title="Inbox is clear" description="New shared reports, files and faculty updates will appear here."/>}</div></section></>;
}
