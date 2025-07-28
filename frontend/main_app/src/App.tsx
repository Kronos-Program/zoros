// See architecture: docs/zoros_architecture.md#ui-blueprint
import IntakeWidget from './components/IntakeWidget';
import QuickTaskLauncher from './components/QuickTaskLauncher';
import FiberCardViewer from './components/FiberCardViewer.js';
import { useZorosStore } from './hooks/useZorosStore.js';
import FeatureSidebar from './components/FeatureSidebar';
import StatusBar from './components/StatusBar';
import CoAuthorPanel from './routes/coauthor/CoAuthorPanel';
import React, { useEffect, useState } from 'react';
import { CommandForm, CommandSpec } from './components/CommandForm.jsx';
// @ts-ignore: Ensure JSX runtime is available
import 'react/jsx-runtime';

async function fetchJson(url: string, opts?: RequestInit, onError?: () => void) {
  const resp = await fetch(url, opts);
  if (!resp.ok) {
    onError && onError();
    throw new Error("Request failed");
  }
  return resp.json();
}

export default function App() {
  if (window.location.pathname === '/coauthor') {
    return <CoAuthorPanel />;
  }
  const [schema, setSchema] = useState<CommandSpec[]>([]);
  const [errorInfo, setErrorInfo] = useState<any | null>(null);
  const [suggestion, setSuggestion] = useState("");
  const [diagnostics, setDiagnostics] = useState<any[]>([]);
  const { selectedThread, setSelectedThread } = useZorosStore();

  useEffect(() => {
    fetch('/api/cli/schema')
      .then((r) => r.json())
      .then(setSchema)
      .catch(() => setSchema([]));
  }, []);

  const run = (cmd: string, args: Record<string, any>) => {
    fetch('/api/cli/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: cmd, args }),
    })
      .then((r) => r.json())
      .then((d) => alert(d.stdout || d.stderr));
  };

  const runDiagnostics = async () => {
    try {
      const data = await fetchJson("/api/diagnostics/run", {}, () => setErrorInfo({}));
      setDiagnostics(data);
    } catch {
      /* handled */
    }
  };

  const reportBug = async () => {
    const err = await fetchJson("/api/errors/latest");
    const res = await fetchJson("/api/errors/suggest_fix", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(err),
    });
    setSuggestion(res.suggestion);
  };

  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex flex-1">
        <FeatureSidebar />
        <main className="flex-1 p-2 flex flex-col gap-2">
          <IntakeWidget />
          <QuickTaskLauncher />
          <div className="self-end">
            <label className="mr-1 text-sm">View:</label>
            <select
              className="border p-1 text-sm"
              value={selectedThread || ''}
              onChange={(e) =>
                setSelectedThread(e.target.value || null)
              }
            >
              <option value="">Inbox</option>
              <option value="thread-a">Thread A</option>
            </select>
          </div>
          {/* Fiber viewer */}
          <FiberCardViewer />
          {/* Render command forms below the main widgets */}
          {schema.map((spec: CommandSpec) => (
            <details key={spec.command} style={{ marginBottom: 16 }}>
              <summary>{spec.command}</summary>
              <CommandForm spec={spec} onRun={run} />
            </details>
          ))}
          {/* Diagnostics and Bug Reporting UI */}
          <section style={{ marginTop: 24 }}>
            <button onClick={runDiagnostics}>Run Self-Test</button>
            {diagnostics.length > 0 && (
              <table style={{ marginTop: 12 }}>
                <thead>
                  <tr>
                    <th>Check</th>
                    <th>Status</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {diagnostics.map((c, i) => (
                    <tr key={i}>
                      <td>{c.check}</td>
                      <td>{c.status}</td>
                      <td>{c.details}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {errorInfo && (
              <div role="dialog" style={{ marginTop: 16 }}>
                <p>Zoros encountered an unexpected problem. Click ‘Report Bug’ to get a suggested fix.</p>
                <button onClick={reportBug}>Report Bug</button>
                {suggestion && (
                  <div style={{ marginTop: 8 }}>
                    <textarea value={suggestion} readOnly style={{ width: '100%', minHeight: 60 }} />
                    <a href="vscode://file/" target="_blank" rel="noreferrer">
                      Apply Fix
                    </a>
                  </div>
                )}
              </div>
            )}
          </section>
        </main>
      </div>
      <StatusBar />
    </div>
  );
}


