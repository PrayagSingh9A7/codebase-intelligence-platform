'use client'

import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  Activity, ArrowRight, BookOpen, Bot, Boxes, BrainCircuit, CheckCircle2, ChevronRight,
  CircleDot, Code2, Command, ExternalLink, FileCode2, GitBranch, GitCompareArrows,
  Github, Layers3, Loader2, LogIn, LogOut, Network, PanelLeft, Search, Send, Settings2,
  ShieldCheck, Sparkles, TerminalSquare, User, Workflow, X, Zap, AlertTriangle
} from 'lucide-react'
import { ArchitectureScene } from '../components/ArchitectureScene'

type Repo = { owner:string; name:string; full_name:string; url:string; branch:string; stars:number; forks:number; open_issues:number; description:string; topics:string[]; default_branch:string }
type Lang = { name:string; files:number; share:number }
type GraphNode = { id:string; label:string; path:string; language:string; degree?:number; module?:string }
type GraphEdge = { source:string; target:string; kind:string }
type GraphLayer = { id:string; name:string; files:number; node_ids:string[] }
type Analysis = { summary:string; modules:{name:string; files:number}[]; entrypoints:string[]; services:string[]; docs:string[]; relationships:number; graph_nodes:number; top_language:string; architecture_notes:string[] }
type Result = { repo:Repo; file_count:number; indexed_files:number; total_lines:number; languages:Lang[]; technologies:string[]; graph:{nodes:GraphNode[];edges:GraphEdge[];layers?:GraphLayer[]}; analysis:Analysis; flows:{name:string;explanation?:string;steps:{id:string;label:string;detail:string}[]}[]; docs:{title:string;summary:string;sections:{title:string;body:string}[]}; changes:{from:any;to:any;files:any[]}; commits:any[]; indexed_chunks:number }
type Message = {role:'user'|'assistant'; text:string; refs?:{path:string;chunk:number;score:number}[]}
type Profile = {name:string; email:string}
type Settings = {reduceMotion:boolean; compact:boolean}

const features = [
  ['overview','Overview',Boxes], ['architecture','Architecture',Network], ['graph','Knowledge Graph',BrainCircuit],
  ['dependencies','Dependencies',GitBranch], ['impact','Impact Analysis',Activity], ['flows','System Flows',Workflow],
  ['chat','AI Codebase Chat',Bot], ['docs','Documentation',FileCode2], ['changes','Architecture Changes',GitCompareArrows],
] as const

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function Home() {
  const [repoUrl,setRepoUrl] = useState('')
  const [data,setData] = useState<Result|null>(null)
  const [active,setActive] = useState('overview')
  const [loading,setLoading] = useState(false)
  const [error,setError] = useState('')
  const [cmdOpen,setCmdOpen] = useState(false)
  const [accountOpen,setAccountOpen] = useState(false)
  const [authOpen,setAuthOpen] = useState(false)
  const [authMode,setAuthMode] = useState<'login'|'signup'|'profile'>('login')
  const [authUser,setAuthUser] = useState<{id:number;name:string;email:string}|null>(null)
  const [authForm,setAuthForm] = useState({name:'',email:'',password:''})
  const [authError,setAuthError] = useState('')
  const [selectedFile,setSelectedFile] = useState<string|null>(null)
  const [fileSummary,setFileSummary] = useState<any>(null)
  const [fileLoading,setFileLoading] = useState(false)
  const [chat,setChat] = useState<Message[]>([])
  const [query,setQuery] = useState('')
  const [chatLoading,setChatLoading] = useState(false)
  const [impactTarget,setImpactTarget] = useState('')
  const [impact,setImpact] = useState<any>(null)
  const [profile,setProfile] = useState<Profile>({name:'Guest User',email:''})
  const [settings,setSettings] = useState<Settings>({reduceMotion:false,compact:false})

  useEffect(() => {
    try {
      const savedSettings = localStorage.getItem('cb_settings')
      if (savedSettings) setSettings(JSON.parse(savedSettings))
    } catch {}

    const token = localStorage.getItem('cb_token')
    if (!token) {
      localStorage.removeItem('cb_profile')
      setAuthUser(null)
      setProfile({name:'Guest User',email:''})
      return
    }

    fetch(`${API}/api/auth/me`, {headers:{Authorization:`Bearer ${token}`}})
      .then(async res => {
        if (!res.ok) throw new Error('Session expired')
        return res.json()
      })
      .then(body => {
        if (!body?.user) throw new Error('Invalid session')
        setAuthUser(body.user)
        setProfile({name:body.user.name,email:body.user.email})
      })
      .catch(() => {
        localStorage.removeItem('cb_token')
        localStorage.removeItem('cb_profile')
        setAuthUser(null)
        setProfile({name:'Guest User',email:''})
      })
  },[])

  useEffect(() => {
    if (authUser) localStorage.setItem('cb_profile',JSON.stringify(profile))
    else localStorage.removeItem('cb_profile')
  },[profile,authUser])
  useEffect(()=>{ localStorage.setItem('cb_settings',JSON.stringify(settings)) },[settings])

  const activeLabel = features.find(x=>x[0]===active)?.[1] || 'Overview'

  async function submitAuth() {
    setAuthError('')
    const mode = authMode === 'signup' ? 'signup' : 'login'
    if(!authForm.email || !authForm.password) return setAuthError('Email and password are required.')
    if(mode === 'signup' && !authForm.name.trim()) return setAuthError('Name is required.')
    if(mode === 'signup' && authForm.password.length < 8) return setAuthError('Use at least 8 characters for your password.')
    try {
      const res = await fetch(`${API}/api/auth/${mode}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(authForm)})
      const body = await res.json()
      if(!res.ok) throw new Error(body.detail || 'Authentication failed.')
      localStorage.setItem('cb_token',body.token)
      localStorage.removeItem('cb_profile')
      setAuthUser(body.user)
      setProfile({name:body.user.name,email:body.user.email})
      setAuthMode('profile')
      setAuthForm({name:'',email:'',password:''})
      setAuthError('')
    } catch(e:any) { setAuthError(e.message || 'Authentication failed.') }
  }

  async function saveProfile(next:Profile) {
    const token = localStorage.getItem('cb_token')
    if(!token) { setAuthError('Please sign in to update your profile.'); return }
    try {
      const res = await fetch(`${API}/api/auth/profile`,{method:'PUT',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify(next)})
      const body = await res.json()
      if(!res.ok) throw new Error(body.detail || 'Could not save profile.')
      setProfile({name:body.user.name,email:body.user.email}); setAuthUser(body.user)
    } catch(e:any) { setAuthError(e.message || 'Could not save profile.') }
  }

  async function logout() {
    const token = localStorage.getItem('cb_token')
    try {
      if(token) await fetch(`${API}/api/auth/logout`,{method:'POST',headers:{Authorization:`Bearer ${token}`}})
    } catch {}
    finally {
      localStorage.removeItem('cb_token')
      localStorage.removeItem('cb_profile')
      setAuthUser(null)
      setProfile({name:'Guest User',email:''})
      setAuthForm({name:'',email:'',password:''})
      setAuthError('')
      setAuthMode('login')
      setAuthOpen(false)
      setAccountOpen(false)
    }
  }

  async function openFileSummary(path:string) {
    setSelectedFile(path); setFileSummary(null); setFileLoading(true)
    try {
      const res = await fetch(`${API}/api/files/summary`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})})
      const body = await res.json();
      if(!res.ok) throw new Error(body.detail || 'Could not summarize file.')
      setFileSummary(body)
    } catch(e:any) { setFileSummary({error:e.message || 'Could not summarize file.'}) }
    finally { setFileLoading(false) }
  }

  async function analyze() {
    if (!repoUrl.trim()) return setError('Paste a public GitHub repository URL first.')
    setLoading(true); setError(''); setData(null); setChat([]); setImpact(null)
    try {
      const res = await fetch(`${API}/api/repos/analyze`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:repoUrl.trim()})})
      const body = await res.json()
      if (!res.ok) throw new Error(body.detail || 'Repository analysis failed.')
      setData(body)
      setImpactTarget(body.analysis.entrypoints?.[0] || body.repo.name)
      setActive('overview')
    } catch (e:any) { setError(e.message || 'Could not analyze repository.') }
    finally { setLoading(false) }
  }

  async function ask(question = query) {
    const q = question.trim(); if (!q || !data || chatLoading) return
    setQuery('')
    setChat(c=>[...c,{role:'user',text:q}])
    setChatLoading(true)
    try {
      const token = localStorage.getItem('cb_token')
      const res = await fetch(`${API}/api/chat`,{method:'POST',headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},body:JSON.stringify({question:q,history:chat.map(m=>({role:m.role,text:m.text}))})})
      const body = await res.json()
      if (!res.ok) throw new Error(body.detail || 'Chat failed.')
      setChat(c=>[...c,{role:'assistant',text:body.answer,refs:body.references}])
    } catch(e:any) {
      setChat(c=>[...c,{role:'assistant',text:e.message || 'Chat failed.'}])
    } finally { setChatLoading(false) }
  }

  async function runImpact() {
    if (!data || !impactTarget.trim()) return
    const res = await fetch(`${API}/api/impact`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target:impactTarget})})
    const body = await res.json(); if (res.ok) setImpact(body)
  }

  const stats = data ? [
    [data.indexed_files.toString(),'Files indexed',FileCode2],
    [data.analysis.graph_nodes.toString(),'Graph nodes',Network],
    [data.analysis.relationships.toString(),'Relationships',GitBranch],
    [data.total_lines.toLocaleString(),'Lines observed',Layers3],
  ] as const : []

  return <main className={`shell ${settings.compact?'compact':''}`}>
    <header className="topbar glass">
      <div className="brand-wrap"><div className="brand-mark"><Network size={17}/></div><div><div className="brand">Codebase Intelligence</div><div className="brand-sub">Repository understanding, visualized.</div></div></div>
      <div className="top-actions">
        <button className="ghost-btn" onClick={()=>setCmdOpen(true)}><Command size={15}/><span>⌘K</span></button>
        <button className="ghost-icon" onClick={()=>setAccountOpen(v=>!v)} aria-label="Account"><User size={17}/></button>
        {accountOpen && <AccountMenu profile={profile} signedIn={!!authUser} onClose={()=>setAccountOpen(false)} onLogin={()=>{setAccountOpen(false);setAuthError('');setAuthMode(authUser?'profile':'login');setAuthOpen(true)}} onSignup={()=>{setAccountOpen(false);setAuthError('');setAuthMode('signup');setAuthOpen(true)}} onSettings={()=>{setAccountOpen(false);setAuthError('');setAuthMode('profile');setAuthOpen(true)}} onLogout={logout}/> }
      </div>
    </header>

    <section className={`hero glass ${data ? 'hero-compact':''}`}>
      <div className="hero-copy">
        <div className="eyebrow"><span className="status-led"/> {loading ? 'Analyzing repository' : data ? 'Repository analyzed' : 'Ready to analyze'}</div>
        <h1>Understand any codebase.<br/><span>See the system behind it.</span></h1>
        <p>Paste any public GitHub repository and turn real source files into architecture maps, dependency intelligence, impact analysis, system flows, documentation and grounded AI answers.</p>
        <div className="repo-bar"><Github size={18}/><input value={repoUrl} onChange={e=>setRepoUrl(e.target.value)} onKeyDown={e=>{if(e.key==='Enter') analyze()}} placeholder="https://github.com/owner/repository" aria-label="GitHub repository"/><button className="primary-btn" onClick={analyze} disabled={loading}>{loading?<Loader2 className="spin" size={16}/>:<Zap size={16}/>} {loading?'Analyzing…':'Analyze repository'}</button></div>
        <div className="hero-meta"><span><ShieldCheck size={14}/> Public repo ingestion</span><span><GitBranch size={14}/> Import-aware graph</span><span><Sparkles size={14}/> Embeddings + retrieval</span></div>
        {error && <div className="error-banner"><AlertTriangle size={14}/>{error}</div>}
      </div>
      <div className="hero-visual">
        <ArchitectureScene nodes={data?.graph.nodes.slice(0,16) || []} edges={data?.graph.edges || []} interactive={!!data} showLabels={false} />
        <div className="hero-label"><span>3D topology</span><strong>{data ? `${data.graph.layers?.length || 0} modules mapped` : 'Ready for any repository'}</strong></div>
        <div className="hero-foot"><span>{data ? `${data.indexed_chunks} chunks indexed` : 'No hardcoded project data'}</span></div>
      </div>
    </section>

    {!data ? <EmptyState/> : <div className="workspace">
      <aside className="sidebar glass">
        <div className="side-top"><button className="collapse-btn"><PanelLeft size={15}/></button><span>WORKSPACE</span></div>
        <div className="repo-mini"><div className="repo-avatar"><Code2 size={17}/></div><div><strong>{data.repo.name}</strong><span>{data.repo.branch} · {data.indexed_files} indexed</span></div></div>
        <nav>{features.map(([id,label,Icon])=><button key={id} className={`nav-item ${active===id?'active':''}`} onClick={()=>setActive(id)}><Icon size={16}/><span>{label}</span>{active===id&&<ChevronRight size={15} className="nav-arrow"/>}</button>)}</nav>
        <div className="side-footer"><div className="security-chip"><CircleDot size={12}/> Analysis engine online</div><div className="side-footer-row"><TerminalSquare size={14}/><span>{data.analysis.top_language}</span><span>•</span><span>{data.technologies.slice(0,2).join(' · ') || 'Stack scanning active'}</span></div></div>
      </aside>
      <section className="content">
        <div className="content-head"><div><div className="crumb">{data.repo.full_name} <span>/</span> {activeLabel}</div><h2>{activeLabel}</h2></div><button className="soft-btn" onClick={()=>setActive('chat')}><Search size={15}/> Ask the codebase</button></div>
        <div className="view-enter">
          {active==='overview'&&<OverviewView data={data} stats={stats}/>} {active==='architecture'&&<ArchitectureView data={data} openFile={openFileSummary}/>} {active==='graph'&&<GraphView data={data} openFile={openFileSummary}/>} {active==='dependencies'&&<DependenciesView data={data}/>} {active==='impact'&&<ImpactView target={impactTarget} setTarget={setImpactTarget} impact={impact} run={runImpact}/>} {active==='flows'&&<FlowsView data={data} openFile={openFileSummary}/>} {active==='chat'&&<ChatView chat={chat} query={query} setQuery={setQuery} send={ask} repo={data.repo.full_name} loading={chatLoading}/>} {active==='docs'&&<DocsView data={data} openFile={openFileSummary}/>} {active==='changes'&&<ChangesView data={data}/>} 
        </div>
      </section>
    </div>}

    {cmdOpen&&<div className="cmd-overlay" onClick={()=>setCmdOpen(false)}><div className="command-modal glass" onClick={e=>e.stopPropagation()}><div className="command-input"><Command size={17}/><input autoFocus placeholder="Jump to a workspace feature…" onKeyDown={e=>{if(e.key==='Escape')setCmdOpen(false)}}/></div><div className="command-list">{features.map(([id,label,Icon])=><button key={id} onClick={()=>{if(data)setActive(id);setCmdOpen(false)}}><Icon size={15}/>{label}<span>↵</span></button>)}</div></div></div>}
    {authOpen&&<AuthModal mode={authMode} setMode={setAuthMode} user={authUser} form={authForm} setForm={setAuthForm} error={authError} settings={settings} setSettings={setSettings} profile={profile} setProfile={setProfile} onSaveProfile={saveProfile} onSubmit={submitAuth} onLogout={logout} onClose={()=>setAuthOpen(false)}/>}
    {selectedFile&&<FileSummaryModal path={selectedFile} summary={fileSummary} loading={fileLoading} onClose={()=>{setSelectedFile(null);setFileSummary(null)}}/>}
  </main>
}

function EmptyState(){return <section className="empty-state glass"><div className="empty-visual"><div className="poly-orbit"><div className="poly-core"><Network size={30}/></div><span>INGEST</span><span>PARSE</span><span>INDEX</span><span>UNDERSTAND</span></div></div><div className="empty-copy"><div className="eyebrow">CODEBASE INTELLIGENCE</div><h2>Your repository is the dataset.</h2><p>Drop in any public GitHub URL. The platform fetches real files, detects the stack, builds repository-local relationships, indexes code for retrieval and drives every workspace view from the same analysis.</p><div className="empty-points"><span><CheckCircle2 size={14}/> Real repository data</span><span><CheckCircle2 size={14}/> No hardcoded project</span><span><CheckCircle2 size={14}/> Source-grounded answers</span><span><CheckCircle2 size={14}/> 3D topology + readable maps</span></div></div></section>}

function OverviewView({data,stats}:{data:Result;stats:any[]}){return <>
  <div className="stat-grid">{stats.map(([value,label,Icon])=><div className="stat-card glass" key={label}><div className="stat-icon"><Icon size={15}/></div><strong>{value}</strong><span>{label}</span></div>)}</div>
  <div className="grid-two">
    <Panel title="Repository profile"><div className="repo-profile"><div><span>Repository</span><strong>{data.repo.full_name}</strong></div><div><span>Branch</span><code>{data.repo.branch}</code></div><div><span>Description</span><strong>{data.repo.description}</strong></div><div><span>GitHub</span><a href={data.repo.url} target="_blank" rel="noreferrer"><ExternalLink size={13}/> Open repository</a></div><div><span>Topics</span><div className="tag-row">{data.repo.topics.length?data.repo.topics.slice(0,8).map(t=><span className="tag" key={t}>{t}</span>):<em>None declared</em>}</div></div><div><span>Recent commits</span><strong>{data.commits.length}</strong></div></div></Panel>
    <Panel title="Detected technology stack"><div className="stack-grid">{data.technologies.length?data.technologies.map(t=><div className="stack-chip" key={t}><span>{t.slice(0,2).toUpperCase()}</span>{t}</div>):<em>No strong framework signal detected</em>}</div></Panel>
  </div>
  <div className="grid-two">
    <Panel title="Language mix"><div className="lang-list">{data.languages.slice(0,8).map(l=><div className="lang-row" key={l.name}><div><strong>{l.name}</strong><span>{l.files} files</span></div><div className="lang-track"><i style={{width:`${Math.min(100,l.share)}%`}}/></div><b>{l.share}%</b></div>)}</div></Panel>
    <Panel title="Analyzer notes"><div className="insight-list">{data.analysis.architecture_notes.map(n=><div className="insight" key={n}><div className="insight-icon"><BrainCircuit size={15}/></div><p>{n}</p></div>)}</div></Panel>
  </div>
</>}

function ArchitectureView({data,openFile}:{data:Result;openFile:(path:string)=>void}){return <div className="architecture-layout"><Panel title="3D repository topology"><div className="architecture-canvas"><ArchitectureScene nodes={data.graph.nodes.slice(0,32)} edges={data.graph.edges} interactive showLabels/></div><div className="legend-row"><span><i className="legend-dot green"/>Module / connected node</span><span><i className="legend-dot peach"/>High-degree node</span><span><i className="legend-line"/>Repository-local import</span></div></Panel><Panel title="How to read this map"><div className="architecture-explainer"><p><strong>Center</strong> = highly connected files. <strong>Outer ring</strong> = supporting files. Each visible line is a detected repository-local relationship.</p><p><strong>Click a file below</strong> to open an AI-generated explanation of its responsibility, declarations, integrations and data flow.</p></div><div className="module-list">{(data.graph.layers || data.analysis.modules.slice(0,16).map((m,i)=>({id:String(i),name:m.name,files:m.files,node_ids:[]}))).map(m=><div className="module-row" key={m.id}><div><strong>{m.name}</strong><span>{m.files} indexed files</span></div><div className="module-actions">{(m.node_ids||[]).slice(0,2).map(id=>{const n=data.graph.nodes.find(x=>x.id===id);return n?<button className="mini-file-link" key={id} onClick={()=>openFile(n.path)}><FileCode2 size={13}/>{n.label}</button>:null})}</div><ChevronRight size={15}/></div>)}</div></Panel></div>}

function GraphView({data,openFile}:{data:Result;openFile:(path:string)=>void}){return <><div className="panel glass graph-panel"><div className="panel-title"><div><span className="kicker">KNOWLEDGE GRAPH</span><h3>{data.graph.nodes.length} nodes · {data.graph.edges.length} relationships</h3></div><span className="pill">Repository-local</span></div><div className="graph-grid">{(data.graph.layers||[]).slice(0,8).map((layer,idx)=><div className="graph-group" key={layer.id}><div className="group-head"><span>{idx+1}</span><strong>{layer.name}</strong><em>{layer.files} files</em></div><div className="group-nodes">{layer.node_ids.slice(0,8).map(id=>{const n=data.graph.nodes.find(x=>x.id===id); return n?<div className="group-node" key={id} title={n.path}><FileCode2 size={13}/><span>{n.label}</span><small>{n.language}</small></div>:null})}</div></div>)}</div></div><Panel title="Highest-connectivity files"><div className="file-list">{[...data.graph.nodes].sort((a,b)=>(b.degree||0)-(a.degree||0)).slice(0,14).map(n=><button className="file-row file-row-button" key={n.id} onClick={()=>openFile(n.path)}><FileCode2 size={14}/><code>{n.path}</code><span>{n.degree||0} links <ChevronRight size={13}/></span></button>)}</div></Panel></>}

function DependenciesView({data}:{data:Result}){return <div className="panel glass"><div className="panel-title"><div><span className="kicker">DEPENDENCY EXPLORER</span><h3>Real import relationships discovered in the repository</h3></div><span className="pill">{data.graph.edges.length} edges</span></div><div className="dependency-table"><div className="table-head"><span>Source</span><span>Target</span><span>Kind</span><span>Language</span></div>{data.graph.edges.slice(0,60).map((e,i)=>{const s=data.graph.nodes.find(n=>n.id===e.source),t=data.graph.nodes.find(n=>n.id===e.target);return <div className="table-row" key={i}><span><GitBranch size={13}/>{s?.path}</span><span>{t?.path}</span><span><i className="status-dot"/>{e.kind}</span><span>{s?.language}</span></div>})}</div></div>}

function ImpactView({target,setTarget,impact,run}:{target:string;setTarget:(v:string)=>void;impact:any;run:()=>void}){return <div className="grid-two"><Panel title="Impact query"><div className="impact-input"><Search size={15}/><input value={target} onChange={e=>setTarget(e.target.value)} placeholder="file, folder, or symbol e.g. UserService"/><button className="primary-mini" onClick={run}>Analyze</button></div>{impact&&<><div className="impact-score"><div><span>Estimated change risk</span><strong>{impact.level}</strong></div><div className="score-ring"><span>{impact.score}</span><small>/100</small></div></div><div className="reason-list">{impact.affected.map((a:any)=><div className="reason-item" key={`${a.file}-${a.reason}`}><div className="reason-badge">!</div><div><strong>{a.risk} · {a.file}</strong><p>{a.reason}</p></div></div>)}</div></>}</Panel><Panel title="Method"><div className="insight-list"><div className="insight"><div className="insight-icon"><GitBranch size={15}/></div><p>Matches the target against real repository paths and indexed source content.</p></div><div className="insight"><div className="insight-icon"><Network size={15}/></div><p>Traces detected repository-local imports to find likely affected files.</p></div><div className="insight"><div className="insight-icon"><CircleDot size={15}/></div><p>Risk is heuristic, so runtime contracts and external services still need review.</p></div></div></Panel></div>}

function FlowsView({data,openFile}:{data:Result;openFile:(path:string)=>void}){return <div className="flow-stack">{data.flows.map(flow=><Panel title={flow.name} key={flow.name}><div className="flow-explanation">{flow.explanation || 'This flow is inferred from repository-local source relationships.'}</div><div className="flow-track">{flow.steps.map((s,i)=><div className="flow-step" key={s.id}><div className="flow-number">{s.id}</div><button className="flow-file" onClick={()=>openFile(s.detail)}><strong>{s.label}</strong><p>{s.detail}</p><span>Open AI summary <ChevronRight size={13}/></span></button>{i<flow.steps.length-1&&<ArrowRight className="flow-arrow" size={15}/>}</div>)}</div></Panel>)}</div>}

function ChatView({chat,query,setQuery,send,repo,loading}:{chat:Message[];query:string;setQuery:(v:string)=>void;send:(q?:string)=>void;repo:string;loading:boolean}){return <div className="chat-layout"><div className="panel glass chat-panel"><div className="chat-title"><div><strong>AI Codebase Chat</strong><span>Grounded on {repo}</span></div><span className="ai-pill"><CircleDot size={11}/> {loading?'retrieving…':'retrieval online'}</span></div><div className="chat-scroll">{chat.length===0?<div className="chat-empty"><Bot size={26}/><strong>Ask about this repository</strong><span>Questions are retrieved against the currently analyzed codebase.</span></div>:chat.map((m,i)=><div className={`message ${m.role}`} key={i}><div className="avatar-mini">{m.role==='assistant'?'AI':'YOU'}</div><div className="bubble"><span className="message-label">{m.role==='assistant'?'CODEBASE AI':'YOU'}</span><p>{m.text}</p>{m.refs&&<div className="refs">{m.refs.map(r=><span key={`${r.path}-${r.chunk}`}><FileCode2 size={10}/>{r.path} · chunk {r.chunk}</span>)}</div>}</div></div>)}{loading&&<div className="message assistant"><div className="avatar-mini">AI</div><div className="bubble"><p>Searching the indexed codebase…</p></div></div>}</div><div className="chat-compose"><input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')send()}} placeholder="Ask about architecture, code, dependencies…"/><button className="primary-mini icon-only" onClick={()=>send()} disabled={loading}><Send size={15}/></button></div></div><Panel title="Starter prompts"><button className="prompt-btn" onClick={()=>send('How does the application start?')}>How does the application start?</button><button className="prompt-btn" onClick={()=>send('What technologies are used and where?')}>What technologies are used?</button><button className="prompt-btn" onClick={()=>send('Where are the main API entrypoints?')}>Where are the API entrypoints?</button><button className="prompt-btn" onClick={()=>send('What depends on the main application module?')}>What depends on the main application module?</button></Panel></div>}

function DocsView({data,openFile}:{data:Result;openFile:(path:string)=>void}){return <div className="grid-two"><Panel title={data.docs.title}><div className="doc-summary"><BookOpen size={15}/><p>{data.docs.summary}</p></div><div className="doc-cards">{data.docs.sections.map(s=><div className="doc-card" key={s.title}><div className="doc-icon"><FileCode2 size={15}/></div><div><strong>{s.title}</strong><span>{s.body.slice(0,220)}</span></div></div>)}</div></Panel><Panel title="Repository reading list"><div className="file-list">{data.analysis.docs.length?data.analysis.docs.map(p=><button className="file-row file-row-button" key={p} onClick={()=>openFile(p)}><BookOpen size={14}/><code>{p}</code><ChevronRight size={13}/></button>):<div className="empty-inline">No markdown documentation files were detected.</div>}</div></Panel></div>}

function ChangesView({data}:{data:Result}){const c=data.changes;return <div className="panel glass"><div className="compare-head"><div><span>Previous</span><code>{c.from?.sha || '—'}</code></div><GitCompareArrows size={17}/><div><span>Latest</span><code>{c.to?.sha || '—'}</code></div></div><div className="change-list">{c.files.length===0?<div className="chat-empty"><GitCompareArrows size={20}/><strong>No two-commit comparison available</strong><span>GitHub may not expose enough recent history for this repository.</span></div>:c.files.map((f:any)=><div className="change-row" key={f.filename}><div className={`change-badge ${f.status}`}>{f.status==='added'?'+':f.status==='removed'?'−':'~'}</div><div><strong>{f.filename}</strong><p>{f.additions} additions · {f.deletions} deletions · {f.changes} changed lines</p></div><span className="change-meta">{f.status}</span></div>)}</div></div>}

function Panel({title,children}:{title:string;children:ReactNode}){return <div className="panel glass"><div className="panel-title"><div><span className="kicker">{title}</span></div></div>{children}</div>}

function AccountMenu({profile,signedIn,onClose,onLogin,onSignup,onSettings,onLogout}:{profile:Profile;signedIn:boolean;onClose:()=>void;onLogin:()=>void;onSignup:()=>void;onSettings:()=>void;onLogout:()=>void}){return <div className="account-menu glass"><div className="account-head"><div className="account-avatar">{profile.name.slice(0,2).toUpperCase()}</div><div><strong>{profile.name}</strong><span>{profile.email||'Guest workspace'}</span></div><div className={`account-status ${signedIn?'online':''}`}>{signedIn?'LIVE':'GUEST'}</div></div>{signedIn?<><button onClick={onSettings}><User size={14}/> Profile & settings</button><button onClick={onLogout}><LogIn size={14}/> Sign out</button></>:<><button onClick={onLogin}><LogIn size={14}/> Sign in</button><button onClick={onSignup}><User size={14}/> Create account</button></>}<button onClick={onClose}><X size={14}/> Close</button></div>}

function AuthModal({mode,setMode,user,form,setForm,error,settings,setSettings,profile,setProfile,onSaveProfile,onSubmit,onLogout,onClose}:{mode:'login'|'signup'|'profile';setMode:(v:'login'|'signup'|'profile')=>void;user:{id:number;name:string;email:string}|null;form:{name:string;email:string;password:string};setForm:(v:{name:string;email:string;password:string})=>void;error:string;settings:Settings;setSettings:(v:Settings)=>void;profile:Profile;setProfile:(v:Profile)=>void;onSaveProfile:(v:Profile)=>void;onSubmit:()=>void;onLogout:()=>void;onClose:()=>void}){const [name,setName]=useState(profile.name);const [email,setEmail]=useState(profile.email);return <div className="modal-backdrop" onClick={onClose}><div className="auth-modal glass" onClick={e=>e.stopPropagation()}>{mode==='profile'?<><div className="modal-title"><div><span className="kicker">WORKSPACE ACCOUNT</span><h3>Your profile</h3></div><button className="ghost-icon" onClick={onClose}><X size={15}/></button></div><div className="profile-hero"><div className="profile-avatar-lg">{(profile.name||'GU').slice(0,2).toUpperCase()}</div><div><strong>{profile.name}</strong><span>{profile.email}</span><small>Authenticated workspace</small></div></div><div className="profile-form"><label>Display name<input value={name} onChange={e=>setName(e.target.value)} placeholder="Your name"/></label><label>Email<input value={email} readOnly aria-readonly="true" placeholder="you@example.com"/></label></div><div className="settings-list"><div className="setting-row"><div><strong>Reduce motion</strong><span>Keep only useful loading and state transitions.</span></div><button className={`toggle ${settings.reduceMotion?'on':''}`} onClick={()=>setSettings({...settings,reduceMotion:!settings.reduceMotion})}><i/></button></div><div className="setting-row"><div><strong>Compact workspace</strong><span>Use tighter spacing for dense repositories.</span></div><button className={`toggle ${settings.compact?'on':''}`} onClick={()=>setSettings({...settings,compact:!settings.compact})}><i/></button></div></div><div className="auth-actions"><button className="primary-btn" onClick={async()=>{const next={name:name.trim()||'Guest User',email:email.trim()};await onSaveProfile(next);onClose()}}>Save profile</button><button className="soft-btn" onClick={onLogout}>Sign out</button></div></>:<><div className="modal-title"><div><span className="kicker">{mode==='signup'?'JOIN THE WORKSPACE':'WELCOME BACK'}</span><h3>{mode==='signup'?'Create your account':'Sign in to your workspace'}</h3></div><button className="ghost-icon" onClick={onClose}><X size={15}/></button></div><div className="auth-tabs"><button className={mode==='login'?'active':''} onClick={()=>setMode('login')}>Sign in</button><button className={mode==='signup'?'active':''} onClick={()=>setMode('signup')}>Sign up</button></div><div className="auth-form">{mode==='signup'&&<label>Display name<input value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="Prayag Singh"/></label>}<label>Email<input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} placeholder="you@example.com"/></label><label>Password<input type="password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})} placeholder={mode==='signup'?'At least 8 characters':'Your password'} onKeyDown={e=>{if(e.key==='Enter')onSubmit()}}/></label>{error&&<div className="auth-error"><AlertTriangle size={14}/>{error}</div>}<button className="primary-btn auth-submit" onClick={onSubmit}>{mode==='signup'?'Create account':'Sign in'} <ArrowRight size={15}/></button></div><p className="auth-note">You can still analyze public repositories as a guest. An account keeps your workspace identity separate from repository data.</p></>}</div></div>}

function FileSummaryModal({path,summary,loading,onClose}:{path:string;summary:any;loading:boolean;onClose:()=>void}){return <div className="modal-backdrop" onClick={onClose}><div className="file-modal glass" onClick={e=>e.stopPropagation()}><div className="modal-title"><div><span className="kicker">FILE INSIGHT</span><h3>{path}</h3></div><button className="ghost-icon" onClick={onClose}><X size={15}/></button></div>{loading?<div className="file-loading"><Loader2 className="spin" size={25}/><strong>Generating file summary…</strong><span>Reading the actual repository content and extracting responsibilities.</span></div>:summary?.error?<div className="auth-error"><AlertTriangle size={14}/>{summary.error}</div>:<div className="file-summary"><div className="summary-hero"><div className="file-icon-large"><FileCode2 size={22}/></div><div><strong>{summary?.responsibility || 'Repository file'}</strong><span>{summary?.language || 'Source'} · {summary?.lines || 0} lines</span></div></div><div className="summary-section"><span>SUMMARY</span><p>{summary?.summary}</p></div><div className="summary-section"><span>WHAT THIS FILE DOES</span><ul>{(summary?.highlights||[]).map((h:string,i:number)=><li key={i}>{h}</li>)}</ul></div></div>}</div></div>}
