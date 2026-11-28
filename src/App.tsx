import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { createUserWithEmailAndPassword, GoogleAuthProvider, sendEmailVerification, signInWithEmailAndPassword, signInWithPopup, signOut as firebaseSignOut } from "firebase/auth";
import { AnimatePresence, motion } from "motion/react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Activity, Check, ChevronDown, Circle, Clock3, CreditCard, Eye, EyeOff, FolderKanban, GitBranch, Globe2, HeartPulse, History, Layers3, MessageSquare, PanelLeftClose, Plus, Search, Send, UserPlus, X, Zap } from "lucide-react";
import { Page } from "./components/Page";
import { Cursor } from "./components/Cursor";
import { LandingSections } from "./components/LandingSections";
import { ResultsSection } from "./components/ResultsSection";
import { FeatureAccordion } from "./components/FeatureAccordion";
import { SmoothLanding } from "./components/SmoothLanding";
import { CallChip, type CallChipStatus } from "./components/CallChip";
import { ThoughtLine } from "./components/ThoughtLine";
import { api, ApiError, streamAssistant, type AppDetail, type AppRecord, type Branch, type ChatTurn, type Exploration, type PassportRecord, type ProjectContext, type Session, type SystemStatus } from "./lib/api";
import { firebaseAuth } from "./lib/firebase";

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const authMode: "signup" | "signin" = location.pathname === "/signin" ? "signin" : "signup";
  const dashboardPage = dashboardPageFromPath(location.pathname);
  const [showPassword, setShowPassword] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [authError, setAuthError] = useState("");
  const [authBusy, setAuthBusy] = useState(false);

  useEffect(()=>{let currentAsset=document.querySelector<HTMLScriptElement>('script[type="module"][src]')?.src??"";const check=async()=>{try{const response=await fetch(`/?update=${Date.now()}`,{cache:"no-store"});const html=await response.text();const nextAsset=new DOMParser().parseFromString(html,"text/html").querySelector<HTMLScriptElement>('script[type="module"][src]')?.src??"";if(currentAsset&&nextAsset&&new URL(nextAsset,window.location.origin).href!==new URL(currentAsset,window.location.origin).href)window.location.reload();else if(nextAsset)currentAsset=new URL(nextAsset,window.location.origin).href}catch{}};const timer=window.setInterval(()=>void check(),20000);const visible=()=>{if(document.visibilityState==="visible")void check()};document.addEventListener("visibilitychange",visible);return()=>{window.clearInterval(timer);document.removeEventListener("visibilitychange",visible)}},[]);

  const submitAuth = async (event: FormEvent<HTMLFormElement>, mode: "signin" | "signup") => {
    event.preventDefault(); setAuthBusy(true); setAuthError("");
    const form = new FormData(event.currentTarget);
    try {
      const email = String(form.get("email") || "");
      const password = String(form.get("password") || "");
      const workspaceName = `${String(form.get("first_name") || "Multiverse")} Workspace`;
      if (firebaseAuth) {
        const credential = mode === "signin"
          ? await signInWithEmailAndPassword(firebaseAuth, email, password)
          : await createUserWithEmailAndPassword(firebaseAuth, email, password);
        if (!credential.user.emailVerified) {
          await sendEmailVerification(credential.user);
          setAuthError("Verify your email using the link we sent, then sign in again.");
          return;
        }
        await api.firebaseSession({ id_token: await credential.user.getIdToken(), workspace_name: workspaceName });
      } else if (mode === "signin") {
        await api.login({ email, password });
      } else {
        await api.signup({ email, password, workspace_name: workspaceName });
      }
      setSession(await api.me()); navigate("/dashboard/overview", { replace: true });
    } catch (error) { setAuthError(error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Authentication failed."); }
    finally { setAuthBusy(false); }
  };

  const signInWithGoogle = async () => {
    if (!firebaseAuth) { setAuthError("Firebase sign-in is not configured for this site yet."); return; }
    setAuthBusy(true); setAuthError("");
    try {
      const credential = await signInWithPopup(firebaseAuth, new GoogleAuthProvider());
      await api.firebaseSession({ id_token: await credential.user.getIdToken(), workspace_name: "Multiverse Workspace" });
      setSession(await api.me()); navigate("/dashboard/overview", { replace: true });
    } catch (error) { setAuthError(error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Google sign-in failed."); }
    finally { setAuthBusy(false); }
  };

  useEffect(()=>{if(!dashboardPage||session)return;let current=true;api.me().then(value=>{if(current)setSession(value)}).catch(()=>{if(current)navigate("/signin",{replace:true})});return()=>{current=false}},[dashboardPage,navigate,session]);

  if (location.pathname.startsWith("/dashboard") && !dashboardPage) return <Navigate to="/dashboard/overview" replace/>;
  if (dashboardPage) return <Dashboard activePage={dashboardPage} onSelect={(page)=>navigate(dashboardPath(page))} session={session} onSignOut={async () => { await api.logout().catch(()=>undefined); if(firebaseAuth)await firebaseSignOut(firebaseAuth).catch(()=>undefined); setSession(null); navigate("/signin", { replace: true }); }} />;

  if (location.pathname === "/") return <SmoothLanding><Page onGetStarted={() => navigate("/signup")} /><ResultsSection/><FeatureAccordion/><LandingSections/><Cursor /></SmoothLanding>;

  if (location.pathname !== "/signin" && location.pathname !== "/signup") return <Navigate to="/" replace/>;

  return (
    <main className="flex min-h-screen w-full bg-black p-2 text-white selection:bg-white/30 transition-all duration-500 lg:h-screen lg:overflow-hidden lg:p-4">
      <GlobalErrorToasts/><Toast message={authError} onClose={()=>setAuthError("")}/>
      <section className="relative hidden h-full w-[52%] flex-col items-center justify-end overflow-hidden rounded-3xl px-12 pb-32 shadow-2xl lg:flex">
        <video autoPlay muted loop playsInline className="absolute inset-0 h-full w-full object-cover">
          <source src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260506_081238_406ed0e3-5d83-436e-a512-0bbff7ec5b95.mp4" type="video/mp4" />
        </video>
      </section>

      <section className="relative flex min-h-[760px] flex-1 flex-col items-center justify-center overflow-hidden px-4 py-12 sm:px-12 lg:min-h-0 lg:px-10 lg:py-6 xl:px-16">
        {authMode === "signin" ? (
          <motion.div key="signin" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.8, ease: "easeOut" }} className="w-full max-w-xl space-y-8 sm:space-y-10 lg:space-y-6">
            <header className="space-y-2">
              <div className="mb-8 flex items-center gap-2 lg:hidden"><Circle className="fill-white" size={18}/><span className="font-semibold">Multiverse</span></div>
              <h1 className="text-3xl font-medium tracking-tight">Welcome Back</h1>
              <p className="text-sm text-white/40">Enter your details to access your workspace.</p>
            </header>
            <div className="grid grid-cols-1 gap-4">
              <SocialButton icon={<span className="font-semibold">G</span>} label="Continue with Google" onClick={()=>void signInWithGoogle()} disabled={authBusy}/>
            </div>
            <div className="relative flex items-center"><div className="w-full border-t border-white/10"/><span className="absolute left-1/2 -translate-x-1/2 bg-black px-4 text-xs font-medium uppercase tracking-widest text-white/40">Or</span></div>
            <form className="space-y-5" onSubmit={(event) => void submitAuth(event,"signin")}>
              <InputGroup name="email" label="Email" placeholder="you@company.com" type="email" />
              <div className="space-y-2">
                <div className="flex items-center justify-between"><label htmlFor="signin-password" className="block text-sm font-medium text-white">Password</label><button type="button" className="text-xs text-white/40 transition hover:text-white">Forgot password?</button></div>
                <div className="relative">
                  <input id="signin-password" name="password" required minLength={8} type={showPassword ? "text" : "password"} placeholder="Enter your password" className="h-11 w-full rounded-xl border-none bg-brand-gray px-4 pr-12 text-white outline-none placeholder:text-white/20 focus:ring-2 focus:ring-white/20" />
                  <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Hide password" : "Show password"} className="absolute right-4 top-1/2 -translate-y-1/2 text-white/35 transition hover:text-white">{showPassword ? <EyeOff size={18}/> : <Eye size={18}/>}</button>
                </div>
              </div>
              <button disabled={authBusy} type="submit" className="mt-4 h-14 w-full rounded-xl bg-white font-semibold text-black transition hover:bg-white/90 active:scale-[0.98] disabled:opacity-50">{authBusy?"Connecting…":"Sign In"}</button>
            </form>
            <p className="text-center text-sm text-white/40">New to Multiverse? <button type="button" onClick={() => navigate("/signup")} className="font-medium text-white underline-offset-4 hover:underline">Create an account</button></p>
          </motion.div>
        ) : (
        <motion.div key="signup" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.8, ease: "easeOut" }} className="w-full max-w-xl space-y-7 lg:space-y-5">
          <header className="space-y-2">
            <div className="mb-8 flex items-center gap-2 lg:hidden"><Circle className="fill-white" size={18}/><span className="font-semibold">Multiverse</span></div>
            <h1 className="text-3xl font-medium tracking-tight">Create New Profile</h1>
            <p className="text-sm text-white/40">Input your basic details to begin the journey.</p>
          </header>
          <div className="grid grid-cols-1 gap-4">
            <SocialButton icon={<span className="font-semibold">G</span>} label="Continue with Google" onClick={()=>void signInWithGoogle()} disabled={authBusy}/>
          </div>
          <div className="relative flex items-center"><div className="w-full border-t border-white/10"/><span className="absolute left-1/2 -translate-x-1/2 bg-black px-4 text-xs font-medium uppercase tracking-widest text-white/40">Or</span></div>
          <form className="space-y-5" onSubmit={(event) => void submitAuth(event,"signup")}>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <InputGroup name="first_name" label="First Name" placeholder="Mila" type="text" />
              <InputGroup name="last_name" label="Last Name" placeholder="Quelm" type="text" />
            </div>
            <InputGroup name="email" label="Email" placeholder="you@company.com" type="email" />
            <div className="space-y-2">
              <label htmlFor="signup-password" className="block text-sm font-medium text-white">Password</label>
              <div className="relative">
                <input id="signup-password" name="password" required minLength={8} type={showPassword ? "text" : "password"} placeholder="Enter your password" className="h-11 w-full rounded-xl border-none bg-brand-gray px-4 pr-12 text-white outline-none placeholder:text-white/20 focus:ring-2 focus:ring-white/20" />
                <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Hide password" : "Show password"} className="absolute right-4 top-1/2 -translate-y-1/2 text-white/35 transition hover:text-white">
                  {showPassword ? <EyeOff size={18}/> : <Eye size={18}/>} 
                </button>
              </div>
              <p className="text-xs text-white/30">Requires at least 8 symbols.</p>
            </div>
            <button disabled={authBusy} type="submit" className="mt-4 h-14 w-full rounded-xl bg-white font-semibold text-black transition hover:bg-white/90 active:scale-[0.98] disabled:opacity-50">{authBusy?"Creating workspace…":"Create Account"}</button>
          </form>
          <p className="text-center text-sm text-white/40">Member of the team? <button type="button" onClick={() => navigate("/signin")} className="font-medium text-white underline-offset-4 hover:underline">Log in</button></p>
        </motion.div>
        )}
      </section>
    </main>
  );
}

type DashboardPage = "Overview" | "Applications" | "Verse AI" | "Atlas" | "Verse" | "Passports" | "Runtime" | "Account";

const dashboardRoutes: Record<DashboardPage,string> = { Overview:"overview", Applications:"applications", "Verse AI":"assistant", Atlas:"atlas", Verse:"verse", Passports:"passports", Runtime:"runtime", Account:"account" };
const dashboardPath = (page: DashboardPage) => `/dashboard/${dashboardRoutes[page]}`;
function dashboardPageFromPath(pathname:string):DashboardPage|null {
  if(!pathname.startsWith("/dashboard")) return null;
  const segment=pathname.split("/")[2];
  if(!segment)return null;
  return (Object.entries(dashboardRoutes).find(([,route])=>route===segment)?.[0] as DashboardPage|undefined)??null;
}

const navigation: { section: string; items: [DashboardPage, typeof Layers3][] }[] = [
  { section: "", items: [["Overview", Layers3], ["Applications", FolderKanban], ["Verse AI", MessageSquare]] },
  { section: "Multiverse", items: [["Atlas", Activity], ["Verse", GitBranch], ["Passports", CreditCard], ["Runtime", Zap]] },
];

const moduleDetails = [
  { name: "Atlas" as const, kicker: "Observe", description: "Explore authorized applications and capture real runtime behaviour.", image: "/images/multiverse/atlas.png", count: "exploration_runs" },
  { name: "Verse" as const, kicker: "Branch", description: "Model alternate product realities without creating another deployment.", image: "/images/multiverse/verse.png", count: "branches" },
  { name: "Passports" as const, kicker: "Carry", description: "Move signed preferences and capabilities safely between products.", image: "/images/multiverse/passport.png", count: "active_passports" },
  { name: "Runtime" as const, kicker: "Resolve", description: "Evaluate the right behaviour for each request at the edge of your system.", image: "/images/multiverse/verse.png", count: "commits" },
];

function Dashboard({ activePage, onSelect, session, onSignOut }: { activePage: DashboardPage; onSelect: (page:DashboardPage)=>void; session: Session | null; onSignOut: () => void }) {
  const [sidebar, setSidebar] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [apps, setApps] = useState<AppRecord[]>([]);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [createOpen,setCreateOpen]=useState(false);
  const [createError,setCreateError]=useState("");
  const [serviceQuery,setServiceQuery]=useState("");
  const createApplication=async(event:FormEvent<HTMLFormElement>)=>{event.preventDefault();setCreateError("");const form=new FormData(event.currentTarget);try{await api.createApp({name:String(form.get("name")),base_url:String(form.get("base_url")),build_id:String(form.get("build_id")||"build-0.1.0")});setApps((await api.apps()).items);setCreateOpen(false)}catch(reason){setCreateError(reason instanceof Error?reason.message:"Unable to register application")}};
  useEffect(()=>{let stale=false;const refresh=()=>{api.apps().then((appData)=>{if(!stale){setApps(appData.items);setError("")}}).catch((reason)=>{if(!stale)setError(reason instanceof Error?reason.message:"Dashboard data unavailable")}).finally(()=>{if(!stale)setLoading(false)});api.status().then((statusData)=>{if(!stale)setStatus(statusData)}).catch(()=>undefined)};refresh();const timer=window.setInterval(refresh,4000);const visible=()=>{if(document.visibilityState==="visible")refresh()};document.addEventListener("visibilitychange",visible);return()=>{stale=true;window.clearInterval(timer);document.removeEventListener("visibilitychange",visible)}},[]);
  const selectPage = (page: DashboardPage) => { onSelect(page); setSidebar(false); };
  const count = (key: string) => status?.counts?.[key] ?? 0;
  const matchingModules=moduleDetails.filter(module=>{
    const query=serviceQuery.trim().toLowerCase();
    return !query||query==="all"||`${module.name} ${module.kicker} ${module.description}`.toLowerCase().includes(query);
  });
  return (
    <main className="min-h-screen bg-[#080909] text-[#f4f4f5]"><GlobalErrorToasts/><Toast message={error} onClose={()=>setError("")}/><Toast message={createError} onClose={()=>setCreateError("")}/>
      {activePage!=="Verse AI"&&<header className="fixed inset-x-0 top-0 z-40 flex h-[54px] border-b border-white/10 bg-[#090a0a]/95 backdrop-blur-xl">
        <button type="button" aria-label="Toggle navigation" onClick={() => setSidebar((value) => !value)} className="grid w-[54px] shrink-0 place-items-center border-r border-white/10 lg:pointer-events-none">
          <span className="relative block size-7"><span className="absolute left-0 top-2 size-3 rounded-full bg-white"/><span className="absolute bottom-1 right-0 h-3 w-5 rounded-full bg-white"/></span>
        </button>
        <button type="button" onClick={() => selectPage("Overview")} className="hidden w-[186px] items-center gap-3 border-r border-white/10 px-3 text-left sm:flex">
          <span className="grid size-7 place-items-center rounded-full bg-violet-200 text-xs font-semibold text-black">M</span>
          <span className="truncate font-medium">{session?.workspaces[0]?.name||"Multiverse workspace"}</span><ChevronDown className="ml-auto text-white/40" size={15}/>
        </button>
        <div className="flex min-w-0 flex-1 items-center gap-3 px-4"><span className="size-1.5 rounded-full bg-violet-300"/><span className="truncate text-sm font-medium">{activePage}</span></div>
        <button type="button" onClick={() => setCreateOpen(true)} className="flex items-center gap-2 border-l border-white/10 px-4 text-xs font-medium transition hover:bg-white/5 sm:text-sm"><Plus size={16}/> <span className="hidden sm:inline">Register app</span></button>
        <button type="button" onClick={() => selectPage("Account")} aria-label="Open account" title="Account" className="grid w-[58px] place-items-center border-l border-white/10"><span className="grid size-7 place-items-center rounded-full bg-violet-200 text-xs font-semibold text-black">{session?.email?.[0]?.toUpperCase()||"M"}</span></button>
      </header>}

      {activePage==="Verse AI"&&<button type="button" aria-label="Open navigation" onClick={()=>setSidebar(true)} className="fixed left-3 top-3 z-20 grid size-10 place-items-center rounded-full border border-white/10 bg-[#111212]/90 text-white/65 backdrop-blur-xl lg:hidden"><PanelLeftClose className="rotate-180" size={16}/></button>}
      <aside className={`fixed bottom-0 left-0 z-30 flex max-w-[88vw] flex-col border-r border-white/10 bg-[#0d0e0e] transition-transform lg:translate-x-0 ${sidebarCollapsed ? "w-[240px] lg:w-16" : "w-[240px]"} ${activePage==="Verse AI"?"top-0":"top-[54px]"} ${sidebar ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="dashboard-scroll flex-1 space-y-7 overflow-y-auto px-3 py-5">
          {navigation.map((group) => <div key={group.section || "primary"}>
            {group.section && !sidebarCollapsed && <p className="mb-3 px-3 font-mono text-xs uppercase tracking-[.16em] text-white/55">{group.section}</p>}
            <div className="space-y-1">{group.items.map(([label, Icon]) => <button type="button" onClick={() => selectPage(label)} key={label} title={sidebarCollapsed ? label : undefined} className={`flex h-9 w-full items-center gap-2.5 rounded-md px-3 text-left text-[13px] transition hover:bg-white/5 ${sidebarCollapsed ? "lg:justify-center" : ""} ${activePage === label ? "bg-violet-500/15 text-violet-200" : "text-white/75"}`}><Icon size={15} className={activePage === label ? "text-violet-300" : "text-white/40"}/><span className={sidebarCollapsed ? "lg:hidden" : ""}>{label}</span></button>)}</div>
          </div>)}
        </div>
        <div className="space-y-1 border-t border-white/10 p-3">
          <button type="button" title={sidebarCollapsed ? "System status" : undefined} onClick={() => selectPage("Runtime")} className={`w-full px-3 py-2 text-left transition hover:bg-white/5 ${sidebarCollapsed ? "lg:text-center" : ""}`}><span className={`flex items-center gap-3 text-[13px] text-white/75 ${sidebarCollapsed ? "lg:justify-center" : ""}`}><HeartPulse size={16}/><span className={sidebarCollapsed ? "lg:hidden" : ""}>System status</span></span><span className={`mt-2 grid grid-cols-3 gap-2 text-[9px] text-white/35 ${sidebarCollapsed ? "lg:hidden" : ""}`}>{[["API",true],["Flagsmith",Boolean(status?.flagsmith.connected)],["Worker",Boolean(status?.redis.connected)]].map(([label,ready])=><span key={String(label)} className="flex items-center gap-1.5"><i className={`size-1.5 rounded-full ${ready?"bg-white":"bg-white/20"}`}/>{label}</span>)}</span></button>
      <button type="button" aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"} title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"} onClick={() => setSidebarCollapsed(value => !value)} className={`flex h-9 w-full items-center gap-3 px-3 text-[13px] text-white/65 ${sidebarCollapsed ? "lg:justify-center" : ""}`}><PanelLeftClose size={16} className={sidebarCollapsed ? "lg:rotate-180" : ""}/><span className={sidebarCollapsed ? "lg:hidden" : ""}>{sidebarCollapsed ? "Expand" : "Collapse"}</span></button>
        </div>
      </aside>

      {sidebar && <button aria-label="Close navigation" onClick={() => setSidebar(false)} className="fixed inset-0 z-20 bg-black/60 lg:hidden"/>}

      <section className={`${activePage==="Verse AI"?"h-screen overflow-hidden":"min-h-screen px-5 pb-16 pt-20 lg:px-10 lg:pt-20 xl:px-14"} ${sidebarCollapsed ? "lg:ml-16" : "lg:ml-[240px]"}`}>
        <motion.div key={activePage} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .42 }} className={activePage==="Verse AI"?"h-full w-full":"mx-auto max-w-[1480px]"}>
          {activePage === "Overview" && <><label className="mb-5 flex h-12 w-full max-w-xl items-center gap-3 border border-white/10 bg-white/[.025] px-4 text-white/40 transition focus-within:border-white/25"><Search size={17}/><input aria-label="Search services" type="search" value={serviceQuery} onChange={event=>setServiceQuery(event.target.value)} placeholder="Search services (Atlas, Verse, Passport, Runtime)" className="h-full min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-white/35"/></label>{matchingModules.length?<div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{matchingModules.map((module, index) => <motion.button type="button" key={module.name} onClick={() => selectPage(module.name)} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .07 }} className="relative aspect-square overflow-hidden border border-white/10 bg-[#111212] text-left transition-colors duration-200 hover:border-violet-300/70"><img src={module.image} alt="" className="absolute inset-0 h-full w-full object-cover opacity-45"/><span className="absolute inset-0 bg-gradient-to-t from-[#0d0e0e] via-[#0d0e0e]/45 to-transparent"/><span className="absolute inset-x-0 bottom-0 block p-6"><small className="text-[10px] font-semibold uppercase tracking-[.22em] text-violet-300">{module.kicker}</small><span className="mt-2 flex items-end justify-between"><b className="text-2xl font-medium">{module.name}</b><strong className="font-mono text-sm text-white/45">{count(module.count).toString().padStart(2,"0")}</strong></span><span className="mt-3 block max-w-[28ch] text-xs leading-5 text-white/50">{module.description}</span></span></motion.button>)}</div>:<p className="py-10 text-sm text-white/40">No services match “{serviceQuery}”. Try Atlas, Verse, Passport, Runtime, or all.</p>}<div className="mt-10 flex items-center justify-between"><div><h2 className="text-xl font-medium">Authorized applications</h2><p className="mt-1 text-xs text-white/40">Targets explicitly registered for observation.</p></div><button type="button" onClick={() => selectPage("Applications")} className="text-xs text-violet-300 hover:text-violet-200">View all</button></div></>}
          {activePage === "Applications" && <div className="mb-7 flex items-center justify-between"><div><h2 className="text-xl font-medium">Application registry</h2><p className="mt-1 text-xs text-white/40">Multiverse only explores targets you authorize here.</p></div><button type="button" onClick={() => setCreateOpen(true)} className="rounded-lg bg-white px-4 py-2.5 text-xs font-semibold text-black transition hover:bg-violet-100"><Plus className="mr-2 inline" size={14}/>Register application</button></div>}
          {(activePage === "Overview" || activePage === "Applications") && <ApplicationGrid compact={activePage === "Overview"} apps={apps} loading={loading} onCreate={() => setCreateOpen(true)} onOpen={() => selectPage("Atlas")}/>} 
          {activePage === "Overview" && <OverviewPassports onViewMore={() => selectPage("Passports")}/>} 
          {activePage === "Account" && <AccountWorkspace session={session} apps={apps} onSignOut={onSignOut} onRemove={async id=>{await api.deleteApp(id);setApps(items=>items.filter(item=>item.id!==id))}}/>}
          {activePage === "Applications" && apps.length>0 && <ApplicationSetup apps={apps}/>} 
          {activePage === "Verse AI" && <AssistantWorkspace apps={apps} onCreate={() => setCreateOpen(true)}/>} 
          {(activePage === "Atlas" || activePage === "Verse" || activePage === "Passports" || activePage === "Runtime") && <ModuleWorkspace page={activePage} apps={apps} status={status} onCreate={() => setCreateOpen(true)}/>} 
        </motion.div>
      </section>

      <section className="hidden">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5 }}>
          <div className="mb-10 flex items-center justify-between"><div><h1 className="text-4xl font-medium tracking-tight">Overview</h1><div className="mt-3 flex gap-2 text-xs"><span className={`rounded-full px-2 py-1 ${status?.flagsmith.connected?"bg-emerald-950 text-emerald-300":"bg-amber-950 text-amber-300"}`}>Flagsmith {status?.flagsmith.connected?"connected":"disconnected"}</span><span className={`rounded-full px-2 py-1 ${status?.redis.connected?"bg-emerald-950 text-emerald-300":"bg-zinc-800 text-zinc-400"}`}>Worker {status?.redis.connected?"ready":"offline"}</span></div></div><button className="hidden items-center gap-2 text-sm text-violet-300 sm:flex"><UserPlus size={18}/> Invite your team</button></div>
          <h2 className="mb-8 text-2xl font-semibold">Projects</h2>
          {loading&&<p className="text-white/50">Loading persisted applications…</p>}
          <div className="grid grid-cols-1 gap-7 md:grid-cols-2 2xl:grid-cols-3">
            {apps.map((project, index) => <motion.button key={project.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .08 * index }} className="flex min-h-36 flex-col items-start justify-between border border-white/25 bg-[#090a0a] p-5 text-left transition hover:border-violet-400/70 hover:bg-white/[.025]">
              <span><b className="block text-lg">{project.name}</b><small className="mt-1 block text-white/40">{project.build_id}</small></span>
              <span className={`inline-flex items-center gap-2 px-3 py-2 text-sm font-medium ${project.environments.length?"bg-emerald-950 text-emerald-300":"bg-amber-950 text-amber-300"}`}>{project.environments.length?<Check size={16}/>:<X size={16}/>} {project.environments.length?`${project.environments.length} Flagsmith environment${project.environments.length>1?"s":""}`:"Flagsmith not connected"}</span>
            </motion.button>)}
            {!loading&&!error&&apps.length===0&&<div className="flex min-h-36 flex-col justify-center border border-white/15 p-5 text-white/50"><b className="text-white">No applications yet</b><span className="mt-2 text-sm">Register an authorized application to begin Atlas exploration.</span></div>}
            <button onClick={()=>setCreateOpen(true)} className="grid min-h-36 place-items-center border border-dashed border-white/25 text-lg transition hover:border-violet-400 hover:text-violet-300"><span className="flex items-center gap-2"><Plus size={19}/> Register application</span></button>
          </div>
        </motion.div>
      </section>
      {createOpen&&<div className="fixed inset-0 z-50 grid place-items-center bg-black/75 p-4"><form onSubmit={(event)=>void createApplication(event)} className="w-full max-w-md space-y-4 border border-white/15 bg-[#111212] p-6 shadow-2xl"><div className="flex items-center justify-between"><h2 className="text-xl font-semibold">Register application</h2><button type="button" onClick={()=>setCreateOpen(false)}><X size={18}/></button></div><p className="text-sm text-white/45">Only explicitly authorized targets can be explored.</p><input name="name" required placeholder="Application name" className="h-11 w-full bg-white/5 px-3 outline-none ring-1 ring-white/15 focus:ring-violet-400"/><input name="base_url" required type="url" placeholder="http://localhost:5173/demo/shop" className="h-11 w-full bg-white/5 px-3 outline-none ring-1 ring-white/15 focus:ring-violet-400"/><input name="build_id" placeholder="build-0.1.0" className="h-11 w-full bg-white/5 px-3 outline-none ring-1 ring-white/15 focus:ring-violet-400"/><button className="h-11 w-full bg-white font-semibold text-black">Register</button></form></div>}
    </main>
  );
}

function ApplicationGrid({ apps, loading, onCreate, onOpen, compact=false }: { apps: AppRecord[]; loading: boolean; onCreate: () => void; onOpen: () => void; compact?: boolean }) {
  if (loading) return <div className="mt-6 animate-pulse rounded-2xl border border-white/10 bg-white/[.025] p-8 text-sm text-white/35">Loading registered applications...</div>;
  return <div className={`application-registry-grid mt-6 grid gap-4 md:grid-cols-2 ${compact?"overview-app-grid":"xl:grid-cols-3"}`}>
    {apps.map((app) => <button type="button" onClick={onOpen} key={app.id} className={`group flex flex-col border border-white/10 bg-[#101111] p-6 text-left transition hover:border-violet-300/35 hover:bg-white/[.035] ${compact?"aspect-square":"min-h-44"}`}><span className="flex items-start justify-between"><span className="grid size-9 place-items-center bg-violet-400/10 text-violet-300"><Globe2 size={17}/></span><small className="font-mono text-[10px] text-white/30">{app.build_id}</small></span><span className="mt-auto"><b className="block text-xl font-medium">{app.name}</b><small className="mt-2 block truncate text-white/35">{app.base_url}</small><span className="mt-5 flex flex-wrap items-center gap-3 text-[11px] text-white/45"><span>{app.capability_count} capabilities</span><span>{app.workflow_count} workflows</span><span className="ml-auto text-violet-300 transition group-hover:translate-x-0.5">Open Atlas →</span></span></span></button>)}
    {apps.length===0&&<div className={`flex flex-col justify-end border border-white/10 bg-white/[.02] p-6 ${compact?"aspect-square":"min-h-44"}`}><b className="font-medium">No applications registered</b><p className="mt-2 max-w-sm text-xs leading-5 text-white/40">Add an application you own or are explicitly authorized to test.</p></div>}
    <button type="button" onClick={onCreate} className={`grid place-items-center border border-dashed border-white/15 text-sm text-white/50 transition hover:border-violet-300/40 hover:text-violet-200 ${compact?"aspect-square":"min-h-44"}`}><span className="flex items-center gap-2"><Plus size={16}/>Register application</span></button>
  </div>;
}

function AssistantWorkspace({apps,onCreate}:{apps:AppRecord[];onCreate:()=>void}){
  const [appId,setAppId]=useState(apps[0]?.id??"");
  const [context,setContext]=useState<ProjectContext|null>(null);
  const [messages,setMessages]=useState<ChatTurn[]>([]);
  const [configured,setConfigured]=useState<boolean|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [draft,setDraft]=useState("");
  const [historyOpen,setHistoryOpen]=useState(false);
  const [thinkingSteps,setThinkingSteps]=useState<string[]>([]);
  const [chatHistory,setChatHistory]=useState<{id:string;appId:string;title:string;messages:ChatTurn[]}[]>([]);
  const bottomRef=useRef<HTMLDivElement>(null);
  useEffect(()=>{if(!apps.some(app=>app.id===appId))setAppId(apps[0]?.id??"")},[apps,appId]);
  useEffect(()=>{api.assistantStatus().then(value=>setConfigured(value.configured)).catch(()=>setConfigured(false))},[]);
  useEffect(()=>{if(!appId){setContext(null);return}let current=true;api.projectContext(appId).then(value=>{if(current)setContext(value)}).catch(reason=>{if(current)setError(reason instanceof Error?reason.message:"Unable to load project")});return()=>{current=false}},[appId]);
  useEffect(()=>{bottomRef.current?.scrollIntoView({behavior:"smooth",block:"nearest"})},[messages,busy,thinkingSteps]);
  const archive=()=>{if(messages.length)setChatHistory(items=>[{id:crypto.randomUUID(),appId,title:messages.find(item=>item.role==="user")?.content.slice(0,52)||"Project conversation",messages},...items])};
  const startNew=()=>{archive();setMessages([]);setThinkingSteps([]);setDraft("");setError("");setHistoryOpen(false)};
  const switchProject=(value:string)=>{if(value===appId)return;archive();setAppId(value);setMessages([]);setThinkingSteps([]);setDraft("");setError("")};
  const submit=async(event:FormEvent<HTMLFormElement>)=>{event.preventDefault();const message=draft.trim();if(!message||!appId||busy)return;const history=messages.slice(-12);setMessages(value=>[...value,{role:"user",content:message},{role:"assistant",content:""}]);setThinkingSteps([]);setDraft("");setBusy(true);setError("");try{await streamAssistant({application_id:appId,message,history,model:"thinkingmachines/Inkling:peft:262144"},event=>{if(event.type==="step"&&event.text)setThinkingSteps(value=>value.includes(event.text!)?value:[...value,event.text!]);if(event.type==="delta"&&event.text)setMessages(value=>value.map((item,index)=>index===value.length-1?{...item,content:item.content+event.text}:item));if(event.type==="error")throw new Error(event.message||"Tinker streaming failed")})}catch(reason){setMessages(value=>value.at(-1)?.role==="assistant"&&!value.at(-1)?.content?value.slice(0,-1):value);setError(reason instanceof Error?reason.message:"The assistant is unavailable")}finally{setBusy(false)}};
  if(!apps.length)return <div className="border border-white/10 bg-[#111212] p-10"><h2 className="text-2xl font-medium">Register a project first</h2><p className="mt-3 text-sm text-white/45">The assistant is deliberately scoped to one authorized project at a time.</p><button type="button" onClick={onCreate} className="mt-6 rounded-lg bg-white px-4 py-2.5 text-xs font-semibold text-black">Register application</button></div>;
  const prompts=["Summarize this project","What should I fix first?","Explain the latest exploration"];
  const empty=messages.length===0;
  const latestQuestion=[...messages].reverse().find(message=>message.role==="user")?.content??"";
  const wantsCharts=/\b(chart|charts|graph|graphs|visuali[sz]e|visualization|dashboard|plot|metrics view)\b/i.test(latestQuestion);
  return <section className={`verse-ai ${empty?"verse-ai-empty":""} relative flex h-full min-h-0 w-full flex-col items-center justify-center overflow-hidden bg-[#080909] px-4 sm:px-7`}>
    <button type="button" onClick={startNew} className="absolute left-5 top-5 z-20 flex h-9 items-center gap-2 rounded-full border border-white/10 bg-white/[.04] px-3 text-xs text-white/55 backdrop-blur-xl transition hover:border-white/25 hover:text-white sm:left-7"><Plus size={13}/>New</button>
    <button type="button" onClick={()=>{if(messages.length)setChatHistory(items=>[{id:"current",appId,title:messages.find(item=>item.role==="user")?.content.slice(0,52)||"Current conversation",messages},...items.filter(item=>item.id!=="current")]);setHistoryOpen(true)}} className="absolute right-5 top-5 z-20 flex h-9 items-center gap-2 rounded-full border border-white/10 bg-white/[.04] px-3 text-xs text-white/55 backdrop-blur-xl transition hover:border-white/25 hover:text-white sm:right-7"><History size={13}/>History</button>
    <AnimatePresence>{historyOpen&&<><motion.button aria-label="Close history" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} onClick={()=>setHistoryOpen(false)} className="absolute inset-0 z-30 bg-black/45 backdrop-blur-sm"/><motion.aside initial={{opacity:0,x:28}} animate={{opacity:1,x:0}} exit={{opacity:0,x:28}} transition={{duration:.28,ease:"easeOut"}} className="absolute bottom-3 right-3 top-3 z-40 w-[min(380px,calc(100%-24px))] overflow-hidden rounded-[24px] border border-white/10 bg-[#111214]/95 p-5 shadow-2xl backdrop-blur-2xl"><div className="flex items-center justify-between"><div><h3 className="font-medium">Chat history</h3><p className="mt-1 text-[11px] text-white/35">Current session · MongoDB persistence next</p></div><button type="button" onClick={()=>setHistoryOpen(false)} className="grid size-9 place-items-center rounded-full hover:bg-white/5"><X size={16}/></button></div><div className="dashboard-scroll mt-6 space-y-2 overflow-y-auto">{chatHistory.length?chatHistory.map(chat=><button type="button" key={chat.id} onClick={()=>{setAppId(chat.appId);setMessages(chat.messages);setHistoryOpen(false)}} className="w-full rounded-xl border border-white/10 p-4 text-left transition hover:border-violet-300/35 hover:bg-white/[.03]"><b className="block truncate text-sm font-medium">{chat.title}</b><span className="mt-2 flex items-center gap-2 text-[10px] text-white/35"><Clock3 size={11}/>{apps.find(app=>app.id===chat.appId)?.name??"Project"} · {chat.messages.length} messages</span></button>):<div className="rounded-2xl border border-dashed border-white/10 px-5 py-10 text-center"><History className="mx-auto text-white/20" size={22}/><p className="mt-3 text-sm text-white/45">No previous chats yet</p><p className="mt-1 text-[11px] text-white/25">Starting a new chat will place the current one here.</p></div>}</div></motion.aside></>}</AnimatePresence>
    <AnimatePresence>{empty&&<motion.div initial={{opacity:0,y:14,filter:"blur(8px)"}} animate={{opacity:1,y:0,filter:"blur(0px)"}} exit={{opacity:0,y:-12}} transition={{duration:.65,ease:[.22,1,.36,1]}} className="absolute bottom-[190px] w-full px-6 text-center"><h2 className="text-3xl font-medium tracking-[-.035em] text-white sm:text-4xl">How can I help today?</h2><div className="mt-4 flex flex-wrap justify-center gap-2">{prompts.map((prompt,index)=><motion.button initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{delay:.35+index*.08}} key={prompt} type="button" onClick={()=>setDraft(prompt)} className="rounded-full border border-white/10 bg-white/[.025] px-3 py-2 text-xs text-white/40 transition hover:border-white/25 hover:text-white/75">{prompt}</motion.button>)}</div></motion.div>}</AnimatePresence>
    {!empty&&<div className="dashboard-scroll absolute bottom-40 left-1/2 top-14 w-[min(768px,calc(100%-32px))] -translate-x-1/2 overflow-y-auto py-6">{context&&wantsCharts&&<ProjectSnapshot context={context}/>} {messages.map((message,index)=>message.role==="user"?<motion.div initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} key={`user-${index}`} className="mb-7 flex justify-end"><div className="max-w-[82%] whitespace-pre-wrap rounded-2xl bg-white px-4 py-3 text-sm leading-6 text-black shadow-[0_10px_35px_rgba(0,0,0,.18)]">{message.content}</div></motion.div>:<motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} key={`assistant-${index}`} className="mb-10 max-w-3xl text-white/85">{index===messages.length-1&&thinkingSteps.length>0&&<ThoughtLine working={busy} steps={thinkingSteps} label="Inkling is thinking…" doneLabel="Thought for" className="mb-5"/>}{message.content&&<MarkdownAnswer content={message.content}/>}</motion.div>)}<div ref={bottomRef}/></div>}
    <motion.form layout onSubmit={event=>void submit(event)} initial={{opacity:0,y:18,scale:.99}} animate={{opacity:1,y:0,scale:1}} transition={{opacity:{delay:.3,duration:.6,ease:"easeOut"},y:{delay:.3,duration:.6,ease:[.22,1,.36,1]},layout:{duration:.55,ease:[.22,1,.36,1]}}} className={`${empty?"relative mt-6 shrink-0":"absolute bottom-[14px] left-1/2 -translate-x-1/2"} z-20 max-h-[min(220px,42vh)] w-[min(768px,calc(100%-32px))] rounded-[24px] border border-white/20 bg-white/[.09] p-3 shadow-[0_24px_80px_rgba(0,0,0,.55),inset_0_1px_0_rgba(255,255,255,.15)] backdrop-blur-2xl`}>
      <textarea id="assistant-message" value={draft} onChange={event=>setDraft(event.target.value)} onKeyDown={event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();event.currentTarget.form?.requestSubmit()}}} rows={2} required maxLength={4000} disabled={!configured||busy} placeholder={configured?`Ask about ${context?.application.name??"the selected project"}…`:"Add TINKER_API_KEY to enable chat"} className="dashboard-scroll max-h-36 min-h-[58px] w-full resize-none bg-transparent px-3 py-2 text-[15px] leading-6 text-white outline-none placeholder:text-white/28 disabled:opacity-45"/>
      <div className="flex items-end justify-between gap-2 pt-2"><div className="flex min-w-0 flex-1 gap-2"><div className="min-w-0 flex-1 sm:max-w-[210px]"><CustomSelect monochrome dropUp ariaLabel="Project" value={appId} onChange={switchProject} options={apps.map(app=>({value:app.id,label:app.name,description:app.build_id}))}/></div><div className="hidden w-[210px] sm:block"><CustomSelect monochrome dropUp ariaLabel="Model" value="thinkingmachines/Inkling:peft:262144" onChange={()=>undefined} options={[{value:"thinkingmachines/Inkling:peft:262144",label:"Inkling",description:"Thinking Machines Lab"}]}/></div></div><button aria-label="Send message" disabled={!configured||busy||!draft.trim()} className="grid size-12 shrink-0 place-items-center rounded-full bg-white text-black shadow-lg transition hover:scale-[1.03] hover:bg-white/90 active:scale-95 disabled:cursor-not-allowed disabled:opacity-30"><Send size={17}/></button></div>
      <Toast message={error} onClose={()=>setError("")}/>
    </motion.form>
  </section>;
}

function MarkdownAnswer({content}:{content:string}){
  return <div className="text-[15px] leading-7 text-white/78 [&_a]:text-violet-300 [&_a]:underline [&_a]:underline-offset-4 [&_blockquote]:my-5 [&_blockquote]:border-l-2 [&_blockquote]:border-violet-300/50 [&_blockquote]:pl-4 [&_blockquote]:text-white/55 [&_code]:rounded [&_code]:bg-white/[.07] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[.88em] [&_h1]:mb-4 [&_h1]:mt-8 [&_h1]:text-2xl [&_h1]:font-semibold [&_h2]:mb-3 [&_h2]:mt-7 [&_h2]:text-xl [&_h2]:font-semibold [&_h3]:mb-2 [&_h3]:mt-6 [&_h3]:text-base [&_h3]:font-semibold [&_hr]:my-7 [&_hr]:border-white/10 [&_li]:my-1.5 [&_ol]:my-4 [&_ol]:list-decimal [&_ol]:pl-6 [&_p]:my-3 [&_pre]:my-5 [&_pre]:overflow-x-auto [&_pre]:rounded-xl [&_pre]:border [&_pre]:border-white/10 [&_pre]:bg-black/40 [&_pre]:p-4 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_strong]:font-semibold [&_strong]:text-white [&_table]:my-5 [&_table]:w-full [&_table]:border-collapse [&_td]:border-b [&_td]:border-white/10 [&_td]:p-3 [&_td]:text-left [&_th]:border-b [&_th]:border-white/15 [&_th]:p-3 [&_th]:text-left [&_th]:text-white [&_ul]:my-4 [&_ul]:list-disc [&_ul]:pl-6"><ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown></div>;
}

function ProjectSnapshot({context}:{context:ProjectContext}){
  const recent=context.recent_explorations.slice(0,5);
  const maximum=Math.max(1,...recent.map(run=>run.budget));
  const stats=[
    [context.workflows.length,"Workflows"],
    [context.capabilities.length,"Capabilities"],
    [context.branches.length,"Branches"],
    [context.recent_explorations.length,"Explorations"],
  ] as const;
  return <motion.section initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} className="mb-10 border-y border-white/10 py-5">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-[10px] uppercase tracking-[.2em] text-white/35">Live project context</p><h3 className="mt-1 text-lg font-medium">{context.application.name}</h3></div><span className="font-mono text-[10px] text-white/30">{context.application.build_id}</span></div>
    <div className="mt-5 grid grid-cols-2 gap-px overflow-hidden border border-white/10 bg-white/10 sm:grid-cols-4">{stats.map(([value,label])=><div key={label} className="bg-[#0b0c0c] p-4"><strong className="text-2xl font-light tabular-nums">{String(value).padStart(2,"0")}</strong><span className="mt-1 block text-[10px] text-white/35">{label}</span></div>)}</div>
    {recent.length>0&&<div className="mt-5 space-y-3"><div className="flex justify-between text-[10px] uppercase tracking-[.14em] text-white/30"><span>Recent test budgets</span><span>max {maximum}</span></div>{recent.map((run,index)=><div key={`${run.strategy}-${index}`} className="grid grid-cols-[90px_1fr_52px] items-center gap-3 text-[11px]"><span className="truncate text-white/55">{run.strategy}</span><span className="h-1 overflow-hidden rounded-full bg-white/10"><motion.i initial={{width:0}} animate={{width:`${Math.max(6,(run.budget/maximum)*100)}%`}} transition={{delay:.15+index*.07,duration:.55}} className="block h-full rounded-full bg-white/75"/></span><span className="text-right font-mono text-white/30">{run.budget} tests</span></div>)}</div>}
  </motion.section>;
}

function ApplicationSetup({apps}:{apps:AppRecord[]}){
  const [appId,setAppId]=useState(apps[0].id);const [message,setMessage]=useState("");const [busy,setBusy]=useState(false);
  const [step,setStep]=useState(1);const [flagsmithMode,setFlagsmithMode]=useState("cloud");
  const [capability,setCapability]=useState("interface.density");const [capabilityType,setCapabilityType]=useState("string");const [workflowAction,setWorkflowAction]=useState("screenshot");
  const act=async(fn:()=>Promise<unknown>,next?:number)=>{setBusy(true);setMessage("");try{const result=await fn();const id=result&&typeof result==="object"&&"id" in result?String((result as {id:unknown}).id):"";setMessage(id?`Saved successfully. ID: ${id}`:"Saved successfully.");if(next)setStep(next)}catch(reason){setMessage(reason instanceof Error?reason.message:"Operation failed")}finally{setBusy(false)}};
  const steps=[{number:1,title:"Connect Flagsmith",text:"Choose Cloud or your own instance."},{number:2,title:"Declare capability",text:"Map a flag to product meaning."},{number:3,title:"Register workflow",text:"Describe the journey to observe."}];
  const panel="py-2 sm:py-4";
  return <section className="mt-12 border-t border-white/10 pt-10">
    <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-[10px] font-semibold uppercase tracking-[.2em] text-violet-300">Application setup</p><h2 className="mt-2 text-2xl font-medium">Connect the behavioural pipeline</h2><p className="mt-2 max-w-xl text-sm leading-6 text-white/40">One focused step at a time. No JSON required.</p></div><div className="w-full sm:w-72"><label className="mb-2 block text-xs text-white/45">Application</label><CustomSelect ariaLabel="Application" value={appId} onChange={value=>{setAppId(value);setStep(1);setMessage("")}} options={apps.map(app=>({value:app.id,label:app.name}))}/></div></div>
    <div className="mt-8 grid gap-5 lg:grid-cols-[260px_minmax(0,760px)]">
      <nav className="space-y-2" aria-label="Application setup steps">{steps.map(item=><button type="button" key={item.number} onClick={()=>{setStep(item.number);setMessage("")}} className={`flex w-full gap-3 border p-4 text-left transition ${step===item.number?"border-violet-300/45 bg-violet-400/10":"border-white/10 bg-[#101111] hover:border-white/20"}`}><span className={`grid size-7 shrink-0 place-items-center rounded-full text-xs ${step===item.number?"bg-violet-300 text-black":"bg-white/5 text-white/40"}`}>{item.number}</span><span><b className="block text-sm font-medium">{item.title}</b><small className="mt-1 block text-[11px] leading-4 text-white/35">{item.text}</small></span></button>)}</nav>
      <div>
        {step===1&&<form className={`${panel} space-y-7`} onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void act(()=>api.connectApp(appId,{flagsmith_api_url:String(f.get("url")),environment_key:String(f.get("key")),environment_name:String(f.get("environment_name")||"sandbox"),environment_type:"sandbox",management_token:String(f.get("token"))||undefined}),2)}}><div><span className="text-[10px] font-semibold uppercase tracking-[.18em] text-violet-300">Step 01</span><h3 className="mt-2 text-xl font-medium">Where is Flagsmith hosted?</h3><p className="mt-2 text-sm leading-6 text-white/40">Cloud is the easiest option. Your environment key is stored encrypted by Multiverse.</p></div><div className="grid gap-3 sm:grid-cols-2">{[{value:"cloud",title:"Flagsmith Cloud",text:"Connect edge.api.flagsmith.com"},{value:"self",title:"Self-hosted",text:"Use your own public or private URL"}].map(option=><button type="button" key={option.value} onClick={()=>setFlagsmithMode(option.value)} className={`border p-4 text-left transition ${flagsmithMode===option.value?"border-violet-300/60 bg-violet-400/10":"border-white/10 hover:border-white/25"}`}><b className="block text-sm">{option.title}</b><span className="mt-1 block text-xs text-white/35">{option.text}</span></button>)}</div><div className="grid gap-5">{flagsmithMode==="cloud"?<><input type="hidden" name="url" value="https://edge.api.flagsmith.com/api/v1/"/><div className="border border-emerald-400/15 bg-emerald-400/5 p-4 text-xs text-emerald-200">Cloud endpoint ready: edge.api.flagsmith.com</div></>:<LabeledInput label="Flagsmith API URL" name="url" type="url" placeholder="https://flags.example.com/api/v1/"/>}<LabeledInput label="Environment name" name="environment_name" defaultValue="sandbox"/><LabeledInput label="Environment key" name="key" type="password" placeholder="Paste the Environment ID from Flagsmith"/><LabeledInput label="Management token" name="token" type="password" placeholder="Optional — only needed for management actions"/></div><div><button disabled={busy} className="h-12 rounded-xl bg-white px-6 text-sm font-semibold text-black transition hover:bg-violet-100 disabled:opacity-50">{busy?"Connecting…":"Connect and continue"}</button><p className="mt-3 text-[11px] leading-5 text-white/30">Use the Environment ID from Flagsmith → Environment Settings → SDK Keys. Do not paste an organisation token into the environment-key field.</p></div></form>}
        {step===2&&<form className={`${panel} space-y-7`} onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);const flagKey=String(f.get("flag_key"));const mapping=capabilityType==="boolean"?{"true":true,"false":false}:{};void act(()=>api.updateCapabilities(appId,{schema_version:"1.0",application:appId,capabilities:{[capability]:{flag_key:flagKey,type:capabilityType,mapping,user_configurable:true,portable:true}}}),3)}}><div><span className="text-[10px] font-semibold uppercase tracking-[.18em] text-violet-300">Step 02</span><h3 className="mt-2 text-xl font-medium">Give the flag a human meaning</h3><p className="mt-2 text-sm text-white/40">This makes behaviour portable across products without writing a manifest.</p></div><div className="grid gap-5"><FieldShell label="Product capability"><CustomSelect ariaLabel="Semantic capability" value={capability} onChange={setCapability} options={[{value:"interface.density",label:"Interface density"},{value:"accessibility.motion",label:"Motion preference"},{value:"network.bandwidth",label:"Bandwidth preference"},{value:"privacy.analytics",label:"Analytics consent"},{value:"experimentation.opt_in",label:"Experiment participation"}]}/></FieldShell><LabeledInput label="Flagsmith flag name" name="flag_key" placeholder="e.g. new_checkout"/><FieldShell label="Value type"><CustomSelect ariaLabel="Capability type" value={capabilityType} onChange={setCapabilityType} options={[{value:"boolean",label:"On / off"},{value:"string",label:"Text value"},{value:"number",label:"Number"}]}/></FieldShell></div><div className="flex gap-3"><button type="button" onClick={()=>setStep(1)} className="h-12 rounded-xl border border-white/15 px-5 text-sm">Back</button><button disabled={busy} className="h-12 rounded-xl bg-white px-6 text-sm font-semibold text-black disabled:opacity-50">Save and continue</button></div></form>}
        {step===3&&<form className={`${panel} space-y-7`} onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);const name=String(f.get("name"));const startPath=String(f.get("start_path")||"/");const action:Record<string,unknown>={action:workflowAction};if(workflowAction==="navigate")action.path=String(f.get("step_value")||startPath);else if(workflowAction==="screenshot")action.label=String(f.get("step_value")||"capture");else if(workflowAction==="wait")action.timeout_ms=Math.min(Number(f.get("step_value"))||1000,2000);void act(()=>api.registerWorkflow(appId,{name,version:"1.0",definition:{name,version:"1.0",start_path:startPath,steps:[action]}}))}}><div><span className="text-[10px] font-semibold uppercase tracking-[.18em] text-violet-300">Step 03</span><h3 className="mt-2 text-xl font-medium">Describe one user journey</h3><p className="mt-2 text-sm text-white/40">Start small. You can add more workflows after the first exploration.</p></div><div className="grid gap-5"><LabeledInput label="Workflow name" name="name" placeholder="e.g. Checkout journey"/><LabeledInput label="Starting path" name="start_path" defaultValue="/"/><FieldShell label="First action"><CustomSelect ariaLabel="Workflow action" value={workflowAction} onChange={setWorkflowAction} options={[{value:"screenshot",label:"Capture screenshot"},{value:"navigate",label:"Visit another path"},{value:"read",label:"Read visible components"},{value:"wait",label:"Wait briefly"}]}/></FieldShell><LabeledInput label="Action detail" name="step_value" placeholder={workflowAction==="navigate"?"Path, e.g. /checkout":workflowAction==="wait"?"Milliseconds, e.g. 1000":"Capture label (optional)"}/></div><div className="flex flex-wrap gap-3"><button type="button" onClick={()=>setStep(2)} className="h-12 rounded-xl border border-white/15 px-5 text-sm">Back</button><button disabled={busy} className="h-12 rounded-xl bg-white px-6 text-sm font-semibold text-black disabled:opacity-50">Register workflow</button><button type="button" disabled={busy} onClick={()=>void act(()=>api.syncApp(appId))} className="h-12 rounded-xl border border-violet-300/25 px-5 text-sm text-violet-200">Sync flags</button></div></form>}
        {message.startsWith("Saved successfully")&&<p role="status" className="mt-4 border border-violet-300/20 bg-violet-400/5 p-3 text-xs text-violet-200">{message}</p>}<Toast message={message&&!message.startsWith("Saved successfully")?message:""} onClose={()=>setMessage("")}/>
      </div>
    </div>
  </section>;
}

function passportIssuedAt(passport: PassportRecord) {
  const payload = passport.payload as Record<string, unknown>;
  return Date.parse(String(payload.issued_at ?? payload.created_at ?? passport.expires_at)) || 0;
}

function OverviewPassports({ onViewMore }: { onViewMore: () => void }) {
  const [passports, setPassports] = useState<PassportRecord[]>([]);
  useEffect(() => {
    let current = true;
    const refresh = () => void api.passports().then(data => { if (current) setPassports(data.items); }).catch(() => undefined);
    refresh();
    const timer = window.setInterval(refresh, 10000);
    return () => { current = false; window.clearInterval(timer); };
  }, []);
  const latest = [...passports].sort((a, b) => passportIssuedAt(b) - passportIssuedAt(a)).slice(0, 3);
  return <section className="mt-10">
    <div className="mb-5 flex items-center justify-between"><h2 className="text-xl font-medium">Issued passports</h2><button type="button" onClick={onViewMore} className="text-xs text-violet-300 transition hover:text-violet-200">View more <span aria-hidden="true">→</span></button></div>
    {latest.length ? <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">{latest.map(passport => <PassportCard key={passport.id} passport={passport}/>)}</div> : <p className="py-5 text-sm text-white/35">No issued passports yet.</p>}
  </section>;
}

function AccountWorkspace({session,apps,onSignOut,onRemove}:{session:Session|null;apps:AppRecord[];onSignOut:()=>void;onRemove:(id:string)=>Promise<void>}){
  const [pending,setPending]=useState<AppRecord|null>(null);
  const [confirmation,setConfirmation]=useState("");
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const confirmRemoval=async()=>{
    if(!pending||confirmation.trim()!==pending.name)return;
    setBusy(true);setMessage("");
    try{await onRemove(pending.id);setPending(null);setConfirmation("")}
    catch(reason){setMessage(reason instanceof Error?reason.message:"Unable to remove this project")}
    finally{setBusy(false)}
  };
  return <div className="mx-auto max-w-5xl space-y-10">
    <header><p className="text-[10px] font-semibold uppercase tracking-[.2em] text-white/40">Workspace profile</p><h1 className="mt-2 text-3xl font-medium tracking-tight">Account</h1><p className="mt-2 text-sm text-white/45">Your sign-in, workspaces, and registered projects.</p></header>
    <section className="grid gap-4 md:grid-cols-2">
      <article className="border border-white/10 bg-white/[.025] p-5"><h2 className="text-sm font-medium text-white/65">Personal details</h2><dl className="mt-5 space-y-4 text-sm"><div><dt className="text-xs text-white/35">Email</dt><dd className="mt-1 break-all">{session?.email??"—"}</dd></div><div><dt className="text-xs text-white/35">Account ID</dt><dd className="mt-1 break-all font-mono text-xs text-white/60">{session?.id??"—"}</dd></div><div><dt className="text-xs text-white/35">Member since</dt><dd className="mt-1">{session?.created_at?new Date(session.created_at).toLocaleDateString():"—"}</dd></div></dl><button type="button" onClick={onSignOut} className="mt-6 h-10 border border-white/15 px-4 text-xs text-white/75 transition hover:border-white/30 hover:text-white">Sign out</button></article>
      <article className="border border-white/10 bg-white/[.025] p-5"><h2 className="text-sm font-medium text-white/65">Workspaces</h2>{session?.workspaces.length?<div className="mt-4 space-y-3">{session.workspaces.map(workspace=><div key={workspace.id} className="border-t border-white/10 pt-3"><div className="flex items-center justify-between gap-4"><b className="truncate text-sm">{workspace.name}</b><span className="shrink-0 text-xs capitalize text-white/45">{workspace.role}</span></div><p className="mt-1 break-all font-mono text-[10px] text-white/30">{workspace.id}</p></div>)}</div>:<p className="mt-4 text-sm text-white/40">No workspace memberships found.</p>}</article>
    </section>
    <section><div className="mb-4 flex items-end justify-between gap-4"><div><h2 className="text-xl font-medium">Your projects</h2><p className="mt-1 text-xs text-white/40">Projects registered in your workspaces.</p></div><span className="font-mono text-xs text-white/40">{apps.length.toString().padStart(2,"0")}</span></div>
      {apps.length?<div className="divide-y divide-white/10 border-y border-white/10">{apps.map(app=><article key={app.id} className="flex flex-col gap-4 py-5 sm:flex-row sm:items-center sm:justify-between"><div className="min-w-0"><h3 className="truncate font-medium">{app.name}</h3><p className="mt-1 truncate text-xs text-white/45">{app.base_url}</p><p className="mt-2 text-[11px] text-white/35">{app.workspace_name??"Workspace"} · {app.build_id} · {app.environments.length} environment{app.environments.length===1?"":"s"} · {app.workflow_count} workflow{app.workflow_count===1?"":"s"}</p></div>{app.can_delete?<button type="button" onClick={()=>{setPending(app);setConfirmation("");setMessage("")}} className="h-9 self-start border border-white/15 px-3 text-xs text-white/65 transition hover:border-red-300/50 hover:text-red-200 sm:self-auto">Remove project</button>:<span className="self-start text-[11px] text-white/30 sm:self-auto">Workspace owner can remove</span>}</article>)}</div>:<p className="border-y border-white/10 py-8 text-sm text-white/40">No registered projects in your workspaces.</p>}
    </section>
    {pending&&<div className="fixed inset-0 z-50 grid place-items-center bg-black/75 p-4"><section role="dialog" aria-modal="true" aria-labelledby="remove-project-title" className="w-full max-w-md space-y-5 border border-white/15 bg-[#101111] p-6 shadow-2xl"><div><p className="text-[10px] uppercase tracking-[.18em] text-white/40">Permanent action</p><h2 id="remove-project-title" className="mt-2 text-xl font-medium">Remove {pending.name}?</h2><p className="mt-3 text-sm leading-6 text-white/55">This deletes the project, its environments, workflows, branches, explorations, and observations. Signed passports already in your account remain unchanged.</p></div><label className="block text-xs text-white/50">Type <b className="text-white">{pending.name}</b> to confirm<input autoFocus value={confirmation} onChange={event=>setConfirmation(event.target.value)} className="mt-2 h-11 w-full border border-white/15 bg-black/30 px-3 text-sm text-white outline-none focus:border-white/35"/></label>{message&&<p role="alert" className="text-sm text-red-200">{message}</p>}<div className="flex justify-end gap-3"><button type="button" disabled={busy} onClick={()=>{setPending(null);setConfirmation("")}} className="h-10 px-4 text-xs text-white/60">Cancel</button><button type="button" disabled={busy||confirmation.trim()!==pending.name} onClick={()=>void confirmRemoval()} className="h-10 bg-white px-4 text-xs font-semibold text-black disabled:cursor-not-allowed disabled:opacity-35">{busy?"Removing…":"Remove permanently"}</button></div></section></div>}
  </div>;
}

function ModuleWorkspace({ page, apps, status, onCreate }: { page: Exclude<DashboardPage,"Overview"|"Applications"|"Verse AI"|"Account">; apps: AppRecord[]; status: SystemStatus | null; onCreate: () => void }) {
  const [explorations,setExplorations]=useState<Exploration[]>([]);
  const [branches,setBranches]=useState<Branch[]>([]);
  const [passports,setPassports]=useState<PassportRecord[]>([]);
  const [chosenApp,setChosenApp]=useState(apps[0]?.id??"");
  const [result,setResult]=useState<Record<string,unknown>|null>(null);
  const [appDetail,setAppDetail]=useState<AppDetail|null>(null);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [workflowChoice,setWorkflowChoice]=useState("");
  const [strategy,setStrategy]=useState("adaptive");
  const [domainType,setDomainType]=useState("boolean");
  const [motionPreference,setMotionPreference]=useState("full");
  const [bandwidthPreference,setBandwidthPreference]=useState("standard");
  const [densityPreference,setDensityPreference]=useState("comfortable");
  const [analyticsPreference,setAnalyticsPreference]=useState("true");
  const [experimentPreference,setExperimentPreference]=useState("true");
  const [passportWorkflow,setPassportWorkflow]=useState("");
  const visibleExplorations=[...explorations].sort((a,b)=>{
    const activeA=a.status==="running"||a.status==="queued";
    const activeB=b.status==="running"||b.status==="queued";
    if(activeA!==activeB)return activeA?-1:1;
    const timeA=Date.parse(a.started_at??a.completed_at??"")||0;
    const timeB=Date.parse(b.started_at??b.completed_at??"")||0;
    return timeB-timeA;
  }).slice(0,9);
  const latestPassports=[...passports].sort((a,b)=>passportIssuedAt(b)-passportIssuedAt(a));
  const reload=async()=>{try{if(page==="Atlas")setExplorations((await api.explorations()).items);if(page==="Verse")setBranches((await api.branches()).items);if(page==="Passports")setPassports((await api.passports()).items)}catch(reason){setMessage(reason instanceof Error?reason.message:"Unable to load workspace")}};
  useEffect(()=>{let current=true;const refresh=()=>{if(page==="Atlas")void api.explorations().then(data=>{if(current)setExplorations(data.items)}).catch(()=>undefined);if(page==="Verse")void api.branches().then(data=>{if(current)setBranches(data.items)}).catch(()=>undefined);if(page==="Passports")void api.passports().then(data=>{if(current)setPassports(data.items)}).catch(()=>undefined)};refresh();const timer=window.setInterval(refresh,page==="Atlas"?1500:4000);const visible=()=>{if(document.visibilityState==="visible")refresh()};document.addEventListener("visibilitychange",visible);return()=>{current=false;window.clearInterval(timer);document.removeEventListener("visibilitychange",visible)}},[page]);
  const selectedApp=chosenApp||apps[0]?.id||"";
  useEffect(()=>{let current=true;if(selectedApp)void api.app(selectedApp).then(value=>{if(current){setAppDetail(value);setPassportWorkflow(existing=>value.workflows.some(workflow=>workflow.id===existing)?existing:(value.workflows[0]?.id??""))}}).catch(reason=>{if(current)setMessage(reason instanceof Error?reason.message:"Unable to load application setup")});return()=>{current=false}},[selectedApp]);
  const run=async(action:()=>Promise<unknown>)=>{setBusy(true);setMessage("");try{const value=await action();if(value&&typeof value==="object")setResult(value as Record<string,unknown>);await reload()}catch(reason){setMessage(reason instanceof Error?reason.message:"Action failed")}finally{setBusy(false)}};
  const data = {
    Atlas: { image: "/images/multiverse/atlas.png", primary: status?.counts?.exploration_runs??0, primaryLabel: "exploration runs", secondary: status?.counts?.observations??0, secondaryLabel: "observations", action: "Start with an application" },
    Verse: { image: "/images/multiverse/verse.png", primary: status?.counts?.branches??0, primaryLabel: "active branches", secondary: status?.counts?.commits??0, secondaryLabel: "behaviour commits", action: "Create from Atlas evidence" },
    Passports: { image: "/images/multiverse/passport.png", primary: status?.counts?.active_passports??0, primaryLabel: "active passports", secondary: apps.reduce((total,app)=>total+app.capability_count,0), secondaryLabel: "known capabilities", action: "Issue from observed capabilities" },
    Runtime: { image: "/images/multiverse/verse.png", primary: apps.length, primaryLabel: "registered applications", secondary: apps.reduce((total,app)=>total+app.environments.length,0), secondaryLabel: "connected environments", action: "Resolve through an application" },
  }[page];
  if(!apps.length)return <div className="rounded-3xl border border-white/10 bg-[#111212] p-10"><h2 className="text-2xl font-medium">Register an application first</h2><p className="mt-3 text-sm text-white/45">Every Multiverse action is scoped to an explicitly authorized application.</p><button type="button" onClick={onCreate} className="mt-6 rounded-lg bg-white px-4 py-2.5 text-xs font-semibold text-black">Register application</button></div>;
  const input="h-10 w-full rounded-lg border border-white/10 bg-black/30 px-3 text-sm outline-none focus:border-violet-300/50";
  return <div className="space-y-8">
    <div className="space-y-5"><div className="py-2 sm:py-4"><div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-[10px] font-semibold uppercase tracking-[.22em] text-violet-300">{page} control</p><h2 className="mt-2 text-2xl font-medium">{data.action}</h2></div><div className="w-full sm:w-80"><label className="mb-2 block text-[11px] font-medium uppercase tracking-[.12em] text-white/35">Application</label><CustomSelect ariaLabel="Application" value={selectedApp} onChange={setChosenApp} options={apps.map(app=>({value:app.id,label:app.name}))}/></div></div>
      {page==="Atlas"&&<form className="mt-8 space-y-5" onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);const app=apps.find(item=>item.id===selectedApp);if(!app?.environments[0]||!workflowChoice){setMessage("Connect a valid Flagsmith environment and register a workflow first.");return}const flagKey=String(f.get("flag_key")).trim();const rawValues=String(f.get("values")).split(",").map(value=>value.trim()).filter(Boolean);const values:unknown[]=domainType==="boolean"?[false,true]:domainType==="number"?rawValues.map(Number):rawValues;if(!flagKey||!values.length||values.some(value=>typeof value==="number"&&Number.isNaN(value))){setMessage("Enter a flag name and at least one valid value.");return}void run(()=>api.startExploration({application_id:selectedApp,environment_id:app.environments[0].id,workflow_id:workflowChoice,strategy,budget:Number(f.get("budget")),seed:42,domains:{[flagKey]:values}}))}}><div><div className="mb-3"><h3 className="text-sm font-medium">Feature values to explore</h3><p className="mt-1 text-xs text-white/35">Choose one Flagsmith feature and the possible values Atlas should test.</p></div><div className="grid gap-4 md:grid-cols-[1.2fr_.8fr_1.5fr]"><div><label className="mb-2 block text-xs font-medium text-white/60">Flag name</label><input required name="flag_key" defaultValue="new_checkout" placeholder="e.g. new_checkout" className={`${input} h-12 rounded-xl px-4`}/></div><div><label className="mb-2 block text-xs font-medium text-white/60">Value type</label><CustomSelect ariaLabel="Feature value type" value={domainType} onChange={setDomainType} options={[{value:"boolean",label:"On / off"},{value:"string",label:"Text options"},{value:"number",label:"Numbers"}]}/></div><div><label className="mb-2 block text-xs font-medium text-white/60">Possible values</label><input name="values" disabled={domainType==="boolean"} defaultValue={domainType==="boolean"?"Off, On":"control, variant-a"} placeholder="Separate values with commas" className={`${input} h-12 rounded-xl px-4 disabled:text-white/35`}/></div></div></div><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[1.5fr_1fr_140px_180px]"><div><label className="mb-2 block text-xs font-medium text-white/60">Workflow</label><CustomSelect ariaLabel="Workflow" value={workflowChoice} onChange={setWorkflowChoice} placeholder={appDetail?.workflows.length?"Select workflow":"No workflows registered"} options={(appDetail?.workflows??[]).map(workflow=>({value:workflow.id,label:`${workflow.name} · v${workflow.version}`}))}/></div><div><label className="mb-2 block text-xs font-medium text-white/60">Strategy</label><CustomSelect ariaLabel="Strategy" value={strategy} onChange={setStrategy} options={[{value:"adaptive",label:"Adaptive — find differences quickly"},{value:"pairwise",label:"Pairwise — cover interactions"},{value:"exhaustive",label:"Exhaustive — test every combination"}]}/></div><div><label className="mb-2 block text-xs font-medium text-white/60">Max tests</label><input name="budget" aria-label="Maximum exploration budget" type="number" min="1" max="512" defaultValue="16" className={`${input} h-12 rounded-xl px-4`}/></div><button disabled={busy||!appDetail?.environments.length||!appDetail?.workflows.length||!workflowChoice} className="mt-auto h-12 rounded-xl bg-white px-4 text-xs font-semibold text-black transition hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-35">{busy?"Starting…":"Start exploration"}</button></div></form>}
      {page==="Verse"&&<form className="mt-8 max-w-4xl space-y-5" onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void run(()=>api.createBranch({application_id:selectedApp,name:String(f.get("name")),message:String(f.get("message")),assignments:{}}))}}><div><h3 className="text-sm font-medium">Create a behavioural branch</h3><p className="mt-1 text-xs leading-5 text-white/35">Give this reality a clear name and explain why it exists.</p></div><div className="grid gap-4 md:grid-cols-2"><LabeledInput label="Branch name" name="name" placeholder="e.g. compact-checkout"/><LabeledInput label="Initial commit message" name="message" placeholder="e.g. Test a shorter purchase flow"/></div><button disabled={busy} className="h-11 rounded-xl bg-white px-6 text-xs font-semibold text-black disabled:opacity-50">{busy?"Creating…":"Create branch"}</button></form>}
      {page==="Passports"&&<form className="mt-7 space-y-7" onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);if(!passportWorkflow){setMessage("Register and select a workflow before issuing its pass.");return}void run(()=>api.createPassport({application_id:selectedApp,workflow_id:passportWorkflow,audience:[selectedApp],preferences:{"privacy.analytics":analyticsPreference==="true","accessibility.motion":motionPreference,"network.bandwidth":bandwidthPreference,"interface.density":densityPreference,"experimentation.opt_in":experimentPreference==="true"},ttl_days:Number(f.get("ttl"))}))}}><div className="grid gap-5 lg:grid-cols-[1.2fr_.8fr]"><div><label className="mb-2 block text-xs font-medium text-white/60">Workflow on this pass</label><CustomSelect ariaLabel="Passport workflow" value={passportWorkflow} onChange={setPassportWorkflow} placeholder={appDetail?.workflows.length?"Select workflow":"No workflows registered"} options={(appDetail?.workflows??[]).map(workflow=>({value:workflow.id,label:workflow.name,description:`Version ${workflow.version}`}))}/><p className="mt-2 text-[11px] leading-5 text-white/30">The project, build and selected workflow are included in the signed payload.</p></div><div><label className="mb-2 block text-xs font-medium text-white/60">Valid for</label><div className="flex gap-2"><input name="ttl" type="number" min="1" max="365" defaultValue="30" className={`${input} h-12 rounded-xl px-4`}/><span className="grid h-12 place-items-center rounded-xl border border-white/10 px-4 text-xs text-white/40">days</span></div></div></div><div className="border-t border-white/10 pt-6"><h3 className="text-sm font-medium">Portable preferences</h3><p className="mt-1 text-xs text-white/35">These values travel with the signed project pass.</p><div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3"><PreferenceField label="Motion" value={motionPreference} onChange={setMotionPreference} options={[{value:"full",label:"Full motion"},{value:"reduced",label:"Reduced motion"}]}/><PreferenceField label="Bandwidth" value={bandwidthPreference} onChange={setBandwidthPreference} options={[{value:"standard",label:"Standard"},{value:"low",label:"Data saver"},{value:"high",label:"High quality"}]}/><PreferenceField label="Interface spacing" value={densityPreference} onChange={setDensityPreference} options={[{value:"comfortable",label:"Comfortable"},{value:"compact",label:"Compact"}]}/><PreferenceField label="Analytics" value={analyticsPreference} onChange={setAnalyticsPreference} options={[{value:"true",label:"Allow analytics"},{value:"false",label:"Do not allow"}]}/><PreferenceField label="Experiments" value={experimentPreference} onChange={setExperimentPreference} options={[{value:"true",label:"Participate"},{value:"false",label:"Opt out"}]}/></div></div><button disabled={busy||!passportWorkflow} className="h-12 rounded-xl bg-white px-6 text-sm font-semibold text-black transition hover:bg-violet-100 disabled:cursor-not-allowed disabled:opacity-35">{busy?"Signing with Ed25519…":"Issue signed project pass"}</button></form>}
      {page==="Runtime"&&<form className="mt-6 space-y-5" onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void run(()=>api.resolveRuntime({application_id:selectedApp,passport_token:String(f.get("passport"))||undefined,preview_token:String(f.get("preview"))||undefined,user_context:{identifier:String(f.get("identifier"))},entitlements:String(f.get("entitlements")).split(",").map(value=>value.trim()).filter(Boolean)}))}}><div className="grid gap-4 md:grid-cols-2"><div><label className="mb-2 block text-xs font-medium text-white/60">User identifier</label><input required name="identifier" defaultValue="demo-user" placeholder="e.g. customer-1042" className={`${input} h-12 rounded-xl px-4`}/></div><div><label className="mb-2 block text-xs font-medium text-white/60">Entitlements <span className="font-normal text-white/30">(optional)</span></label><input name="entitlements" placeholder="pro, beta-access" className={`${input} h-12 rounded-xl px-4`}/></div><div><label className="mb-2 block text-xs font-medium text-white/60">Passport token <span className="font-normal text-white/30">(optional)</span></label><input name="passport" placeholder="Paste signed token" className={`${input} h-12 rounded-xl px-4`}/></div><div><label className="mb-2 block text-xs font-medium text-white/60">Preview token <span className="font-normal text-white/30">(optional)</span></label><input name="preview" placeholder="Paste preview token" className={`${input} h-12 rounded-xl px-4`}/></div></div><button disabled={busy} className="h-11 rounded-xl bg-white px-6 text-xs font-semibold text-black disabled:opacity-50">{busy?"Resolving…":"Resolve experience"}</button></form>}
      <Toast message={message} onClose={()=>setMessage("")}/>
    </div><div className="grid gap-5 sm:grid-cols-2"><Metric value={data.primary} label={data.primaryLabel}/><Metric value={data.secondary} label={data.secondaryLabel} accent/></div></div>
    {page==="Atlas"?<div className="pt-1"><div className="mb-4 flex items-center justify-between"><h3 className="text-sm font-medium text-white/70">Exploration tests</h3>{explorations.some(run=>run.status==="running"||run.status==="queued")&&<span className="flex items-center gap-2 text-[10px] uppercase tracking-[.14em] text-violet-300"><i className="size-1.5 animate-pulse rounded-full bg-violet-300"/>Testing live</span>}</div>{visibleExplorations.length?<div className="flex flex-wrap gap-2.5">{visibleExplorations.map(run=>{const chipStatus:CallChipStatus=run.status==="completed"?"done":run.status==="failed"||run.status==="cancelled"?"error":run.status==="queued"?"idle":"running";const tested=run.metrics?.executed_count??0;return <CallChip key={run.id} name={run.strategy} argument={`${tested}/${run.budget} configurations`} status={chipStatus} expectedMs={Math.max(5000,run.budget*1200)} size={38} radius={12} showTimer={chipStatus==="running"}/>})}</div>:<p className="py-5 text-sm text-white/35">No tests yet. Start an exploration above and progress will appear here.</p>}</div>:<div className={page==="Passports"?"py-1":"rounded-3xl border border-white/10 bg-[#111212] p-6"}><div className="mb-5 flex items-center justify-between"><h3 className="font-medium">{page==="Verse"?"Behaviour branches":page==="Passports"?"Issued passports":"Resolution output"}</h3>{page==="Verse"&&<span className="flex items-center gap-2 text-[10px] uppercase tracking-[.14em] text-emerald-300"><i className="size-1.5 animate-pulse rounded-full bg-emerald-400"/>Live</span>}</div>{page==="Verse"&&<RecordList rows={branches.map(x=>[x.name,`revision ${x.revision} · ${x.head_message}`,x.head_commit_hash])}/>} {page==="Passports"&&(latestPassports.length?<div className="grid gap-7 md:grid-cols-2 2xl:grid-cols-3">{latestPassports.map(passport=><PassportCard key={passport.id} passport={passport}/>)}</div>:<p className="py-8 text-sm text-white/35">No project passes yet. Select a workflow above and issue the first signed card.</p>)} {page==="Runtime"&&<pre className="max-h-72 overflow-auto rounded-xl bg-black/40 p-4 text-xs text-violet-100">{result?JSON.stringify(result,null,2):"Run a resolution to inspect the evaluated configuration and provenance."}</pre>}</div>}
  </div>;
}

function PassportCard({passport}:{passport:PassportRecord}){
  const scope=passport.payload.scope;
  const signature=passport.signature??"unsigned";
  const fingerprint=signature.length>24?`${signature.slice(0,12)}…${signature.slice(-10)}`:signature;
  const seed=[...signature].reduce((total,char)=>total+char.charCodeAt(0),0);
  const modules=Array.from({length:121},(_,index)=>((index*17+seed+(index%11)*7)%13)<6);
  const bars=Array.from({length:30},(_,index)=>1+((seed+index*11)%3));
  return <article className="group mx-auto w-full max-w-[360px] overflow-hidden rounded-[34px] shadow-[0_28px_70px_rgba(0,0,0,.42)] transition duration-300 hover:-translate-y-1">
    <div className="relative min-h-[370px] overflow-hidden bg-[radial-gradient(circle_at_15%_0%,rgba(255,240,224,.11),transparent_45%),linear-gradient(145deg,#27272a,#111113)] p-7 text-[#f4f4f5] ring-1 ring-inset ring-white/10">
      <div className="flex items-center justify-between"><div className="flex items-center gap-2.5"><span className="relative size-5 rounded-full bg-[radial-gradient(circle_at_40%_30%,#ff8a5c,#ff5a1f_45%,#d8400c)] shadow-[0_2px_3px_rgba(0,0,0,.8),inset_0_1px_1px_rgba(255,220,190,.5)]"><i className="absolute inset-[7px] rounded-full bg-[#2a0e04]"/></span><b className="text-sm font-semibold">Multiverse Pass</b></div></div>
      <p className="mt-12 text-[10px] font-semibold uppercase tracking-[.18em] text-white/45">Project</p><h4 className="mt-2 line-clamp-2 min-h-[70px] text-[34px] font-semibold leading-[1.03] tracking-[-.04em]">{scope?.application_name??"Portable profile"}</h4>
      <div className="mt-7 grid grid-cols-3 gap-3 border-t border-white/10 pt-5">{[["Workflow",scope?.workflow_name??"General"],["Build",scope?.build_id??"—"],["Version",`v${passport.version}`]].map(([label,value])=><div key={label} className="min-w-0"><span className="block text-[8px] font-semibold uppercase tracking-[.16em] text-white/35">{label}</span><b className="mt-2 block truncate text-xs font-medium" title={value}>{value}</b></div>)}</div>
      <div className="pointer-events-none absolute inset-0 translate-x-[-130%] bg-[linear-gradient(105deg,transparent_42%,rgba(255,246,236,.13)_48%,rgba(255,246,236,.04)_52%,transparent_58%)] transition-transform duration-1000 group-hover:translate-x-[90%]"/>
    </div>
    <div className="relative min-h-[180px] bg-[linear-gradient(90deg,#e6e2d9,#faf8f3_12%,#faf8f3_88%,#e2ded4)] px-7 py-6 text-[#2b2a28] shadow-[inset_0_18px_24px_rgba(0,0,0,.18)]">
      <span className="absolute -left-3 -top-3 size-6 rounded-full bg-[#111212]"/><span className="absolute -right-3 -top-3 size-6 rounded-full bg-[#111212]"/><div className="absolute inset-x-6 top-0 border-t-2 border-dashed border-[#2b2a28]/35"/>
      <div className="flex items-start justify-between gap-5"><div className="min-w-0"><p className="font-mono text-[9px] uppercase tracking-[.12em] text-[#2b2a28]/60">Ed25519 signature</p><code className="mt-2 block break-all font-mono text-[11px] font-semibold leading-4">{fingerprint}</code><p className="mt-4 font-mono text-[9px] uppercase tracking-[.1em] text-[#2b2a28]/55">Expires</p><b className="mt-1 block font-mono text-xs">{new Date(passport.expires_at).toLocaleDateString()}</b></div><div className="grid size-[88px] shrink-0 grid-cols-11 bg-[#f8f5ee] p-2 shadow-inner">{modules.map((filled,index)=><i key={index} className={filled?"bg-[#2b2a28]":"bg-transparent"}/>)}</div></div>
      <div className="mt-5 flex h-7 items-stretch gap-[2px] overflow-hidden">{bars.map((width,index)=><i key={index} style={{width:`${width*2}px`}} className="shrink-0 rounded-[1px] bg-[#2b2a28]"/>)}</div>
    </div>
  </article>;
}

function Toast({message,onClose}:{message:string;onClose?:()=>void}){
  const closeRef=useRef(onClose);useEffect(()=>{closeRef.current=onClose},[onClose]);
  useEffect(()=>{if(!message)return;const timer=window.setTimeout(()=>closeRef.current?.(),5200);return()=>window.clearTimeout(timer)},[message]);
  return <AnimatePresence>{message&&<motion.div role="alert" initial={{opacity:0,y:-12,scale:.98}} animate={{opacity:1,y:0,scale:1}} exit={{opacity:0,y:-8,scale:.98}} transition={{duration:.24,ease:"easeOut"}} className="fixed right-5 top-5 z-[120] flex w-[min(380px,calc(100%-40px))] items-start gap-3 rounded-2xl border border-white/15 bg-[#111212]/95 p-4 text-sm leading-5 text-white shadow-2xl backdrop-blur-xl"><span className="mt-1 size-2 shrink-0 rounded-full bg-white"/><span className="min-w-0 flex-1">{message}</span><button type="button" onClick={onClose} aria-label="Dismiss notification" className="grid size-6 shrink-0 place-items-center rounded-full text-white/45 transition hover:bg-white/5 hover:text-white"><X size={13}/></button></motion.div>}</AnimatePresence>;
}

function GlobalErrorToasts(){
  const [message,setMessage]=useState("");
  useEffect(()=>{const onError=(event:ErrorEvent)=>setMessage(event.error instanceof Error?event.error.message:event.message||"Something went wrong.");const onRejection=(event:PromiseRejectionEvent)=>setMessage(event.reason instanceof Error?event.reason.message:"An unexpected request failed.");window.addEventListener("error",onError);window.addEventListener("unhandledrejection",onRejection);return()=>{window.removeEventListener("error",onError);window.removeEventListener("unhandledrejection",onRejection)}},[]);
  return <Toast message={message} onClose={()=>setMessage("")}/>;
}

function Metric({value,label,accent=false}:{value:number;label:string;accent?:boolean}){return <div className={`rounded-3xl border p-6 ${accent?"border-violet-200 bg-violet-300 text-black":"border-white/10 bg-[#111212]"}`}><strong className="text-4xl font-light">{value.toString().padStart(2,"0")}</strong><span className={`mt-2 block text-xs ${accent?"text-black/55":"text-white/45"}`}>{label}</span></div>}
function RecordList({rows}:{rows:[string,string,string][]}){return rows.length?<div className="divide-y divide-white/10">{rows.map(([title,meta,id])=><div key={id} className="flex items-center justify-between gap-4 py-4"><div><b className="text-sm font-medium">{title}</b><p className="mt-1 text-xs text-white/40">{meta}</p></div><code className="max-w-40 truncate text-[10px] text-white/25">{id}</code></div>)}</div>:<p className="py-8 text-sm text-white/35">No records yet. Use the controls above to create the first one.</p>}

type SelectOption={value:string;label:string;description?:string};
function FieldShell({label,children}:{label:string;children:ReactNode}){return <div><label className="mb-2 block text-xs font-medium text-white/55">{label}</label>{children}</div>}
function LabeledInput({label,name,type="text",placeholder,defaultValue}:{label:string;name:string;type?:string;placeholder?:string;defaultValue?:string}){return <div><label htmlFor={`field-${name}`} className="mb-2 block text-xs font-medium text-white/55">{label}</label><input id={`field-${name}`} required={name!=="token"} name={name} type={type} placeholder={placeholder} defaultValue={defaultValue} className="h-12 w-full rounded-xl border border-white/10 bg-black/30 px-4 text-sm outline-none transition placeholder:text-white/20 focus:border-violet-300/50 focus:ring-2 focus:ring-violet-300/10"/></div>}
function PreferenceField({label,value,onChange,options}:{label:string;value:string;onChange:(value:string)=>void;options:SelectOption[]}){return <div><label className="mb-2 block text-xs font-medium text-white/60">{label}</label><CustomSelect ariaLabel={label} value={value} onChange={onChange} options={options}/></div>}
function CustomSelect({value,onChange,options,placeholder="Select an option",ariaLabel,monochrome=false,dropUp=false}:{value:string;onChange:(value:string)=>void;options:SelectOption[];placeholder?:string;ariaLabel:string;monochrome?:boolean;dropUp?:boolean}){
  const [open,setOpen]=useState(false);const root=useRef<HTMLDivElement>(null);const selected=options.find(option=>option.value===value);
  useEffect(()=>{const close=(event:PointerEvent)=>{if(root.current&&!root.current.contains(event.target as Node))setOpen(false)};document.addEventListener("pointerdown",close);return()=>document.removeEventListener("pointerdown",close)},[]);
  const openStyle=monochrome?"border-white/35 ring-2 ring-white/10":"border-violet-300/60 ring-2 ring-violet-300/10";
  return <div ref={root} className="relative"><button type="button" aria-label={ariaLabel} aria-haspopup="listbox" aria-expanded={open} onClick={()=>setOpen(current=>!current)} onKeyDown={event=>{if(event.key==="Escape")setOpen(false)}} className={`flex h-12 w-full items-center justify-between gap-3 rounded-xl border bg-black/30 px-4 text-left text-sm transition ${open?openStyle:"border-white/10 hover:border-white/20"}`}><span className={selected?"truncate text-white":"truncate text-white/35"}>{selected?.label??placeholder}</span><ChevronDown size={16} className={`shrink-0 text-white/45 transition-transform ${open?"rotate-180":""}`}/></button>{open&&<div role="listbox" aria-label={ariaLabel} className={`absolute z-[80] max-h-64 w-full overflow-y-auto rounded-xl border border-white/10 bg-[#18191a] p-1.5 shadow-2xl shadow-black/60 ${dropUp?"bottom-full mb-2":"mt-2"}`}><button type="button" role="option" aria-selected={!value} onClick={()=>{onChange("");setOpen(false)}} className="flex w-full items-center rounded-lg px-3 py-2.5 text-left text-sm text-white/35 transition hover:bg-white/5">{placeholder}</button>{options.map(option=><button type="button" role="option" aria-selected={value===option.value} key={option.value} onClick={()=>{onChange(option.value);setOpen(false)}} className={`flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition hover:bg-white/5 ${value===option.value?(monochrome?"bg-white/10 text-white":"bg-violet-400/10 text-violet-200"):"text-white/80"}`}><span className="min-w-0"><span className="block truncate">{option.label}</span>{option.description&&<small className="mt-0.5 block truncate text-[10px] text-white/35">{option.description}</small>}</span>{value===option.value&&<Check size={14} className={`shrink-0 ${monochrome?"text-white":"text-violet-300"}`}/>}</button>)}</div>}</div>;
}

function SocialButton({ icon, label, onClick, disabled=false }: { icon: ReactNode; label: string; onClick?:()=>void; disabled?:boolean }) {
  return <button type="button" onClick={onClick} disabled={disabled} className="flex h-12 items-center justify-center gap-3 rounded-xl border border-white/10 bg-black text-sm font-medium transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50">{icon}{label}</button>;
}

function InputGroup({ name, label, placeholder, type }: { name: string; label: string; placeholder: string; type: string }) {
  return <div className="space-y-2"><label htmlFor={name} className="block text-sm font-medium text-white">{label}</label><input id={name} name={name} required type={type} placeholder={placeholder} className="h-11 w-full rounded-xl border-none bg-brand-gray px-4 text-white outline-none placeholder:text-white/20 focus:ring-2 focus:ring-white/20"/></div>;
}
