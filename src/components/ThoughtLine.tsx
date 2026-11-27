import { useEffect, useRef, useState, type CSSProperties } from "react";
import { HugeiconsIcon } from "@hugeicons/react";
import { ArrowDown01Icon, SparklesIcon, Tick02Icon } from "@hugeicons/core-free-icons";

const format = (seconds: number) => seconds < 60 ? `${seconds.toFixed(1)}s` : `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(1)}s`;

type ThoughtLineProps = { working: boolean; steps: string[]; label?: string; doneLabel?: string; fontSize?: number; collapsible?: boolean; collapseOnSettle?: boolean; showTimer?: boolean; className?: string; style?: CSSProperties };

export function ThoughtLine({ working, steps, label = "Thinking…", doneLabel = "Thought for", fontSize = 14, collapsible = true, collapseOnSettle = true, showTimer = true, className = "", style }: ThoughtLineProps) {
  const [open, setOpen] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (!working) return; const started = performance.now(); const timer = window.setInterval(() => setElapsed((performance.now() - started) / 1000), 100); return () => window.clearInterval(timer); }, [working]);
  useEffect(() => { if (!working && collapseOnSettle) setOpen(false); }, [working, collapseOnSettle]);
  const traceOpen = open && steps.length > 0;
  const visibleLabel = label === "Inkling is thinking…" ? "Reviewing project evidence…" : label;
  const visibleDoneLabel = doneLabel === "Thought for" ? "Reviewed for" : doneLabel;
  const toggle=()=>{setOpen(value=>!value);window.requestAnimationFrame(()=>window.requestAnimationFrame(()=>rootRef.current?.scrollIntoView({behavior:"smooth",block:"nearest"})))};
  return <div ref={rootRef} className={`inline-flex flex-col items-start text-white/55 ${className}`} style={{ fontSize, ...style }}>
    <button type="button" disabled={!collapsible || !steps.length} onClick={toggle} className="group flex items-center gap-2 bg-transparent p-0 text-left disabled:cursor-default">
      <span className={`grid size-5 place-items-center text-white/65 ${working ? "animate-pulse" : "opacity-60"}`}><HugeiconsIcon icon={SparklesIcon} size={16} strokeWidth={2}/></span>
      <span className={working ? "animate-[thought-shimmer_1.8s_linear_infinite] bg-[linear-gradient(100deg,rgba(255,255,255,.45)_30%,#fff_50%,rgba(255,255,255,.45)_70%)] bg-[length:250%_100%] bg-clip-text text-transparent" : "text-white/45"}>{working ? visibleLabel : visibleDoneLabel}</span>
      {showTimer && <span className="font-mono text-[11px] tabular-nums text-white/30">{format(elapsed)}</span>}
      {collapsible && steps.length > 0 && <HugeiconsIcon icon={ArrowDown01Icon} size={13} className={`transition ${traceOpen ? "rotate-180" : ""}`}/>} 
    </button>
    <div className={`grid transition-[grid-template-rows,opacity] duration-300 ${traceOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}><div className="overflow-hidden"><div className="space-y-2 pb-1 pl-7 pt-3">{steps.map((step, index) => { const done = !working || index < steps.length - 1; return <div key={`${index}-${step}`} className="flex items-center gap-2 text-xs text-white/40"><span className="grid size-4 place-items-center">{done ? <HugeiconsIcon icon={Tick02Icon} size={13} strokeWidth={2.4}/> : <i className="size-1.5 animate-pulse rounded-full bg-white/70"/>}</span><span>{step}</span></div>; })}</div></div></div>
    <style>{`@keyframes thought-shimmer{to{background-position:-125% 0}}`}</style>
  </div>;
}
