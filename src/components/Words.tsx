export function Words({ text, className }: { text: string; className?: string }) {
  return <>{text.split(" ").map((word, i) => <span key={`${word}-${i}`} className={className} data-word>{word}{i < text.split(" ").length - 1 ? " " : ""}</span>)}</>;
}
