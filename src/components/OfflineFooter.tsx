import styles from "./OfflineFooter.module.css";

const columns = [
  ["Product", "Atlas", "Verse", "Passport", "Runtime"],
  ["Build", "Architecture", "Runtime SDK", "Workflow schema", "API reference"],
  ["Open source", "Repository", "Roadmap", "Security", "System status"],
  ["Legal", "Privacy", "Terms", "Licences"],
];

export function OfflineFooter() {
  return <footer className={styles.footer}>
    <div className={styles.top}>
      <div className={styles.intro}><a href="#" className={styles.brand}><b>Multiverse</b></a><h2>Know every reality<br/>before you ship one.</h2><p>Open-source behavioural infrastructure for self-hosted Flagsmith.</p><button type="button">Open your workspace <span>↗</span></button></div>
      <div className={styles.columns}>{columns.map(([title,...items])=><nav key={title}><h3>{title}</h3>{items.map(item=><a href="#" key={item}>{item}</a>)}</nav>)}</div>
    </div>
    <div className={styles.meta}><small>© 2026 Multiverse. Open source.</small><small>Observe · Version · Carry · Resolve</small><a href="mailto:hello@multiverse.dev">hello@multiverse.dev</a></div>
    <div className={styles.wordmark} aria-label="Multiverse">MULTIVERSE</div>
  </footer>;
}
