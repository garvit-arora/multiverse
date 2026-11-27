/** Small helpers shared by the timeline, the LED matrix and render(t) */
export const TAU = Math.PI * 2;

/** Clamp to 0 … 1 */
export const cl = (v: number) => Math.min(1, Math.max(0, v));
/** Linear interpolation from a to b by k */
export const L = (a: number, b: number, k: number) => a + (b - a) * k;
/** Smootherstep (6t⁵ − 15t⁴ + 10t³), for 0 … 1 */
export const sm = (t: number) => t * t * t * (t * (t * 6 - 15) + 10);
/** Quadratic ease in-out, for 0 … 1 */
export const eio = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
/** A fixed pseudo-random number in 0 … 1 for each integer i */
export const hash = (i: number) => {
  const s = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s);
};
