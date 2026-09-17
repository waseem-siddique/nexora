import React, {useState, useEffect, useContext, createContext, useRef} from 'react';

export const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);
let csrf = '';
export function setCsrf(value) { csrf = value || ''; }
export async function api(path, data, method = data === undefined ? 'GET' : 'POST') {
  const r = await fetch('/api' + path, {method, credentials: 'same-origin', headers: {
    'Content-Type': 'application/json', 'X-Nexora-Request': '1', ...(csrf ? {'X-CSRF-Token': csrf} : {})
  }, ...(data !== undefined ? {body: JSON.stringify(data)} : {})});
  let result;
  try { result = await r.json(); } catch { throw new Error('The server returned an unreadable response. Please restart the local server.'); }
  if (!r.ok) { const error = new Error(result.error || 'Something went wrong.'); error.status = r.status; throw error; }
  if (result.csrf) setCsrf(result.csrf);
  return result;
}
export function navigate(path) { window.history.pushState({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')); window.scrollTo({top:0, behavior:'instant'}); }
export function Link({to, children, className='', onClick, ...rest}) {
  return <a href={to} className={className} onClick={e => { if(!e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0) { e.preventDefault(); onClick?.(e); navigate(to); } }} {...rest}>{children}</a>;
}
export const formatDate = (s, options={day:'numeric',month:'short'}) => s ? new Date(s.substring(0,10)+'T12:00:00').toLocaleDateString('en-IN',options) : 'Not set';
export const initials = name => (name || 'Faculty').replace(/^Dr\.\s*/,'').split(' ').filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase();
export const avg = list => list.length ? Math.round(list.reduce((a,b)=>a+b,0)/list.length*10)/10 : null;
export const percent = n => n == null ? '—' : `${Math.round(n)}%`;
export const latestEvidence = rows => Object.values([...rows].sort((a,b)=>a.recorded_on.localeCompare(b.recorded_on)||a.id-b.id).reduce((acc,r)=>({...acc,[r.course]:r}),{}));
export const planDelta = p => p.progress.length ? Math.round((p.progress.at(-1).score-p.data.baseline.score)*10)/10 : null;
export function recommendation(p) {
  const delta = planDelta(p); const latest = p.progress.at(-1);
  if (delta === null) return {title:'Collect evidence', text:'Log a follow-up assessment before adjusting this plan.', tone:'neutral'};
  if (delta < 0 || latest.attendance < 60) return {title:'Revise support',text:'Progress is below baseline or attendance remains under 60%. Offer a check-in and smaller learning steps.',tone:'orange'};
  if (delta < 5) return {title:'Adjust approach',text:'Improvement is under 5 points. Try worked examples and a shorter feedback cycle.',tone:'orange'};
  return {title:'Continue & review',text:'Assessment improved by at least 5 points. Keep support in place and verify retention at the next review.',tone:'green'};
}

const icons = {
  grid:<><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
  users:<><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/><circle cx="9" cy="7" r="4"/></>,
  user:<><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v2"/></>,
  layers:<><path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/></>,
  chart:<><path d="M4 3v17h17M8 15l4-5 4 2 5-7"/><path d="M17 5h4v4"/></>,
  book:<><path d="M12 5v16M3 3c4-1 6 0 9 2 3-2 5-3 9-2v16c-4-1-6 0-9 2-3-2-5-3-9-2Z"/></>,
  settings:<><path d="m9 3-.5 3-3 1-2.5-1-2 3 2 2v3l-2 2 2 3 2.5-1 3 1 .5 3h4l.5-3 3-1 2.5 1 2-3-2-2v-3l2-2-2-3-2.5 1-3-1L13 3Z"/><circle cx="11" cy="12" r="3"/></>,
  search:<><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
  bell:<><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
  sun:<><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></>,
  moon:<path d="M20.7 13.3A9 9 0 0 1 10.7 3.3 9 9 0 1 0 20.7 13.3Z"/>,
  arrow:<><path d="M4 12h16m-6-6 6 6-6 6"/></>,
  arrowUp:<><path d="m5 16 14-9M9 7h10v10"/></>,
  back:<><path d="M20 12H4m6 6-6-6 6-6"/></>,
  chevron:<path d="m9 5 7 7-7 7"/>,
  down:<path d="m6 9 6 6 6-6"/>,
  plus:<path d="M12 5v14M5 12h14"/>,
  close:<path d="m6 6 12 12M6 18 18 6"/>,
  check:<path d="m5 12 4 4L19 6"/>,
  shield:<><path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6l9-4Z"/><path d="m8 12 3 3 5-6"/></>,
  bolt:<path d="m13 2-9 12h7l-1 8 10-13h-7l0-7Z"/>,
  clock:<><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  calendar:<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6m10-6v6M3 11h18"/></>,
  upload:<><path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/></>,
  download:<><path d="M12 3v13m-5-5 5 5 5-5M4 16v5h16v-5"/></>,
  code:<><path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-15-4 20"/></>,
  target:<><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></>,
  info:<><circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.1"/></>,
  lock:<><rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 4v3"/></>,
  mail:<><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/></>,
  logout:<><path d="M9 21H4V3h5m6 4 5 5-5 5M8 12h12"/></>,
  menu:<path d="M4 6h16M4 12h16M4 18h16"/>,
  help:<><circle cx="12" cy="12" r="9"/><path d="M9 8a3 3 0 1 1 4 3c-1 .5-1 1-1 3m0 3v.1"/></>,
  file:<><path d="M14 2H5v20h14V7l-5-5Zm0 0v6h5M8 12h8m-8 4h8"/></>,
  edit:<><path d="m14 5 5 5M3 21l5-1L21 7l-5-5L3 15v6Z"/></>,
  trash:<><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/></>,
  refresh:<><path d="M20 10a8 8 0 0 0-14-5L3 8m0-5v5h5m-4 6a8 8 0 0 0 14 5l3-3m0 5v-5h-5"/></>,
  external:<><path d="M14 3h7v7m-9 2 9-9M10 3H3v18h18v-7"/></>,
  eye:<><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></>,
  filter:<><path d="M4 6h16M7 12h10m-7 6h4"/></>,
  monitor:<><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M12 17v4m-5 0h10"/></>,
  circle:<circle cx="12" cy="12" r="8"/>,
  graduation:<><path d="m3 8 9-5 9 5-9 5-9-5Z"/><path d="M7 11v5c3 2 7 2 10 0v-5M21 9v6"/></>,
};
export function Icon({name='grid', size=20, className='', ...rest}) { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className={`icon ${className}`} aria-hidden="true" {...rest}>{icons[name]||icons.grid}</svg>; }
export function Logo({compact=false,light=false}) { return <span className={`brand ${light?'brand-light':''}`}><svg className="brand-mark" viewBox="0 0 40 40" fill="none" role="img" aria-label="Nexora logo"><rect width="40" height="40" rx="10" fill="#172c55"/><path d="M9 29 18 10h5l-9 19H9ZM22 15l9 14h-6l-5-8 2-6Z" fill="white"/><path d="M16 25h8l-3-4h-3l-2 4Z" fill="#73C8FE"/></svg>{!compact&&<span className="brand-type">nexora<span className="brand-dot">.</span></span>}</span>; }
export function Footer({publicPage=false}) { return <footer className={`footer ${publicPage?'public-footer':''}`}><span>Developed by Batch - 8 of CSE-A</span><span>Academic Study Plan Studio <span className="footer-sep">/</span> PS-014</span></footer>; }
export function ThemeToggle(){ const {theme,toggleTheme}=useApp(); return <button type="button" className="icon-btn theme-toggle" onClick={toggleTheme} aria-label={`Switch to ${theme==='dark'?'light':'dark'} mode`} title={`Switch to ${theme==='dark'?'light':'dark'} mode`}><Icon name={theme==='dark'?'sun':'moon'}/></button>; }
export function Button({children,icon,variant='primary',busy=false,className='',...props}) { return <button className={`btn btn-${variant} ${className}`} {...props} disabled={props.disabled||busy}>{busy?<span className="spinner small"/>:icon&&<Icon name={icon} size={18}/>}<span>{children}</span></button>; }
export function Badge({children,tone}) { const map={'Needs Attention':'red','Keep Improving':'orange','On Track':'green','No evidence':'neutral','Active':'blue','Draft':'orange','Completed':'green','Archived':'neutral','Local rules':'neutral','Gemini':'blue','Ollama':'violet'}; return <span className={`badge badge-${tone||map[children]||'neutral'}`}><span className="badge-dot"/>{children}</span>; }
export function Avatar({name,size='md',color=0}) { return <span className={`avatar avatar-${size} avatar-${color%5}`}>{initials(name)}</span>; }
export function Empty({icon='users',title,description,children}) { return <div className="empty"><div className="empty-icon"><Icon name={icon} size={26}/></div><h3>{title}</h3><p>{description}</p>{children&&<div className="button-row">{children}</div>}</div>; }
export function Field({label,hint,children,className=''}) { return <label className={`field ${className}`}><span>{label}</span>{children}{hint&&<small>{hint}</small>}</label>; }
export function ErrorBox({children}) { return children?<div className="error-box" role="alert"><Icon name="info" size={18}/><span>{children}</span></div>:null; }
export function Notice({children,icon='shield',tone='blue'}) { return <div className={`notice notice-${tone}`}><Icon name={icon} size={19}/><div>{children}</div></div>; }
export function PageHeader({eyebrow,title,description,children}) { return <div className="page-heading"><div>{eyebrow&&<div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>{description&&<p>{description}</p>}</div>{children&&<div className="page-actions">{children}</div>}</div>; }
export function Modal({title,subtitle,children,onClose,wide=false}) {
  const ref=useRef(null), id=React.useId();
  useEffect(()=>{const old=document.activeElement;const body=document.body.style.overflow;document.body.style.overflow='hidden';
    const targets=()=>Array.from(ref.current?.querySelectorAll('button,a,input,select,textarea,[tabindex="0"]')||[]).filter(e=>!e.disabled&&e.getClientRects().length);
    setTimeout(()=>targets()[0]?.focus(),20);
    function key(e){if(e.key==='Escape')onClose();if(e.key==='Tab'){const list=targets();if(!list.length){e.preventDefault();return;}if(e.shiftKey&&document.activeElement===list[0]){e.preventDefault();list.at(-1).focus();}else if(!e.shiftKey&&document.activeElement===list.at(-1)){e.preventDefault();list[0].focus();}}}
    document.addEventListener('keydown',key);return()=>{document.removeEventListener('keydown',key);document.body.style.overflow=body;old?.focus();};
  },[]);
  return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><section ref={ref} className={`modal ${wide?'modal-wide':''}`} role="dialog" aria-modal="true" aria-labelledby={id}><div className="modal-heading"><div><h2 id={id}>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div><button className="icon-btn" onClick={onClose} aria-label="Close dialog"><Icon name="close"/></button></div><div className="modal-body">{children}</div></section></div>;
}
export function download(content,name,type='application/json'){const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
export function exportCSV(rows,name){if(!rows.length)return; const keys=Object.keys(rows[0]); const escape=v=>{let s=String(v??'');if(/^[=+\-@\t\r]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};download([keys,...rows.map(r=>keys.map(k=>r[k]))].map(row=>row.map(escape).join(',')).join('\r\n'),name,'text/csv;charset=utf-8');}

// UI-native, accessible SVG data plot. Values are not smoothed or interpolated.
export function TrendChart({points,lines=[{key:'score',label:'Assessment',color:'var(--blue)'},{key:'attendance',label:'Attendance',color:'var(--chart-teal)'}],height=208}){
  const plotRef=useRef(null); const [plotWidth,setPlotWidth]=useState(620);
  useEffect(()=>{if(!plotRef.current)return;const o=new ResizeObserver(entries=>setPlotWidth(Math.max(250,Math.round(entries[0].contentRect.width))));o.observe(plotRef.current);return()=>o.disconnect();},[points.length]);
  const W=plotWidth,H=height,L=36,R=24,T=16,B=32;
  const px=i=>L+i*(W-L-R)/Math.max(points.length-1,1), py=n=>T+(100-n)*(H-T-B)/100;
  const id=React.useId().replaceAll(':','');
  if(!points.length)return <Empty icon="chart" title="Waiting for evidence" description="Add dated performance records to see the trend."/>;
  return <div className="trend-wrap" ref={plotRef}><svg className="trend-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby={id}><title id={id}>Performance over time. Assessment and attendance percentages on a zero to one hundred scale. Exact values are available below.</title>{[0,25,50,75,100].map(n=><g key={n}><line x1={L} y1={py(n)} x2={W-R} y2={py(n)} stroke="var(--border)" strokeDasharray="3 5"/><text x={L-10} y={py(n)+4} textAnchor="end" fill="var(--muted)" fontSize="12">{n}</text></g>)}{lines.map((line,j)=><g key={line.key}>{j===0&&points.every(p=>p[line.key]!=null)&&<polygon points={`${px(0)},${py(0)} ${points.map((p,i)=>`${px(i)},${py(p[line.key])}`).join(' ')} ${px(points.length-1)},${py(0)}`} fill="var(--chart-fill)"/>}<polyline points={points.map((p,i)=>p[line.key]!=null?`${px(i)},${py(p[line.key])}`:null).filter(Boolean).join(' ')} stroke={line.color} strokeWidth="2.5" strokeDasharray={j?'5 5':undefined} fill="none" strokeLinecap="round" strokeLinejoin="round"/>{points.map((p,i)=>p[line.key]!=null&&<circle key={i} cx={px(i)} cy={py(p[line.key])} r={3.5} fill="var(--surface)" stroke={line.color} strokeWidth="2"><title>{p.label}: {line.label} {p[line.key]}%</title></circle>)}</g>)}{points.map((p,i)=><text key={i} x={px(i)} y={H-8} textAnchor="middle" fill="var(--muted)" fontSize="12">{p.label}</text>)}</svg><div className="chart-bottom"><div className="chart-legend">{lines.map((l,i)=><span key={l.key}><i style={{background:l.color,opacity:i?.65:1}}/>{l.label}</span>)}</div><details className="chart-data"><summary>View data</summary><div className="table-scroll"><table><thead><tr><th>Date</th>{lines.map(l=><th key={l.key}>{l.label}</th>)}</tr></thead><tbody>{points.map((p,i)=><tr key={i}><td>{p.label}</td>{lines.map(l=><td key={l.key}>{p[l.key]??'—'}%</td>)}</tr>)}</tbody></table></div></details></div></div>;
}
