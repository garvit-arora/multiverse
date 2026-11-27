import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { CONTENT } from "../content";
import styles from "./Nav.module.css";

export function Nav({theme,onCta}:{theme:"light"|"dark";onCta?:()=>void}){
  const [active,setActive]=useState("");
  useEffect(()=>{
    const targets=CONTENT.nav.links.map(label=>document.getElementById(navTargets[label])).filter((target):target is HTMLElement=>Boolean(target));
    const updateActive=()=>{
      const marker=window.innerHeight*.32;
      const current=targets.filter(target=>target.getBoundingClientRect().top<=marker).sort((a,b)=>b.getBoundingClientRect().top-a.getBoundingClientRect().top)[0];
      setActive(current?.id??"");
    };
    updateActive();
    window.addEventListener("scroll",updateActive,{passive:true});
    window.addEventListener("resize",updateActive);
    return()=>{window.removeEventListener("scroll",updateActive);window.removeEventListener("resize",updateActive)};
  },[]);
  return createPortal(<header className={styles.root} data-theme={theme} data-intro="nav"><a className={styles.brand} href="#top">{CONTENT.brand}</a><nav>{CONTENT.nav.links.map(label=>{const target=navTargets[label];return <a key={label} href={`#${target}`} data-active={active===target} aria-current={active===target?"location":undefined}>{label}</a>})}</nav><div className={styles.right}><a className={styles.account} href="/signin"><img src="https://assets.uberdesigner.ai/portale/icon-account.svg" alt=""/>{CONTENT.nav.account}</a><a className={styles.cta} href="/signup" onClick={event=>{event.preventDefault();onCta?.()}}>{CONTENT.nav.cta}</a></div></header>, document.body);
}

const navTargets:Record<string,string>={Atlas:"atlas",Verse:"verse",Passport:"passport",Runtime:"runtime",Architecture:"architecture"};
