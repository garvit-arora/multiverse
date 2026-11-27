import styles from "./LandingSections.module.css";
import { OfflineFooter } from "./OfflineFooter";

const REVIEWS = [
  { company: "Northstar Systems", role: "CTO", quote: "Verse lets our team review the behavioural change itself—not another pile of deployment infrastructure." },
  { company: "Axiom Commerce", role: "VP Engineering", quote: "Atlas showed us that one checkout screen concealed three genuinely different customer journeys." },
  { company: "Continuum Labs", role: "Chief Product Officer", quote: "Passport gives our products a shared language for intent while every application keeps control of its own policy." },
];

export function LandingSections() {
  return <>
    <section className={styles.proof} id="testimonials">
      <header><span>DESIGN PARTNERS / 03</span><h2>For teams changing behaviour,<br/>not just toggling flags.</h2></header>
      <div className={styles.reviewGrid}>{REVIEWS.map((review, index) => <article key={review.company}><span>0{index + 1}</span><blockquote>“{review.quote}”</blockquote><footer><b>{review.company}</b><small>{review.role}</small></footer></article>)}</div>
    </section>
    <OfflineFooter/>
  </>;
}
