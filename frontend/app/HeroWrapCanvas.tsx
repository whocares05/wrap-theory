"use client";

import { useEffect, useRef, useState } from "react";

type Leaf = { orbit: number; angle: number; speed: number; size: number; depth: number; color: "primary" | "accent" | "cream" };
const leaves: Leaf[] = [
  { orbit: .42, angle: .1, speed: .17, size: 26, depth: .72, color: "primary" }, { orbit: .34, angle: 1.4, speed: -.13, size: 19, depth: .46, color: "accent" },
  { orbit: .49, angle: 2.7, speed: .11, size: 22, depth: .9, color: "cream" }, { orbit: .38, angle: 3.5, speed: -.16, size: 17, depth: .55, color: "primary" },
  { orbit: .47, angle: 4.55, speed: .14, size: 23, depth: .8, color: "accent" }, { orbit: .3, angle: 5.5, speed: -.12, size: 15, depth: .4, color: "cream" },
];

function hasWebGL() {
  try { const canvas = document.createElement("canvas"); return Boolean(canvas.getContext("webgl") || canvas.getContext("experimental-webgl" as "webgl")); } catch { return false; }
}

/** Low-poly ingredient orbit for #hero-3d-wrap; no external rendering dependency. */
export default function HeroWrapCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = canvas?.parentElement;
    if (!canvas || !container || !hasWebGL()) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;
    setReady(true);
    let width = 1, height = 1, ratio = 1, frame = 0, previous = performance.now(), elapsed = 0;
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    const palette = () => {
      const styles = getComputedStyle(container);
      const variable = (name: string, fallback: string) => styles.getPropertyValue(name).trim() || fallback;
      return { primary: variable("--primary-color", "#c7f035"), accent: variable("--accent-color", "#f35b28") };
    };
    const resize = () => {
      const box = container.getBoundingClientRect(); width = Math.max(1, box.width); height = Math.max(1, box.height); ratio = Math.min(devicePixelRatio || 1, 1.5);
      canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio); ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    };
    const leaf = (x: number, y: number, radius: number, rotation: number, color: string, alpha: number) => {
      ctx.save(); ctx.translate(x, y); ctx.rotate(rotation); ctx.globalAlpha = alpha; ctx.fillStyle = color; ctx.beginPath();
      ctx.moveTo(radius, 0); ctx.quadraticCurveTo(0, -radius * .7, -radius, 0); ctx.quadraticCurveTo(0, radius * .7, radius, 0); ctx.fill();
      ctx.strokeStyle = "rgba(20,18,15,.28)"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(-radius * .72, 0); ctx.lineTo(radius * .72, 0); ctx.stroke(); ctx.restore();
    };
    const render = (now: number) => {
      const delta = Math.min((now - previous) / 1000, .05); previous = now; if (!media.matches) elapsed += delta;
      const colors = palette(), cx = width * .72, cy = height * .48, scale = Math.min(width, height) * .78;
      ctx.clearRect(0, 0, width, height); ctx.strokeStyle = "rgba(255,255,255,.16)"; ctx.lineWidth = 1;
      for (let ring = 0; ring < 2; ring++) { ctx.beginPath(); ctx.ellipse(cx, cy, scale * (.52 - ring * .12), scale * (.19 + ring * .08), -.38 + ring * .9, 0, Math.PI * 2); ctx.stroke(); }
      const ordered = leaves.map((item) => ({ ...item, position: Math.sin(item.angle + elapsed * item.speed) })).sort((a, b) => a.position - b.position);
      ordered.forEach((item) => { const angle = item.angle + elapsed * item.speed; const color = item.color === "cream" ? "#f5f0e6" : colors[item.color]; leaf(cx + Math.cos(angle) * scale * item.orbit, cy + Math.sin(angle) * scale * item.orbit * .45 - item.position * scale * .08, item.size * (.72 + item.depth * .42), angle + elapsed * .22, color, .42 + item.depth * .52); });
      ctx.save(); ctx.translate(cx, cy); ctx.rotate(-.35 + Math.sin(elapsed * .25) * .05); ctx.globalAlpha = .28; ctx.fillStyle = colors.accent; ctx.beginPath(); ctx.moveTo(-scale * .4, -scale * .08); ctx.lineTo(scale * .38, -scale * .23); ctx.lineTo(scale * .48, -scale * .08); ctx.lineTo(-scale * .28, scale * .12); ctx.fill(); ctx.fillStyle = colors.primary; ctx.beginPath(); ctx.moveTo(-scale * .28, scale * .12); ctx.lineTo(scale * .48, -scale * .08); ctx.lineTo(scale * .32, scale * .12); ctx.lineTo(-scale * .34, scale * .25); ctx.fill(); ctx.restore();
      frame = requestAnimationFrame(render);
    };
    const observer = new ResizeObserver(resize); observer.observe(container); resize(); frame = requestAnimationFrame(render);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); ctx.clearRect(0, 0, width, height); canvas.width = 1; canvas.height = 1; };
  }, []);
  return <canvas ref={canvasRef} className={`heroWrapCanvas${ready ? " is-ready" : ""}`} aria-hidden="true" />;
}
