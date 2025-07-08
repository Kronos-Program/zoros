import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import React from 'react';
import { CommandForm } from '../zoros-frontend/dist/components/CommandForm.js';

const spec = {
  command: 'echo-test',
  params: [{ name: 'text', type: 'str', required: true, help: 'Text to echo' }]
};

test('CommandForm renders input', () => {
  const html = renderToStaticMarkup(
    React.createElement(CommandForm, { spec, onRun: () => {} })
  );
  assert.ok(html.includes('input'));
});
