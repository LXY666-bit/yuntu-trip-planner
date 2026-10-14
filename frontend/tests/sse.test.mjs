import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

// Exercise the production parser with native Fetch streams, without a browser or network.
const source = readFileSync(new URL('../src/services/api.ts', import.meta.url), 'utf8')
const begin = source.indexOf('async function createSSEStream<')
const end = source.indexOf('\nexport async function generateTripPlanStream', begin)
const js = ts.transpileModule(source.slice(begin, end), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
const createStream = new Function(`${js}; return createSSEStream`)()
const encoder = new TextEncoder()

function response(chunks) {
  return new Response(new ReadableStream({ start(controller) {
    for (const text of chunks) controller.enqueue(encoder.encode(text))
    controller.close()
  }}))
}

test('complete across chunks delivers Unicode data and closes', async () => {
  const old = globalThis.fetch
  globalThis.fetch = async () => response([': heartbeat\n\ndata: {"type":"com', 'plete","message":"完成"}\n\n'])
  try {
    const events = []; let heartbeats = 0
    await createStream('/fixture', {}, e => events.push(e), { onHeartbeat: () => heartbeats++ })
    assert.equal(events[0].message, '完成'); assert.equal(heartbeats, 1)
  } finally { globalThis.fetch = old }
})

test('early EOF is an error, never successful completion', async () => {
  const old = globalThis.fetch
  globalThis.fetch = async () => response(['data: {"type":"progress"}\n\n'])
  try { await assert.rejects(createStream('/fixture', {}, () => {}), /尚未完成/) }
  finally { globalThis.fetch = old }
})

test('idle timeout cancelling a reader cannot masquerade as EOF success', async () => {
  const old = globalThis.fetch
  globalThis.fetch = async () => new Response(new ReadableStream())
  try { await assert.rejects(createStream('/fixture', {}, () => {}, { idleTimeout: 5 }), /断开|无响应/) }
  finally { globalThis.fetch = old }
})
