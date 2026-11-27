import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
import styles from "./FeatureAccordion.module.css";

const features = [
  { id: "atlas", number: "01", title: "Discover what flags really change", kicker: "ATLAS / OBSERVE", image: "/images/multiverse/atlas.png", description: "Run structured workflows across valid Flagsmith configurations. Atlas records the evidence and separates outcomes only when their observed behaviour differs." },
  { id: "verse", number: "02", title: "Turn evidence into a branch", kicker: "VERSE / VERSION", image: "/images/multiverse/verse.png", description: "Commit a proven configuration, branch it, review its behavioural diff, and share a scoped preview without provisioning another environment." },
  { id: "passport", number: "03", title: "Move intent, never unchecked access", kicker: "PASSPORT / CARRY", image: "/images/multiverse/passport.png", description: "Sign portable preferences with Ed25519. Each application translates them only into semantic capabilities declared by its own manifest and policy." },
  { id: "runtime", number: "04", title: "Resolve the permitted reality", kicker: "RUNTIME / RESOLVE", image: "/images/multiverse/atlas.png", description: "Combine authenticated identity, application policy, Passport traits, preview state, and live Flagsmith evaluation in one deterministic resolution path." },
];

export function FeatureAccordion() {
  const [active, setActive] = useState(features[0].id);
  useEffect(()=>{
    const syncFromHash=()=>{const id=window.location.hash.slice(1);if(features.some(feature=>feature.id===id))setActive(id)};
    window.addEventListener("hashchange",syncFromHash);
    syncFromHash();
    return()=>window.removeEventListener("hashchange",syncFromHash);
  },[]);
  const selected = features.find(feature => feature.id === active) ?? features[0];
  return <section className={styles.section} aria-labelledby="feature-heading">
    <header><span>THE MULTIVERSE LOOP / 04</span><h2 id="feature-heading">Observe. Version.<br/>Carry. Resolve.</h2><p>One evidence chain connects configuration discovery to the behaviour served at runtime.</p></header>
    <div className={styles.layout}>
      <div className={styles.list}>{features.map(feature => {
        const open = active === feature.id;
        return <article key={feature.id} data-open={open}>
          <button type="button" aria-expanded={open} aria-controls={`${feature.id}-panel`} onClick={() => setActive(feature.id)}><span>{feature.number}</span><strong>{feature.title}</strong><ChevronDown size={18}/></button>
          <div id={`${feature.id}-panel`} className={styles.answer} aria-hidden={!open}><div><small>{feature.kicker}</small><p>{feature.description}</p><img src={feature.image} alt="" className={styles.mobileImage}/></div></div>
        </article>;
      })}</div>
      <div className={styles.preview} data-premium-pin aria-live="polite"><div className={styles.previewMeta}><span>{selected.kicker}</span><small>{selected.number} / 04</small></div><img data-reveal-image key={selected.id} src={selected.image} alt={`${selected.title} preview`}/><p>{selected.description}</p></div>
    </div>
  </section>;
}
