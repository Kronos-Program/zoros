import { test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import FiberCard from '../zoros-frontend/dist/components/FiberCard.js';

test('FiberCard renders fields', () => {
  const fiber = {
    id: '1',
    content: 'hello world example',
    tags: 'tag1 tag2',
    created_at: '2025-07-02T00:00:00Z',
    source: 'test',
  };
  const html = renderToStaticMarkup(React.createElement(FiberCard, { fiber }));
  assert.ok(html.includes('hello world example'));
  assert.ok(html.includes('tag1'));
});
