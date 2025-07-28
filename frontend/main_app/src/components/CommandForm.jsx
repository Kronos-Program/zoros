import React, { useState } from 'react';

// JSDoc for props type hinting
/**
 * @param {{ spec: any, onRun: (cmd: string, args: Record<string, any>) => void }} props
 */
export function CommandForm(props) {
  const [state, setState] = useState(() => {
    const init = {};
    props.spec.params.forEach((p) => {
      if (p.default !== undefined) init[p.name] = p.default;
    });
    return init;
  });

  return (
    <div style={{ padding: '8px 0' }}>
      {props.spec.params.map((p) => (
        <div key={p.name} style={{ marginBottom: 8 }}>
          <label>
            {p.name}
            <input
              type={p.type === 'number' ? 'number' : 'text'}
              value={state[p.name] || ''}
              onChange={(e) =>
                setState((s) => ({ ...s, [p.name]: e.target.value }))
              }
            />
          </label>
        </div>
      ))}
      <button onClick={() => props.onRun(props.spec.command, state)}>Run</button>
    </div>
  );
}
