import React,{useState,useEffect,useRef} from 'react';
import {createRoot} from 'react-dom/client';
import {AppContext,api,setCsrf,Link,navigate,Icon,Logo,Footer,ThemeToggle,Button,Avatar,ErrorBox,Empty} from './core';
import {Landing,Auth,PublicGuide} from './public';
import {Dashboard,Students,StudentDetail,Plans,Progress,Resources,StudentPortal,Reports,AcademicFiles,SyllabusPage,FacultyAnalytics} from './dashboard';
import {PlanDetail} from './plan-detail';
import {Settings,Profile,Security,Help} from './settings';
import {WorkspaceModal} from './modals';
import {StudentDashboard,StudentPerformance,StudentPlan,StudentMarks,StudentAttendance,StudentReports,StudentFiles,StudentSyllabus,StudentHistory,StudentInbox} from './student';
import './styles.css';

const NAV=[['/app','grid','Overview'],['/app/students','users','Students'],['/app/plans','layers','Study Plans'],['/app/reports','file','Reports'],['/app/files','download','Academic Files'],['/app/syllabus','book','Syllabus'],['/app/progress','chart','Progress'],['/app/analytics','chart','Faculty Analytics']];
function Sidebar({path,user,workspace,onClose,logout}){const drafts=workspace?.plans.filter(p=>p.status==='Draft').length||0;const isActive=to=>path===to||(to!=='/app'&&path.startsWith(to+'/'));return <><div className="sidebar-brand"><Link to="/app" onClick={onClose} aria-label="Nexora overview"><Logo/></Link>{onClose&&<button className="icon-btn mobile-close" onClick={onClose} aria-label="Close navigation"><Icon name="close"/></button>}</div><div className="workspace-selector"><span className="workspace-icon"><Icon name="code" size={19}/></span><div><strong>CSE Academic Studio</strong><span>B.Tech · Faculty workspace</span></div></div><div className="nav-section-label">ACADEMIC WORKSPACE</div><nav className="side-nav" aria-label="Academic workspace">{NAV.map(([to,icon,label])=><Link key={to} to={to} onClick={onClose} aria-current={isActive(to)?'page':undefined} className={`side-link ${isActive(to)?'active':''}`}><Icon name={icon} size={19}/><span>{label}</span>{label==='Study Plans'&&drafts>0&&<small>{drafts}</small>}{label==='Overview'&&isActive(to)&&<span className="nav-active-dot"/>}</Link>)}</nav><div className="nav-section-label workspace-nav-label">YOUR WORKSPACE</div><nav className="side-nav" aria-label="Workspace settings">{[['/app/settings','settings','AI settings'],['/app/profile','user','My profile'],['/app/security','lock','Password & security']].map(([to,icon,label])=><Link key={to} to={to} onClick={onClose} aria-current={isActive(to)?'page':undefined} className={`side-link ${isActive(to)?'active':''}`}><Icon name={icon} size={19}/><span>{label}</span></Link>)}</nav><div className="sidebar-bottom"><div className="faculty-control-card"><span><Icon name="shield" size={18}/> Faculty in control</span><p>AI supports your judgment.<br/>It never replaces it.</p><Link to="/app/help" onClick={onClose}>Meet the workflow<Icon name="arrow" size={15}/></Link></div><Link to="/app/help" onClick={onClose} className={`side-link help-link ${isActive('/app/help')?'active':''}`}><Icon name="help" size={19}/><span>Help & project guide</span></Link><div className="sidebar-account"><Link to="/app/profile" onClick={onClose} className="sidebar-user"><Avatar name={user.name} size="sm"/><span><strong>{user.name}</strong><small>{user.is_demo?'Demo workspace':'Faculty mentor'}</small></span></Link><button className="icon-btn" aria-label="Sign out" title="Sign out" onClick={logout}><Icon name="logout" size={17}/></button></div></div></>;}

function Shell({path,children,context}){
 const {user,workspace,openModal,logout}=context;const [mobileOpen,setMobileOpen]=useState(false),[isMobile,setIsMobile]=useState(()=>window.matchMedia('(max-width: 1050px)').matches);const asideRef=useRef(null),trigger=useRef(null);
 useEffect(()=>{const m=window.matchMedia('(max-width: 1050px)');const f=e=>{setIsMobile(e.matches);if(!e.matches)setMobileOpen(false);};m.addEventListener('change',f);return()=>m.removeEventListener('change',f);},[]);
 useEffect(()=>{if(!mobileOpen)return;const old=document.body.style.overflow;document.body.style.overflow='hidden';const first=asideRef.current?.querySelector('a,button');first?.focus();function key(e){if(e.key==='Escape'){setMobileOpen(false);trigger.current?.focus();}if(e.key==='Tab'){const list=Array.from(asideRef.current?.querySelectorAll('a,button')||[]).filter(x=>x.getClientRects().length);if(e.shiftKey&&document.activeElement===list[0]){e.preventDefault();list.at(-1)?.focus();}if(!e.shiftKey&&document.activeElement===list.at(-1)){e.preventDefault();list[0]?.focus();}}}document.addEventListener('keydown',key);return()=>{document.body.style.overflow=old;document.removeEventListener('keydown',key);};},[mobileOpen]);
 useEffect(()=>{setMobileOpen(false);},[path]);
 const label=path==='/app'?'Overview':path.startsWith('/app/students/')?'Student profile':path.startsWith('/app/plans/')?'Study Plan details':([...NAV,['/app/settings','','AI settings'],['/app/profile','','My profile'],['/app/security','','Password & security'],['/app/help','','Project guide']].find(x=>x[0]===path)?.[2]||'Workspace');
 return <div className="app-shell"><a href="#main-content" className="skip-link">Skip to content</a>{mobileOpen&&<div className="sidebar-overlay" onClick={()=>setMobileOpen(false)}/>}<div className="print-hidden">{(!isMobile||mobileOpen)&&<aside ref={asideRef} className={`sidebar ${mobileOpen?'sidebar-open':''}`} role={isMobile?'dialog':undefined} aria-modal={isMobile?true:undefined} aria-label="Workspace navigation"><Sidebar path={path} user={user} workspace={workspace} onClose={isMobile?()=>{setMobileOpen(false);trigger.current?.focus();}:undefined} logout={logout}/></aside>}</div><div className="app-body"><header className="topbar"><div className="topbar-left"><button ref={trigger} className="icon-btn menu-toggle" onClick={()=>setMobileOpen(true)} aria-label="Open navigation"><Icon name="menu"/></button><span className="topbar-section">Workspace</span><Icon name="chevron" size={13}/><span className="topbar-current">{label}</span></div><div className="topbar-right"><button className="global-search" onClick={()=>openModal('search')} aria-label="Search workspace"><Icon name="search" size={17}/><span>Search anything...</span><kbd>/</kbd></button><span className="topbar-divider"/><ThemeToggle/><button className="icon-btn inbox-button" onClick={()=>openModal('inbox')} aria-label="Open review inbox"><Icon name="bell" size={19}/>{workspace?.plans.some(p=>p.status==='Draft')&&<i/>}</button><Link to="/app/profile" aria-label="Open profile" className="topbar-avatar"><Avatar name={user.name} size="sm"/></Link></div></header><main id="main-content" className="main-content" tabIndex={-1}>{!!user.is_demo&&<div className="demo-banner"><span><Icon name="monitor" size={15}/><strong>Sample workspace</strong><span>All student records are fictional. Explore freely.</span></span><Link to="/signup">Create your own<Icon name="arrow" size={15}/></Link></div>}{!user.is_demo&&workspace?.students.some(s=>s.synthetic)&&<div className="demo-banner"><span><Icon name="info" size={15}/><strong>Sample cohort loaded</strong><span>Marked records are synthetic.</span></span></div>}{children}</main><Footer/></div></div>;
}

const STUDENT_NAV=[['/student','grid','Dashboard'],['/student/performance','chart','My Performance'],['/student/plan','layers','My Study Plan'],['/student/reports','file','My Reports'],['/student/syllabus','book','Syllabus'],['/student/attendance','check','Attendance'],['/student/marks','file','Marks'],['/student/files','download','Academic Files'],['/student/history','clock','Task History'],['/student/inbox','bell','Inbox']];
function StudentShell({path,children,context}){
  const {user,workspace,logout}=context; const [mobileOpen,setMobileOpen]=useState(false),[isMobile,setIsMobile]=useState(()=>window.matchMedia('(max-width:1050px)').matches); const asideRef=useRef(null),trigger=useRef(null);
  useEffect(()=>{const m=window.matchMedia('(max-width:1050px)');const f=e=>{setIsMobile(e.matches);if(!e.matches)setMobileOpen(false)};m.addEventListener('change',f);return()=>m.removeEventListener('change',f)},[]);
  useEffect(()=>{setMobileOpen(false)},[path]);
  const active=to=>path===to; const label=(STUDENT_NAV.find(x=>x[0]===path)||['','','Student Portal'])[2];
  return <div className="app-shell student-shell"><a href="#main-content" className="skip-link">Skip to content</a>{mobileOpen&&<div className="sidebar-overlay" onClick={()=>setMobileOpen(false)}/>}
    <div className="print-hidden">{(!isMobile||mobileOpen)&&<aside ref={asideRef} className={`sidebar ${mobileOpen?'sidebar-open':''}`} role={isMobile?'dialog':undefined} aria-modal={isMobile?true:undefined} aria-label="Student navigation">
      <div className="sidebar-brand"><Link to="/student" onClick={()=>setMobileOpen(false)} aria-label="Nexora student portal"><Logo/></Link>{isMobile&&<button className="icon-btn mobile-close" onClick={()=>setMobileOpen(false)} aria-label="Close navigation"><Icon name="close"/></button>}</div>
      <div className="workspace-selector"><span className="workspace-icon"><Icon name="graduation" size={19}/></span><div><strong>Student Portal</strong><span>KITS · CSE · JNTUH R23</span></div></div>
      <div className="nav-section-label">MY ACADEMICS</div><nav className="side-nav" aria-label="Student navigation">{STUDENT_NAV.map(([to,icon,text])=><Link key={to} to={to} onClick={()=>setMobileOpen(false)} className={`side-link ${active(to)?'active':''}`} aria-current={active(to)?'page':undefined}><Icon name={icon} size={19}/><span>{text}</span>{text==='Inbox'&&(workspace?.notifications||[]).some(n=>!n.read_at)&&<small>!</small>}</Link>)}</nav>
      <div className="sidebar-bottom"><div className="faculty-control-card"><span><Icon name="shield" size={18}/> Faculty reviewed</span><p>Your study plan is based on the academic data shared by your faculty.</p></div><Link to="/student/profile" onClick={()=>setMobileOpen(false)} className="side-link"><Icon name="user" size={19}/><span>Profile</span></Link><div className="sidebar-account"><div className="sidebar-user"><Avatar name={user.name} size="sm"/><span><strong>{user.name}</strong><small>{user.student_id?'Student':'Portal user'}</small></span></div><button className="icon-btn" onClick={logout} aria-label="Sign out" title="Sign out"><Icon name="logout" size={17}/></button></div></div>
    </aside>}</div>
    <div className="app-body"><header className="topbar"><div className="topbar-left"><button ref={trigger} className="icon-btn menu-toggle" onClick={()=>setMobileOpen(true)} aria-label="Open navigation"><Icon name="menu"/></button><span className="topbar-section">Student Portal</span><Icon name="chevron" size={13}/><span className="topbar-current">{label}</span></div><div className="topbar-right"><ThemeToggle/><Link to="/student/inbox" className="icon-btn inbox-button" aria-label="Open inbox"><Icon name="bell" size={19}/>{(workspace?.notifications||[]).some(n=>!n.read_at)&&<i/>}</Link><Link to="/student/profile" aria-label="Open profile" className="topbar-avatar"><Avatar name={user.name} size="sm"/></Link></div></header>
      <main id="main-content" className="main-content" tabIndex={-1}><div className="student-portal-banner"><Icon name="shield" size={15}/><span><strong>Private student view</strong> · You can only see your own marks, attendance, plans, reports and shared files.</span></div>{children}</main><Footer/></div>
  </div>
}

function App(){
 const [path,setPath]=useState(location.pathname.replace(/\/$/,'')||'/'),[user,setUser]=useState(null),[workspace,setWorkspace]=useState(null),[boot,setBoot]=useState(true),[error,setError]=useState(''),[modal,setModal]=useState(null),[toasts,setToasts]=useState([]),[busy,setBusy]=useState(false);
 const [theme,setTheme]=useState(()=>{try{return localStorage.getItem('nexora-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');}catch{return 'light';}});
 const toast=(text,tone='success')=>{const id=Date.now()+Math.random();setToasts(t=>[...t,{id,text,tone}]);setTimeout(()=>setToasts(t=>t.filter(x=>x.id!==id)),5500);};
 const openModal=(type,payload={})=>setModal({type,payload});
 async function refresh(){try{const r=await api('/workspace');setWorkspace(r);setError('');return r;}catch(e){if(e.status===401){setUser(null);setWorkspace(null);setModal(null);navigate('/login');}setError(e.message);throw e;}}
 function login(result){setCsrf(result.csrf);setWorkspace(null);setUser(result.user);setError('');}
 async function logout(){try{await api('/auth/logout',{});setUser(null);setWorkspace(null);setModal(null);setCsrf('');navigate('/login');}catch(e){toast(e.message,'error');}}
 async function seed(){setBusy(true);try{await api('/workspace/seed',{});await refresh();toast('Your synthetic sample cohort is ready.');}catch(e){toast(e.message,'error');}finally{setBusy(false);}}
 async function bootSession(){setBoot(true);setError('');try{const r=await api('/session');setUser(r.user);}catch(e){setError(e.message);}finally{setBoot(false);}}
 useEffect(()=>{bootSession();const listener=()=>setPath(location.pathname.replace(/\/$/,'')||'/');window.addEventListener('popstate',listener);return()=>window.removeEventListener('popstate',listener);},[]);
 useEffect(()=>{document.documentElement.dataset.theme=theme;try{localStorage.setItem('nexora-theme',theme);}catch{}},[theme]);
 useEffect(()=>{if(user)refresh().catch(()=>{});},[user?.id]);
 useEffect(()=>{if(!boot&&(path.startsWith('/app')||path.startsWith('/student'))&&!user&&!error)navigate('/login');setModal(null);document.title=`${path==='/'?'Nexora — Every student. A clearer path forward.':'Nexora | Academic Study Plan Studio'}`;},[path,boot,user?.id]);
 useEffect(()=>{const key=e=>{const tag=document.activeElement?.tagName;if(e.key==='/'&&user&&path.startsWith('/app')&&!['INPUT','TEXTAREA','SELECT'].includes(tag)&&!modal){e.preventDefault();openModal('search');}};document.addEventListener('keydown',key);return()=>document.removeEventListener('keydown',key);},[user,path,modal]);
 const context={user,setUser,workspace,refresh,login,logout,toast,modal,setModal,openModal,theme,toggleTheme:()=>setTheme(t=>t==='dark'?'light':'dark'),seed,busy};
 let view;
 if(boot)view=<div className="boot-screen"><Logo/><span className="spinner"/><p>Making room for meaningful progress.</p><Footer/></div>;
 else if(!user&&error)view=<div className="boot-screen"><Logo/><ErrorBox>{error}</ErrorBox><Button onClick={bootSession}>Retry connection</Button><p>Make sure the local server is running.</p><Footer/></div>;
 else if(path==='/')view=<Landing/>;
 else if(path==='/login'||path==='/faculty-login'||path==='/signup')view=<Auth key={path} signup={path==='/signup'}/>;
 else if(path==='/student-login')view=<Auth key={path} signup={false} student/>;
 else if(path==='/guide'||path==='/privacy')view=<PublicGuide privacy={path==='/privacy'}/>;
 else if((path.startsWith('/app')||path.startsWith('/student'))&&user){
  let page;
  if(!workspace) page=<div className="loading-inline">{error?<><ErrorBox>{error}</ErrorBox><Button onClick={()=>refresh().catch(()=>{})}>Retry workspace</Button></>:<><span className="spinner"/>Loading your workspace...</>}</div>;
  else if(user.role==='student'){
   if(path==='/app'){navigate('/student');page=null;}
   else if(path==='/student')page=<StudentDashboard/>;
   else if(path==='/student/performance')page=<StudentPerformance/>;
   else if(path==='/student/plan')page=<StudentPlan/>;
   else if(path==='/student/marks')page=<StudentMarks/>;
   else if(path==='/student/attendance')page=<StudentAttendance/>;
   else if(path==='/student/reports')page=<StudentReports/>;
   else if(path==='/student/files')page=<StudentFiles/>;
   else if(path==='/student/syllabus')page=<StudentSyllabus/>;
   else if(path==='/student/history')page=<StudentHistory/>;
   else if(path==='/student/inbox')page=<StudentInbox/>;
   else if(path==='/student/profile')page=<Profile/>;
   else page=<Empty icon="search" title="Page not found" description="Use the student navigation to return to your academic dashboard."/>;
   view=page?<StudentShell path={path} context={context}>{page}</StudentShell>:null;
  } else {
   if(path==='/student'){navigate('/app');page=null;}
   else if(path==='/app')page=<Dashboard/>;
   else if(path==='/app/students')page=<Students/>;
   else if(/^\/app\/students\/\d+$/.test(path))page=<StudentDetail key={path} id={path.split('/').at(-1)}/>;
   else if(path==='/app/plans')page=<Plans/>;
   else if(/^\/app\/plans\/\d+$/.test(path))page=<PlanDetail key={path} id={path.split('/').at(-1)}/>;
   else if(path==='/app/progress')page=<Progress/>;
   else if(path==='/app/reports')page=<Reports/>;
   else if(path==='/app/files')page=<AcademicFiles/>;
   else if(path==='/app/syllabus')page=<SyllabusPage/>;
   else if(path==='/app/analytics')page=<FacultyAnalytics/>;
   else if(path==='/app/resources')page=<Resources/>;
   else if(path==='/app/settings')page=<Settings/>;
   else if(path==='/app/profile')page=<Profile/>;
   else if(path==='/app/security')page=<Security/>;
   else if(path==='/app/help')page=<Help/>;
   else page=<Empty icon="search" title="This page is not in your workspace" description="Let's get you back to a clearer starting point."><Link to="/app" className="btn btn-primary">Back to overview</Link></Empty>;
   view=page?<Shell path={path} context={context}>{page}</Shell>:null;
  }
 }else return <AppContext.Provider value={context}>{view}{workspace&&<WorkspaceModal/>}<div className="toast-stack" aria-live="polite">{toasts.map(t=><div key={t.id} className={`toast toast-${t.tone}`} role={t.tone==='error'?'alert':'status'}><Icon name={t.tone==='error'?'info':'check'} size={19}/><span>{t.text}</span><button className="icon-btn" onClick={()=>setToasts(x=>x.filter(i=>i.id!==t.id))} aria-label="Dismiss notification"><Icon name="close" size={15}/></button></div>)}</div></AppContext.Provider>;
}

class ErrorBoundary extends React.Component{constructor(props){super(props);this.state={error:false};}static getDerivedStateFromError(){return {error:true};}render(){return this.state.error?<div className="boot-screen"><Logo/><h1>Let’s get you back on track.</h1><p>A page could not be displayed. Your saved workspace remains on the server.</p><button className="btn btn-primary" onClick={()=>location.assign('/app')}>Reload workspace</button><Footer/></div>:this.props.children;}}
createRoot(document.getElementById('root')).render(<ErrorBoundary><App/></ErrorBoundary>);
