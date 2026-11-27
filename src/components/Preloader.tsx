import { Wordmark } from "./Wordmark"; import styles from "./Preloader.module.css";
export function Preloader({ count }: { count: number }) { return <div className={styles.root} data-preloader><Wordmark/><span data-counter>{String(Math.round(count)).padStart(2,"0")}%</span></div>; }
