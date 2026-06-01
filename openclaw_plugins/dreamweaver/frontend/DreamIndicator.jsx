import React, { useState, useEffect, useRef, useCallback } from 'react';

// ── Moon phase icon paths (SVG arc segments) ──────────────────────────────

const MOON_PATHS = {
  // New moon: barely visible crescent
  new: {
    outer: 'M12 2 A10 10 0 1 1 12 22 A10 10 0 1 0 12 2',
    description: '新月 — 等待梦境触发',
  },
  // Waxing crescent: dream starting
  waxing: {
    outer: 'M12 2 A10 10 0 1 1 12 22 A8 10 0 1 0 12 2',
    description: '蛾眉月 — 生成母题中',
  },
  // Full moon: dreaming heavily
  full: {
    outer: 'M12 2 A10 10 0 1 1 12 22 A10 10 0 1 0 12 2',
    description: '满月 — 梦境进行中',
  },
  // Moon with halo ring: completed
  done: {
    outer: 'M12 2 A10 10 0 1 1 12 22 A10 10 0 1 0 12 2',
    description: '光环月 — 梦境已完成',
  },
  // Interrupted / failed
  interrupted: {
    outer: 'M12 2 A10 10 0 1 1 12 22 A10 10 0 1 0 12 2',
    description: '梦境已中断',
  },
  // Disabled
  off: {
    outer: 'M12 4 A8 8 0 1 1 12 20 A8 8 0 1 0 12 4',
    description: '梦境功能已关闭',
  },
};

// ── Particle field for the "dreaming" animation (PRD §9.1) ────────────────

function ParticleField({ active, count = 30 }) {
  const canvasRef = useRef(null);
  const animRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const particles = Array.from({ length: count }, () => ({
      x: Math.random() * rect.width,
      y: Math.random() * rect.height,
      r: Math.random() * 2 + 0.5,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      alpha: Math.random() * 0.5 + 0.2,
    }));

    function draw() {
      ctx.clearRect(0, 0, rect.width, rect.height);
      if (!active) {
        // Still particles, dim
        particles.forEach((p) => {
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(156, 163, 175, ${p.alpha * 0.3})`;
          ctx.fill();
        });
        return;
      }
      // Active: slow drift toward center, gentle glow
      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        // Wrap around
        if (p.x < 0) p.x = rect.width;
        if (p.x > rect.width) p.x = 0;
        if (p.y < 0) p.y = rect.height;
        if (p.y > rect.height) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(139, 92, 246, ${p.alpha})`;
        ctx.fill();
      });
    }

    function tick() {
      draw();
      animRef.current = requestAnimationFrame(tick);
    }
    tick();

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [active, count]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
      }}
    />
  );
}

// ── Main component ────────────────────────────────────────────────────────

/**
 * DreamIndicator — moon-phase status indicator (PRD §9.1, §6.5.1).
 *
 * Props:
 *   status      - "idle" | "running" | "completed" | "interrupted" | "failed" | "off"
 *   round       - current iteration round (when running)
 *   maxRounds   - max iterations
 *   motif       - current dream motif (tooltip)
 *   bestScore   - current best score
 *   onClick     - callback to open DreamPanel
 */
export default function DreamIndicator({
  status = 'idle',
  round = 0,
  maxRounds = 100,
  motif = '',
  bestScore = 0,
  onClick,
}) {
  const [hovered, setHovered] = useState(false);
  const [phase, setPhase] = useState('new');

  // Map status to moon phase
  useEffect(() => {
    const map = {
      idle: 'new',
      running: 'full',
      completed: 'done',
      interrupted: 'interrupted',
      failed: 'interrupted',
      off: 'off',
    };
    setPhase(map[status] || 'off');
  }, [status]);

  // Progress ring for running state
  const progress = maxRounds > 0 ? round / maxRounds : 0;
  const circumference = 2 * Math.PI * 14; // r=14
  const dashOffset = circumference * (1 - progress);

  const isRunning = status === 'running';
  const showScore = status === 'completed' || status === 'running';

  return (
    <div
      className="dream-indicator"
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 44,
        height: 44,
        borderRadius: '50%',
        cursor: onClick ? 'pointer' : 'default',
        background: isRunning
          ? 'radial-gradient(circle at 30% 30%, rgba(139,92,246,0.2), transparent)'
          : 'transparent',
        transition: 'background 0.6s ease',
      }}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      title={
        hovered
          ? undefined
          : MOON_PATHS[phase]?.description || '梦境指示器'
      }
    >
      {/* Particle canvas during dreaming */}
      {isRunning && <ParticleField active={isRunning} count={20} />}

      {/* Moon SVG */}
      <svg
        width="28"
        height="28"
        viewBox="0 0 24 24"
        style={{ position: 'relative', zIndex: 1 }}
      >
        {/* Moon body */}
        <path
          d={MOON_PATHS[phase]?.outer || MOON_PATHS.new.outer}
          fill={
            phase === 'off'
              ? '#6b7280'
              : isRunning
              ? '#a78bfa'
              : phase === 'done'
              ? '#fbbf24'
              : '#9ca3af'
          }
          style={{ transition: 'fill 0.5s ease' }}
        />

        {/* Progress ring (running state) */}
        {isRunning && (
          <circle
            cx="12"
            cy="12"
            r="14"
            fill="none"
            stroke="#8b5cf6"
            strokeWidth="1.5"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            strokeLinecap="round"
            style={{
              transform: 'rotate(-90deg)',
              transformOrigin: '12px 12px',
              transition: 'stroke-dashoffset 0.3s ease',
              opacity: 0.6,
            }}
          />
        )}

        {/* Halo ring for completed */}
        {phase === 'done' && (
          <circle
            cx="12"
            cy="12"
            r="15"
            fill="none"
            stroke="#fbbf24"
            strokeWidth="1"
            opacity={0.5}
          />
        )}
      </svg>

      {/* Score badge */}
      {showScore && bestScore > 0 && (
        <span
          style={{
            position: 'absolute',
            bottom: -2,
            right: -2,
            fontSize: 10,
            fontWeight: 700,
            color: '#fff',
            background: bestScore >= 8 ? '#10b981' : bestScore >= 6 ? '#f59e0b' : '#ef4444',
            borderRadius: 8,
            padding: '0 4px',
            lineHeight: '16px',
            minWidth: 20,
            textAlign: 'center',
          }}
        >
          {bestScore.toFixed(1)}
        </span>
      )}

      {/* Tooltip on hover */}
      {hovered && (
        <div
          style={{
            position: 'absolute',
            top: '110%',
            right: 0,
            background: '#1f2937',
            color: '#f9fafb',
            borderRadius: 8,
            padding: '10px 14px',
            fontSize: 12,
            lineHeight: 1.5,
            whiteSpace: 'nowrap',
            zIndex: 100,
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            pointerEvents: 'none',
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 4 }}>
            {phase === 'new' && '等待空闲…'}
            {phase === 'full' && `梦境中 · 第 ${round}/${maxRounds} 轮`}
            {phase === 'done' && `已完成 · 评分 ${bestScore.toFixed(1)}`}
            {phase === 'interrupted' && '已中断'}
            {phase === 'off' && '已关闭'}
          </div>
          {motif && (
            <div style={{ color: '#9ca3af', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {motif.length > 40 ? motif.slice(0, 40) + '…' : motif}
            </div>
          )}
          {isRunning && (
            <div style={{ marginTop: 4, color: '#a78bfa', fontSize: 11 }}>
              {Math.round(progress * 100)}% 完成
            </div>
          )}
          {onClick && (
            <div style={{ marginTop: 4, color: '#6b7280', fontSize: 11 }}>
              点击查看详情
            </div>
          )}
        </div>
      )}
    </div>
  );
}
