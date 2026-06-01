import React, { useState, useEffect, useCallback } from 'react';

// ── Status badge ──────────────────────────────────────────────────────────

const STATUS_LABELS = {
  idle: '等待中',
  running: '进行中',
  completed: '已完成',
  interrupted: '已中断',
  failed: '失败',
  applied: '已应用',
};

const STATUS_COLORS = {
  running: '#8b5cf6',
  completed: '#10b981',
  interrupted: '#f59e0b',
  failed: '#ef4444',
  applied: '#3b82f6',
  idle: '#6b7280',
};

function StatusBadge({ status }) {
  const color = STATUS_COLORS[status] || '#6b7280';
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: 10,
        fontSize: 11,
        fontWeight: 600,
        color: '#fff',
        background: color,
      }}
    >
      {STATUS_LABELS[status] || status}
    </span>
  );
}

// ── Score bar ─────────────────────────────────────────────────────────────

function ScoreBar({ score, max = 10 }) {
  const pct = Math.min(100, Math.max(0, (score / max) * 100));
  const color = score >= 8 ? '#10b981' : score >= 6 ? '#f59e0b' : '#ef4444';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div
        style={{
          flex: 1,
          height: 6,
          borderRadius: 3,
          background: '#374151',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            borderRadius: 3,
            background: color,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
      <span style={{ fontSize: 12, fontWeight: 700, color, minWidth: 32, textAlign: 'right' }}>
        {score.toFixed(1)}
      </span>
    </div>
  );
}

// ── Evolution timeline ────────────────────────────────────────────────────

function EvolutionTimeline({ logs, bestScore }) {
  const [expanded, setExpanded] = useState(false);
  const scoredLogs = (logs || [])
    .filter((l) => l.score != null)
    .sort((a, b) => (a.round || 0) - (b.round || 0));

  if (scoredLogs.length === 0) {
    return (
      <div style={{ color: '#9ca3af', fontSize: 13, padding: '8px 0' }}>
        暂无演化日志
      </div>
    );
  }

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          background: 'transparent',
          border: 'none',
          color: '#a78bfa',
          cursor: 'pointer',
          fontSize: 13,
          padding: '4px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 4,
        }}
      >
        <span style={{ transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s', display: 'inline-block' }}>
          ▶
        </span>
        演化历程 ({scoredLogs.length} 轮关键迭代)
      </button>

      {expanded && (
        <div style={{ marginTop: 8, position: 'relative', paddingLeft: 24 }}>
          {/* Timeline line */}
          <div
            style={{
              position: 'absolute',
              left: 8,
              top: 4,
              bottom: 4,
              width: 2,
              background: '#374151',
            }}
          />
          {scoredLogs.map((log, i) => {
            const isBest = log.score === bestScore;
            return (
              <div
                key={i}
                style={{
                  position: 'relative',
                  marginBottom: 12,
                  paddingLeft: 12,
                }}
              >
                {/* Timeline dot */}
                <div
                  style={{
                    position: 'absolute',
                    left: -20,
                    top: 4,
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: isBest ? '#fbbf24' : '#6b7280',
                    border: isBest ? '2px solid #f59e0b' : '2px solid #4b5563',
                  }}
                />
                <div style={{ fontSize: 12, color: '#d1d5db' }}>
                  <span style={{ fontWeight: 600 }}>
                    第 {log.round} 轮
                  </span>
                  {' · '}
                  <span style={{ color: '#9ca3af' }}>{log.role}</span>
                  {' — '}
                  <span style={{ color: isBest ? '#fbbf24' : '#e5e7eb', fontWeight: isBest ? 700 : 400 }}>
                    {log.score.toFixed(1)}
                  </span>
                  {isBest && (
                    <span style={{ color: '#fbbf24', marginLeft: 4, fontSize: 11 }}>
                      ★ 最佳
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Dream detail card ─────────────────────────────────────────────────────

function DreamDetail({ dream, iterations, onApply, onDelete, onClose }) {
  if (!dream) return null;

  const applied = dream.status === 'applied';
  const handleApply = async () => {
    if (onApply) await onApply(dream.id);
  };
  const handleDelete = async () => {
    if (onDelete && window.confirm('确定要删除这个梦境吗？')) {
      await onDelete(dream.id);
      if (onClose) onClose();
    }
  };

  return (
    <div style={{ padding: '16px 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#9ca3af',
              cursor: 'pointer',
              fontSize: 20,
              padding: 0,
              marginRight: 12,
            }}
          >
            ←
          </button>
          <h2 style={{ display: 'inline', fontSize: 18, color: '#f9fafb', margin: 0 }}>
            {dream.motif || '未知母题'}
          </h2>
        </div>
        <StatusBadge status={dream.status} />
      </div>

      {/* Meta row */}
      <div style={{ display: 'flex', gap: 20, fontSize: 12, color: '#9ca3af', marginBottom: 16, flexWrap: 'wrap' }}>
        <span>ID: {dream.id}</span>
        <span>迭代: {dream.iterations || 0} 轮</span>
        {dream.tags && (
          <span>
            标签: {(typeof dream.tags === 'string' ? dream.tags.split(',') : dream.tags || []).join(', ') || '—'}
          </span>
        )}
      </div>

      {/* Score */}
      <div style={{ marginBottom: 20 }}>
        <ScoreBar score={dream.best_score || 0} />
      </div>

      {/* Evolution timeline */}
      <div style={{ marginBottom: 20 }}>
        <EvolutionTimeline logs={iterations || []} bestScore={dream.best_score || 0} />
      </div>

      {/* Solution content (simplified markdown rendering) */}
      <div
        style={{
          background: '#111827',
          borderRadius: 8,
          padding: 16,
          maxHeight: 400,
          overflow: 'auto',
          fontSize: 13,
          lineHeight: 1.7,
          color: '#e5e7eb',
          whiteSpace: 'pre-wrap',
          fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        }}
      >
        {/* Show outcome_path content if available, otherwise ID hint */}
        <div style={{ color: '#6b7280', marginBottom: 12 }}>
          📄 {dream.outcome_path || '方案路径未记录'}
        </div>
        {dream.convergence_reason && (
          <div style={{ color: '#6b7280', marginBottom: 12 }}>
            结束原因: {dream.convergence_reason}
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
        {!applied && (
          <button
            onClick={handleApply}
            style={{
              padding: '8px 16px',
              borderRadius: 6,
              border: 'none',
              background: '#10b981',
              color: '#fff',
              fontWeight: 600,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            ✓ 标记已应用
          </button>
        )}
        {applied && (
          <span style={{ color: '#10b981', fontSize: 13, padding: '8px 0' }}>
            ✓ 已应用
          </span>
        )}
        <button
          onClick={handleDelete}
          style={{
            padding: '8px 16px',
            borderRadius: 6,
            border: '1px solid #ef4444',
            background: 'transparent',
            color: '#ef4444',
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          删除
        </button>
        {dream.outcome_path && (
          <button
            onClick={() => {
              // Attempt to open via Obsidian URI
              const vaultPath = dream.outcome_path || '';
              const uri = `obsidian://open?path=${encodeURIComponent(vaultPath)}`;
              window.open(uri, '_blank');
            }}
            style={{
              padding: '8px 16px',
              borderRadius: 6,
              border: '1px solid #a78bfa',
              background: 'transparent',
              color: '#a78bfa',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            在 Obsidian 中打开
          </button>
        )}
      </div>
    </div>
  );
}

// ── Dream list row ────────────────────────────────────────────────────────

function DreamRow({ dream, onClick, isSelected }) {
  const date = dream.created_at || dream.start_time || '';
  const displayDate = date ? new Date(date).toLocaleDateString('zh-CN', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  }) : '';

  return (
    <div
      onClick={() => onClick(dream.id)}
      style={{
        padding: '10px 16px',
        borderBottom: '1px solid #1f2937',
        cursor: 'pointer',
        background: isSelected ? 'rgba(139,92,246,0.1)' : 'transparent',
        transition: 'background 0.15s',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}
    >
      <StatusBadge status={dream.status} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            color: '#f3f4f6',
            fontWeight: 500,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {dream.motif || '未命名梦境'}
        </div>
        <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>
          {displayDate}
          {' · '}
          {dream.iterations || 0} 轮
          {dream.tags ? ` · ${dream.tags}` : ''}
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <ScoreBar score={dream.best_score || 0} />
      </div>
    </div>
  );
}

// ── Settings form ─────────────────────────────────────────────────────────

function SettingsForm({ config, onSave, onStartDream }) {
  const [form, setForm] = useState({ ...config });
  const [customMotif, setCustomMotif] = useState('');

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const handleSave = () => {
    if (onSave) onSave(form);
  };

  const handleStart = () => {
    if (onStartDream) onStartDream(customMotif || undefined);
    setCustomMotif('');
  };

  return (
    <div style={{ padding: 16 }}>
      {/* Manual trigger */}
      <div style={{ marginBottom: 20, padding: 16, background: '#111827', borderRadius: 8 }}>
        <h4 style={{ color: '#f9fafb', fontSize: 14, margin: '0 0 12px' }}>立即做梦</h4>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="text"
            value={customMotif}
            onChange={(e) => setCustomMotif(e.target.value)}
            placeholder="输入自定义母题（留空则自动生成）"
            style={{
              flex: 1,
              padding: '8px 12px',
              borderRadius: 6,
              border: '1px solid #374151',
              background: '#1f2937',
              color: '#f3f4f6',
              fontSize: 13,
              outline: 'none',
            }}
          />
          <button
            onClick={handleStart}
            style={{
              padding: '8px 16px',
              borderRadius: 6,
              border: 'none',
              background: '#8b5cf6',
              color: '#fff',
              fontWeight: 600,
              fontSize: 13,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            开始做梦
          </button>
        </div>
      </div>

      {/* Settings fields */}
      {[
        { key: 'enabled', label: '启用梦境', type: 'checkbox' },
        { key: 'idle_timeout_seconds', label: '空闲超时（秒）', type: 'number', min: 60, max: 7200, step: 60,
          display: (v) => `${Math.round(v / 60)} 分钟` },
        { key: 'max_iterations', label: '最大迭代轮数', type: 'number', min: 10, max: 500, step: 10 },
        { key: 'convergence_rounds', label: '收敛判定轮数', type: 'number', min: 5, max: 100, step: 5 },
        { key: 'max_dream_duration_minutes', label: '最大梦境时长（分钟）', type: 'number', min: 5, max: 480, step: 5 },
        { key: 'cloud_enabled', label: '允许云端 API', type: 'checkbox' },
        { key: 'obsidian_vault_path', label: 'Obsidian Vault 路径', type: 'text', placeholder: '/home/user/notes' },
        { key: 'local_model', label: '本地模型', type: 'text', placeholder: 'deepseek-coder:33b' },
        { key: 'daily_token_limit', label: '每日 Token 上限', type: 'number', min: 1000, max: 10000000, step: 1000 },
        { key: 'notification', label: '启用通知', type: 'checkbox' },
        { key: 'resource_cpu_threshold', label: 'CPU 阈值 (%)', type: 'number', min: 10, max: 100, step: 5 },
        { key: 'resource_memory_threshold', label: '内存阈值 (%)', type: 'number', min: 10, max: 100, step: 5 },
      ].map((field) => (
        <div
          key={field.key}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 0',
            borderBottom: '1px solid #1f2937',
          }}
        >
          <label style={{ color: '#d1d5db', fontSize: 13, flex: 1 }}>
            {field.label}
            {field.display && (
              <span style={{ color: '#6b7280', marginLeft: 6, fontSize: 11 }}>
                ({field.display(form[field.key])})
              </span>
            )}
          </label>
          {field.type === 'checkbox' ? (
            <input
              type="checkbox"
              checked={!!form[field.key]}
              onChange={(e) => update(field.key, e.target.checked)}
              style={{ accentColor: '#8b5cf6' }}
            />
          ) : (
            <input
              type={field.type}
              value={form[field.key] ?? ''}
              onChange={(e) => update(field.key, field.type === 'number' ? Number(e.target.value) : e.target.value)}
              placeholder={field.placeholder}
              min={field.min}
              max={field.max}
              step={field.step}
              style={{
                width: 120,
                padding: '6px 10px',
                borderRadius: 6,
                border: '1px solid #374151',
                background: '#1f2937',
                color: '#f3f4f6',
                fontSize: 12,
                textAlign: field.type === 'number' ? 'right' : 'left',
                outline: 'none',
              }}
            />
          )}
        </div>
      ))}

      <button
        onClick={handleSave}
        style={{
          marginTop: 20,
          width: '100%',
          padding: '10px 0',
          borderRadius: 8,
          border: 'none',
          background: '#10b981',
          color: '#fff',
          fontWeight: 600,
          fontSize: 14,
          cursor: 'pointer',
        }}
      >
        保存设置
      </button>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────

/**
 * DreamPanel — dream log, detail, and settings panel (PRD §6.5.1, §9.2).
 *
 * Props:
 *   history     - array of dream summary objects
 *   config      - current dreamweaver config object
 *   status      - current DreamService status
 *   apiBase     - base URL for API calls (default '/dream')
 *   onClose     - callback to close/minimize panel
 */
export default function DreamPanel({
  history: initialHistory = [],
  config: initialConfig = {},
  status = {},
  apiBase = '/dream',
  onClose,
}) {
  const [tab, setTab] = useState('log'); // 'log' | 'settings'
  const [history, setHistory] = useState(initialHistory);
  const [config, setConfig] = useState(initialConfig);
  const [selectedId, setSelectedId] = useState(null);
  const [dreamDetail, setDreamDetail] = useState(null);
  const [iterations, setIterations] = useState([]);
  const [loading, setLoading] = useState(false);

  // Sync with external history updates
  useEffect(() => {
    setHistory(initialHistory);
  }, [initialHistory]);

  // Fetch dream detail
  const fetchDetail = useCallback(async (dreamId) => {
    setLoading(true);
    try {
      const resp = await fetch(`${apiBase}/${dreamId}`);
      if (resp.ok) {
        const data = await resp.json();
        setDreamDetail(data.dream);
        setIterations(data.iterations || []);
      }
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  // Refresh history
  const refreshHistory = useCallback(async () => {
    try {
      const resp = await fetch(`${apiBase}/history?limit=50`);
      if (resp.ok) {
        const data = await resp.json();
        setHistory(data.items || []);
      }
    } catch {
      // silently fail
    }
  }, [apiBase]);

  // Apply dream
  const applyDream = useCallback(async (dreamId) => {
    try {
      await fetch(`${apiBase}/${dreamId}/apply`, { method: 'POST' });
      await refreshHistory();
      if (dreamDetail && dreamDetail.id === dreamId) {
        setDreamDetail({ ...dreamDetail, status: 'applied' });
      }
    } catch {
      // silently fail
    }
  }, [apiBase, refreshHistory, dreamDetail]);

  // Delete dream
  const deleteDream = useCallback(async (dreamId) => {
    try {
      await fetch(`${apiBase}/${dreamId}`, { method: 'DELETE' });
      await refreshHistory();
      if (selectedId === dreamId) {
        setSelectedId(null);
        setDreamDetail(null);
      }
    } catch {
      // silently fail
    }
  }, [apiBase, refreshHistory, selectedId]);

  // Save config
  const saveConfig = useCallback(async (newConfig) => {
    setConfig(newConfig);
    // In a real integration, this would POST to the backend
    // For now, just update local state
  }, []);

  // Start manual dream
  const startDream = useCallback(async (motif) => {
    try {
      await fetch(`${apiBase}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ motif: motif || null }),
      });
    } catch {
      // silently fail
    }
  }, [apiBase]);

  // Sort state
  const [sortBy, setSortBy] = useState('created_at');
  const sortedHistory = [...history].sort((a, b) => {
    if (sortBy === 'score') return (b.best_score || 0) - (a.best_score || 0);
    if (sortBy === 'iterations') return (b.iterations || 0) - (a.iterations || 0);
    // default: date
    return (b.created_at || '').localeCompare(a.created_at || '');
  });

  // Status display
  const currentStatus = status.status || 'idle';
  const isRunning = currentStatus === 'running';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#0f172a',
        color: '#f9fafb',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        borderLeft: '1px solid #1e293b',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          borderBottom: '1px solid #1e293b',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: '#f9fafb' }}>
            🌙 梦境
          </h3>
          <StatusBadge status={currentStatus} />
          {isRunning && (
            <span style={{ fontSize: 12, color: '#a78bfa' }}>
              第 {status.current_round || 0}/{status.max_rounds || '?'} 轮
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {/* Interrupt button (only when running) */}
          {isRunning && (
            <button
              onClick={async () => {
                await fetch(`${apiBase}/stop`, { method: 'POST' });
              }}
              style={{
                padding: '6px 12px',
                borderRadius: 6,
                border: '1px solid #ef4444',
                background: 'transparent',
                color: '#ef4444',
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              中断
            </button>
          )}
          {onClose && (
            <button
              onClick={onClose}
              style={{
                padding: '6px 12px',
                borderRadius: 6,
                border: '1px solid #374151',
                background: 'transparent',
                color: '#9ca3af',
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #1e293b' }}>
        {['log', 'settings'].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              flex: 1,
              padding: '10px 0',
              background: 'transparent',
              border: 'none',
              borderBottom: tab === t ? '2px solid #8b5cf6' : '2px solid transparent',
              color: tab === t ? '#f9fafb' : '#6b7280',
              fontSize: 13,
              fontWeight: tab === t ? 600 : 400,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {t === 'log' ? '梦境日志' : '设置'}
          </button>
        ))}
      </div>

      {/* Content area */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {tab === 'log' && !selectedId && (
          <>
            {/* Sort bar */}
            <div style={{ padding: '8px 16px', display: 'flex', gap: 8, alignItems: 'center', borderBottom: '1px solid #1f2937' }}>
              <span style={{ fontSize: 12, color: '#6b7280' }}>排序:</span>
              {[
                { key: 'created_at', label: '日期' },
                { key: 'score', label: '评分' },
                { key: 'iterations', label: '迭代' },
              ].map((opt) => (
                <button
                  key={opt.key}
                  onClick={() => setSortBy(opt.key)}
                  style={{
                    padding: '3px 10px',
                    borderRadius: 12,
                    border: 'none',
                    background: sortBy === opt.key ? '#8b5cf6' : '#1f2937',
                    color: sortBy === opt.key ? '#fff' : '#9ca3af',
                    fontSize: 11,
                    cursor: 'pointer',
                  }}
                >
                  {opt.label}
                </button>
              ))}
              <button
                onClick={refreshHistory}
                style={{
                  marginLeft: 'auto',
                  padding: '3px 10px',
                  borderRadius: 12,
                  border: 'none',
                  background: '#1f2937',
                  color: '#9ca3af',
                  fontSize: 11,
                  cursor: 'pointer',
                }}
              >
                刷新
              </button>
            </div>

            {/* Dream list */}
            {sortedHistory.length === 0 ? (
              <div style={{ padding: 40, textAlign: 'center', color: '#6b7280', fontSize: 13 }}>
                还没有梦境记录。
                <br />
                <span style={{ fontSize: 12 }}>
                  系统空闲时会自动开始，或前往「设置」手动触发
                </span>
              </div>
            ) : (
              sortedHistory.map((dream) => (
                <DreamRow
                  key={dream.id}
                  dream={dream}
                  onClick={(id) => {
                    setSelectedId(id);
                    fetchDetail(id);
                  }}
                  isSelected={selectedId === dream.id}
                />
              ))
            )}
          </>
        )}

        {tab === 'log' && selectedId && (
          loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: '#6b7280' }}>加载中…</div>
          ) : (
            <DreamDetail
              dream={dreamDetail}
              iterations={iterations}
              onApply={applyDream}
              onDelete={deleteDream}
              onClose={() => {
                setSelectedId(null);
                setDreamDetail(null);
                setIterations([]);
              }}
            />
          )
        )}

        {tab === 'settings' && (
          <SettingsForm
            config={config}
            onSave={saveConfig}
            onStartDream={startDream}
          />
        )}
      </div>
    </div>
  );
}
