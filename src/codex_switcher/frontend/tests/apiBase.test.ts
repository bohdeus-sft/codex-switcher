import assert from 'node:assert/strict'
import { test } from 'node:test'

import { resolveApiBase } from '../src/apiBase.ts'

test('uses explicit API base when configured', () => {
  assert.equal(
    resolveApiBase(new URL('http://127.0.0.1:5173/'), 'http://localhost:9999'),
    'http://localhost:9999',
  )
})

test('uses local backend when frontend is opened from a file', () => {
  assert.equal(
    resolveApiBase(new URL('file:///Users/example/project/dist/index.html')),
    'http://127.0.0.1:8765',
  )
})

test('uses local backend for any Vite dev server port', () => {
  assert.equal(resolveApiBase(new URL('http://127.0.0.1:5174/')), 'http://127.0.0.1:8765')
  assert.equal(resolveApiBase(new URL('http://localhost:5173/')), 'http://127.0.0.1:8765')
})

test('uses same-origin API when frontend is served by the backend', () => {
  assert.equal(resolveApiBase(new URL('http://127.0.0.1:8765/')), '')
})
