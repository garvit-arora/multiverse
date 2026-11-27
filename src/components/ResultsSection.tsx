import styles from "./ResultsSection.module.css";

const results = [
  { name: "Atlas", outcome: "Observe before you assume", image: "/images/multiverse/atlas.png", stats: [["3", "search strategies"], ["Exact", "evidence grouping"]], icon: "01" },
  { name: "Verse", outcome: "Branch behaviour, not infrastructure", image: "/images/multiverse/verse.png", stats: [["SHA-256", "immutable history"], ["3-way", "behaviour merges"]], icon: "02" },
  { name: "Passport", outcome: "Carry intent across products", image: "/images/multiverse/passport.png", stats: [["Ed25519", "signed identity"], ["SFIP", "capability mapping"]], icon: "03" },
];
const heading = "See every reality your code can become.".split(" ");

export function ResultsSection() {
  return <section id="architecture" className={styles.section} aria-labelledby="results-heading"><div className={styles.frame}>
    <header className={styles.header}><span>MULTIVERSE / FROM FLAGS TO BEHAVIOUR</span><h2 id="results-heading">{heading.map((word,index)=><span key={`${word}-${index}`} style={{"--word":index} as React.CSSProperties}>{word}&nbsp;</span>)}</h2><p>Atlas proves what configurations do. Verse preserves the realities you choose.<br/>Passport carries signed intent into every compatible application.</p><i/></header>
    <div className={styles.cards}>{results.map((result,index)=><article key={result.name} className={styles.card} style={{"--card":index} as React.CSSProperties}><div className={styles.cardHead}><div><h3>{result.name}</h3><p>{result.outcome}</p></div><b>{result.icon}</b></div><div className={styles.stats}>{result.stats.map(([number,label])=><div key={number}><strong>{number}</strong><span>{label}</span></div>)}</div><div className={styles.photoStack}><i/><i/><figure><img data-reveal-image src={result.image} alt={`${result.name} behavioural infrastructure concept`}/></figure></div></article>)}</div>
    <button className={styles.more} type="button">Explore the architecture <span>↗</span></button>
  </div></section>;
}
