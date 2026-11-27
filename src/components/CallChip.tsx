import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { HugeiconsIcon } from "@hugeicons/react";
import { CommandLineIcon, File02Icon, PencilEdit01Icon, RefreshIcon, Search01Icon, Tick02Icon } from "@hugeicons/core-free-icons";

export type CallChipStatus = "idle" | "running" | "done" | "error";

const icons = { terminal: CommandLineIcon, file: File02Icon, search: Search01Icon, edit: PencilEdit01Icon };
const words: Record<CallChipStatus,string> = { idle:"queued", running:"testing", done:"complete", error:"failed" };
const formatTime=(ms:number)=>ms<10000?`${Math.round(ms)} ms`:`${(ms/1000).toFixed(1)} s`;

export function CallChip({icon="search",name="Atlas",argument="Loading test",status="running",expectedMs=12000,size=36,radius=12,color="currentColor",surfaceColor="#171719",progressColor="#a78bfa",progressOpacity=.12,doneColor="#34d399",errorColor="#f87171",washOpacity=.14,shake=5,showTimer=true,onRetry,className="",style}:{icon?:keyof typeof icons|ReactNode;name?:string;argument?:string;status?:CallChipStatus;expectedMs?:number;size?:number;radius?:number;color?:string;surfaceColor?:string;progressColor?:string;progressOpacity?:number;doneColor?:string;errorColor?:string;washOpacity?:number;shake?:number;showTimer?:boolean;onRetry?:()=>void;className?:string;style?:CSSProperties}){
  const root=useRef<HTMLSpanElement>(null);const [elapsed,setElapsed]=useState(0);
  useEffect(()=>{if(status!=="running")return;const started=performance.now();let frame=0;const tick=()=>{setElapsed(performance.now()-started);frame=requestAnimationFrame(tick)};frame=requestAnimationFrame(tick);return()=>cancelAnimationFrame(frame)},[status]);
  useEffect(()=>{if(status==="error"&&shake>0&&root.current&&!matchMedia("(prefers-reduced-motion: reduce)").matches){root.current.animate([{transform:"translateX(0)"},{transform:`translateX(-${shake}px)`},{transform:`translateX(${shake}px)`},{transform:"translateX(0)"}],{duration:420})}},[status,shake]);
  const glyph=status==="done"?Tick02Icon:status==="error"?RefreshIcon:typeof icon==="string"?icons[icon as keyof typeof icons]:null;
  const tint=status==="done"?doneColor:status==="error"?errorColor:progressColor;
  const fill=status==="done"?"100%":status==="running"?"90%":status==="error"?"55%":"0%";
  const font=Math.max(11,Math.round(size*.36));
  const css={"--cc-height":`${size}px`,"--cc-radius":`${radius}px`,"--cc-expected":`${expectedMs}ms`,...style} as CSSProperties;
  return <span ref={root} role="status" aria-busy={status==="running"||undefined} aria-label={`${name} ${argument}, ${words[status]}`} className={`group relative inline-flex max-w-full select-none items-center gap-2 overflow-hidden border border-white/10 px-3.5 text-white shadow-[inset_0_1px_0_rgba(255,255,255,.05)] transition active:scale-[.98] ${status==="error"&&onRetry?"cursor-pointer":""} ${className}`} style={{...css,height:"var(--cc-height)",borderRadius:"var(--cc-radius)",color,backgroundColor:surfaceColor,fontSize:font}}>
    <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-0 origin-left transition-[width,background-color] ease-linear motion-reduce:transition-none" style={{width:fill,transitionDuration:status==="running"?"var(--cc-expected)":"240ms",backgroundColor:`color-mix(in srgb, ${tint} ${(status==="done"||status==="error"?washOpacity:progressOpacity)*100}%, transparent)`}}/>
    <span aria-hidden="true" className="relative grid size-[18px] shrink-0 place-items-center transition duration-300" style={{color:status==="done"||status==="error"?tint:color}}>{glyph?<HugeiconsIcon icon={glyph} size={font+3} strokeWidth={status==="done"?2.2:1.8}/>:icon}</span>
    <b aria-hidden="true" className="relative shrink-0 font-medium">{name}</b><span aria-hidden="true" className="relative min-w-0 truncate text-white/60">{argument}</span>
    {showTimer&&<span aria-hidden="true" className="relative ml-1 min-w-[6ch] shrink-0 text-right font-mono text-[10px] tabular-nums text-white/35">{status==="idle"?"—":formatTime(elapsed)}</span>}
    {status==="error"&&onRetry&&<button type="button" aria-label={`Retry ${name} ${argument}`} onClick={onRetry} className="absolute inset-0"/>}
  </span>;
}
