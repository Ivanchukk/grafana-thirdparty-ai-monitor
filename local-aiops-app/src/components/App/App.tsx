import React, { useEffect, useState } from 'react';
import { getBackendSrv } from '@grafana/runtime';
import { lastValueFrom } from 'rxjs';
import './assistant.css';

type Variables = Record<string, string | string[]>;
type Dashboard = { uid: string; title: string };
type Panel = { id: number; title: string; description: string; targets: Array<{ expr: string }> };
type Context = {
  uid: string;
  title: string;
  panels: Panel[];
  time_range: { from: string; to: string };
  selected_variables: Variables;
  variables: Array<{
    name: string;
    label: string;
    multi: boolean;
    value: string | string[];
    options: Array<{ text: string; value: string }>;
  }>;
};
type Finding = {
  title: string;
  node: string;
  peak: number;
  evidence_value?: number;
  evidence_label?: string;
  latest: number;
  unit: string;
  panel_title: string;
  panel_id: number;
  samples_affected: number;
};
type Result = {
  mode: string;
  session_id: string;
  status: string;
  answer: string;
  findings: Finding[];
  tool_calls: number;
  statistics: Array<{ count: number }>;
  trace: Array<{ tool: string; duration_ms: number; arguments: unknown; result: unknown }>;
  sources: Array<{ title: string; source: string }>;
  query_errors: Array<{ panel_title: string; error: string }>;
};
type Message = { role: 'user' | 'assistant'; text: string; result?: Result };
const proxy = '/api/plugin-proxy/local-aiops-app/backend';

async function api<T>(path: string, data?: unknown): Promise<T> {
  const response = await lastValueFrom(
    getBackendSrv().fetch<T>({ url: `${proxy}${path}`, method: data === undefined ? 'GET' : 'POST', data })
  );
  return response.data;
}

function errorText(error: unknown) {
  const e = error as { data?: { detail?: string; message?: string }; message?: string };
  return e.data?.detail || e.data?.message || e.message || 'The request failed. Check the backend connection.';
}

function measured(value: number, unit: string) {
  if (unit === 'percentunit') {
    return `${(value * 100).toFixed(2)}%`;
  }
  if (unit === 's') {
    return `${(value * 1000).toFixed(1)} ms`;
  }
  if (unit === 'bytes') {
    return `${(value / 1024 ** 3).toFixed(2)} GiB`;
  }
  return `${value.toFixed(2)}${unit === 'ops' || unit === 'reqps' ? '/s' : ''}`;
}

function Answer({ text }: { text: string }) {
  return (
    <div className="ai-answer">
      {text.split(/(https?:\/\/[^\s]+)/g).map((part, i) =>
        /^https?:\/\//.test(part) ? (
          <a key={i} href={part} target="_blank" rel="noreferrer">
            {part}
          </a>
        ) : (
          <React.Fragment key={i}>{part}</React.Fragment>
        )
      )}
    </div>
  );
}

export default function App() {
  const params = new URLSearchParams(window.location.search);
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [uid, setUid] = useState(params.get('dashboard') || 'elasticsearch-demo');
  const [from, setFrom] = useState(params.get('from') || 'now-30m');
  const [to, setTo] = useState(params.get('to') || 'now');
  const [variables, setVariables] = useState<Variables>(() => {
    const selected: Variables = {};
    for (const key of Array.from(params.keys())) {
      if (key.startsWith('var-')) {
        const all = params.getAll(key);
        selected[key.slice(4)] = all.length > 1 ? all : all[0];
      }
    }
    return selected;
  });
  const [contextState, setContextState] = useState<{ key: string; value?: Context }>();
  const requestKey = JSON.stringify([uid, from, to, variables]);
  const context = contextState?.key === requestKey ? contextState.value : undefined;
  const loadingContext = contextState?.key !== requestKey;
  const [mode, setMode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [session, setSession] = useState<string>();
  const latest = [...messages].reverse().find((m) => m.result)?.result;

  useEffect(() => {
    Promise.all([api<Dashboard[]>('/dashboards'), api<{ mode: string }>('/health')])
      .then(([items, health]) => {
        setDashboards(items);
        setMode(health.mode);
      })
      .catch((e) => setError(errorText(e)));
  }, []);

  useEffect(() => {
    let active = true;
    api<Context>('/context', { dashboard_uid: uid, from_time: from, to_time: to, variables })
      .then((ctx) => {
        if (active) {
          setContextState({ key: requestKey, value: ctx });
          setError('');
        }
      })
      .catch((e) => {
        if (active) {
          setContextState({ key: requestKey });
          setError(errorText(e));
        }
      });
    return () => {
      active = false;
    };
  }, [uid, from, to, variables, requestKey]);

  async function investigate(text: string) {
    if (busy || !context) {
      return;
    }
    setError('');
    setBusy(true);
    setQuestion('');
    setMessages((current) => [...current, { role: 'user', text }]);
    try {
      const result = await api<Result>('/chat', {
        dashboard_uid: uid,
        from_time: from,
        to_time: to,
        variables: context.selected_variables,
        question: text,
        session_id: session,
      });
      setSession(result.session_id);
      setMode(result.mode);
      setMessages((current) => [...current, { role: 'assistant', text: result.answer, result }]);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="aiops">
      <header className="ai-header">
        <div>
          <div className="ai-eyebrow">
            <span className="ai-dot" /> LOCAL OPERATIONS / AI ASSISTANT
          </div>
          <h1>Understand what your metrics are saying.</h1>
          <p>Investigate your dashboards with evidence from live queries.</p>
        </div>
        <div className="ai-mode">
          {mode === 'mock' ? 'MOCK AI · DEVELOPMENT' : mode === 'live' ? 'INTERNAL AI · LIVE' : 'CONNECTING'}
        </div>
      </header>
      {mode === 'mock' && (
        <div className="ai-mock" role="note">
          Mock model enabled. Tool calls and metric analysis are real; investigation decisions and response wording are
          deterministic.
        </div>
      )}
      <div className="ai-layout">
        <aside className="ai-context">
          <div className="ai-section-label">INVESTIGATION CONTEXT</div>
          <label htmlFor="ai-dashboard">Dashboard</label>
          <select
            id="ai-dashboard"
            value={uid}
            disabled={busy}
            onChange={(e) => {
              setUid(e.target.value);
              setVariables({});
            }}
          >
            {!dashboards.some((d) => d.uid === uid) && <option value={uid}>{uid}</option>}
            {dashboards.map((d) => (
              <option key={d.uid} value={d.uid}>
                {d.title}
              </option>
            ))}
          </select>
          <div className="ai-time">
            <label htmlFor="ai-from">
              From
              <input
                id="ai-from"
                value={from}
                disabled={busy}
                onChange={(e) => setFrom(e.target.value)}
                placeholder="now-30m or ISO date"
              />
            </label>
            <label htmlFor="ai-to">
              To
              <input
                id="ai-to"
                value={to}
                disabled={busy}
                onChange={(e) => setTo(e.target.value)}
                placeholder="now or ISO date"
              />
            </label>
          </div>
          <div className="ai-presets">
            {['5m', '30m', '1h', '6h'].map((range) => (
              <button
                key={range}
                disabled={busy}
                onClick={() => {
                  setFrom(`now-${range}`);
                  setTo('now');
                }}
              >
                {range}
              </button>
            ))}
          </div>
          {context?.variables.map((v) => (
            <div key={v.name} className="ai-variable">
              <label htmlFor={`ai-var-${v.name}`}>{v.label}</label>
              {v.options.length ? (
                <select
                  id={`ai-var-${v.name}`}
                  multiple={v.multi}
                  size={v.multi ? Math.min(4, v.options.length) : undefined}
                  disabled={busy}
                  value={v.multi ? (Array.isArray(v.value) ? v.value : [v.value]) : String(v.value)}
                  onChange={(e) =>
                    setVariables((current) => ({
                      ...current,
                      [v.name]: v.multi
                        ? Array.from(e.target.selectedOptions, (o) => o.value).filter(
                            (x) => x !== '$__all' || e.target.selectedOptions.length === 1
                          )
                        : e.target.value,
                    }))
                  }
                >
                  {v.options.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.text}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id={`ai-var-${v.name}`}
                  disabled={busy}
                  value={String(v.value)}
                  onChange={(e) => setVariables((current) => ({ ...current, [v.name]: e.target.value }))}
                />
              )}
            </div>
          ))}
          {loadingContext ? (
            <p className="ai-muted" role="status">
              Loading dashboard context…
            </p>
          ) : (
            context && (
              <>
                <div className="ai-context-meta">
                  <span>{context.panels.length} panels discovered</span>
                  <code>{context.uid}</code>
                </div>
                <a
                  className="ai-dashboard-link"
                  href={`/d/${uid}?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}${Object.entries(
                    context.selected_variables
                  )
                    .flatMap(([key, value]) =>
                      (Array.isArray(value) ? value : [value]).map(
                        (x) => `&var-${encodeURIComponent(key)}=${encodeURIComponent(x)}`
                      )
                    )
                    .join('')}`}
                >
                  Open dashboard ↗
                </a>
                <details className="ai-panels">
                  <summary>Panels & query context</summary>
                  {context.panels.map((p) => (
                    <div key={p.id}>
                      <strong>
                        {p.id}. {p.title}
                      </strong>
                      <p>{p.description}</p>
                      {p.targets.map((t, i) => (
                        <code key={i}>{t.expr}</code>
                      ))}
                    </div>
                  ))}
                </details>
              </>
            )
          )}
          <div className="ai-scope">
            <span>READ-ONLY INVESTIGATION</span>
            <p>Queries, statistical analysis and local documentation. Recommendations stay with you.</p>
          </div>
        </aside>
        <section className="ai-workspace">
          <div className="ai-toolbar">
            <div>
              <div className="ai-section-label">DASHBOARD INVESTIGATION</div>
              <h2>{context?.title || 'Select a dashboard'}</h2>
            </div>
            <button
              className="ai-primary"
              disabled={busy || !context || loadingContext}
              onClick={() => investigate('Is there anything wrong with my Elasticsearch cluster?')}
            >
              {busy ? 'Investigating…' : '✦ Analyze Dashboard'}
            </button>
          </div>
          <div className="ai-summary">
            <div>
              <span>Assessment</span>
              <strong className={`ai-status-${latest?.status}`}>
                {latest?.status === 'warning'
                  ? 'Warning'
                  : latest?.status === 'healthy'
                    ? 'Within demo limits'
                    : latest?.status === 'incomplete'
                      ? 'Incomplete data'
                      : 'Ready to investigate'}
              </strong>
            </div>
            <div>
              <span>Findings</span>
              <strong>{latest ? latest.findings.length : '—'}</strong>
            </div>
            <div>
              <span>Tool executions</span>
              <strong>{latest?.tool_calls ?? '—'}</strong>
            </div>
            <div>
              <span>Data source</span>
              <strong>Grafana queries</strong>
            </div>
          </div>
          {error && (
            <div className="ai-error" role="alert">
              {error}
            </div>
          )}
          <div className="ai-conversation" aria-live="polite">
            {!messages.length && (
              <div className="ai-empty">
                <div className="ai-orbit">✦</div>
                <h3>Start with a question. Follow the evidence.</h3>
                <p>
                  The assistant discovers panels, queries their metrics, compares related signals and retrieves
                  technical context.
                </p>
                <div className="ai-prompts">
                  {[
                    'Why is search latency increasing?',
                    'Check JVM heap and garbage collection.',
                    'Compare the health of my nodes.',
                  ].map((text) => (
                    <button key={text} disabled={!context || busy} onClick={() => investigate(text)}>
                      {text} <span>↗</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <article key={i} className={`ai-message ai-${m.role}`}>
                <div className="ai-message-role">
                  {m.role === 'user' ? 'YOU' : `OPERATIONS ASSISTANT · ${m.result?.mode === 'mock' ? 'MOCK' : 'LIVE'}`}
                </div>
                {m.result && m.result.findings.length > 0 && (
                  <div className="ai-findings">
                    {m.result.findings.map((f, j) => (
                      <div className="ai-finding" key={j}>
                        <span>{f.node}</span>
                        <strong>{f.title}</strong>
                        <b>
                          {measured(f.evidence_value ?? f.peak, f.unit)} <small>{f.evidence_label || 'peak'}</small>
                        </b>
                        <p>
                          {f.panel_title} · panel {f.panel_id} · {f.samples_affected} samples
                        </p>
                      </div>
                    ))}
                  </div>
                )}
                <Answer text={m.text} />
                {m.result && (
                  <details className="ai-trace">
                    <summary>Investigation trace · {m.result.tool_calls} tool calls</summary>
                    {m.result.trace.map((t, j) => (
                      <details key={j}>
                        <summary>
                          <code>{t.tool}</code>
                          <span>{t.duration_ms} ms</span>
                        </summary>
                        <pre>{JSON.stringify({ arguments: t.arguments, result: t.result }, null, 2)}</pre>
                      </details>
                    ))}
                  </details>
                )}
              </article>
            ))}
            {busy && (
              <div className="ai-progress" role="status">
                <span className="ai-dot" /> Querying panels and investigating the evidence…
              </div>
            )}
          </div>
          <form
            className="ai-composer"
            onSubmit={(e) => {
              e.preventDefault();
              if (question.trim()) {
                investigate(question.trim());
              }
            }}
          >
            <label className="ai-sr" htmlFor="ai-question">
              Ask a follow-up question
            </label>
            <textarea
              id="ai-question"
              placeholder={session ? 'Ask a follow-up about this investigation…' : 'Ask about your selected dashboard…'}
              value={question}
              disabled={busy}
              onChange={(e) => setQuestion(e.target.value)}
              rows={2}
              maxLength={4000}
            />
            <div>
              <span>
                {session
                  ? 'Follow-up questions keep this chat context.'
                  : 'Findings are grounded in the selected time range.'}
              </span>
              <button className="ai-primary" type="submit" disabled={busy || !context || !question.trim()}>
                Send ↗
              </button>
            </div>
          </form>
          {session && (
            <button
              className="ai-new"
              disabled={busy}
              onClick={() => {
                setSession(undefined);
                setMessages([]);
              }}
            >
              Start a new investigation
            </button>
          )}
        </section>
      </div>
    </main>
  );
}
