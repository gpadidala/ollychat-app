#!/usr/bin/env node
/**
 * Suite 5: Negative / Error Cases (22 tests)
 * Tests error handling, edge cases, RBAC, and stress scenarios.
 *
 * Run: node suite5-negative.js
 */

const http = require('http');

function req(method, path, body = null, headers = {}) {
  return new Promise((resolve) => {
    const data = body ? JSON.stringify(body) : null;
    const h = { ...headers };
    if (data) { h['Content-Type'] = 'application/json'; h['Content-Length'] = Buffer.byteLength(data); }
    const r = http.request({ hostname: 'localhost', port: 8000, path, method, headers: h }, (res) => {
      let full = '';
      res.on('data', c => full += c);
      res.on('end', () => resolve({ status: res.statusCode, body: full }));
    });
    r.on('error', e => resolve({ error: e.message }));
    if (data) r.write(data); r.end();
  });
}

const tryParse = (s) => { try { return JSON.parse(s); } catch (e) { return null; } };

async function run() {
  let PASS = 0, FAIL = 0;
  const check = (cond, name) => { if (cond) { console.log(`  PASS: ${name}`); PASS++; } else { console.log(`  FAIL: ${name}`); FAIL++; } };
  console.log('═══ SUITE 5: NEGATIVE / ERROR CASES ═══\n');

  console.log('T1: Invalid tool name');
  const r1 = tryParse((await req('POST', '/api/v1/mcp/tools/call', { server_name: 'bifrost-grafana', tool_name: 'nonexistent', arguments: {} })).body);
  check(r1 && r1.ok === false, 'ok=false');
  check(r1 && !!r1.error, `Error message present`);

  console.log('\nT2: Invalid server name (graceful error)');
  const r2r = await req('POST', '/api/v1/mcp/tools/call', { server_name: 'fake-srv', tool_name: 'list_dashboards', arguments: {} });
  check(r2r.status === 200, 'HTTP 200 (graceful)');
  const r2 = tryParse(r2r.body);
  check(r2 && r2.ok === false, 'ok=false');
  check(r2 && r2.error && r2.error.includes('fake-srv'), 'Error mentions server name');

  console.log('\nT3: RBAC — viewer calling admin tool');
  const r3 = tryParse((await req('POST', '/api/v1/mcp/tools/call', { server_name: 'bifrost-grafana', tool_name: 'list_users', arguments: {} })).body);
  check(r3 && r3.ok === false, 'ok=false');
  check(r3 && r3.error && r3.error.includes('Permission'), 'Permission error');

  console.log('\nT4: Empty messages');
  const r4 = await req('POST', '/api/v1/chat', { messages: [], stream: true });
  check(r4.status === 200, 'HTTP 200 (graceful)');

  console.log('\nT5: Malformed body');
  const r5 = await req('POST', '/api/v1/chat', { not_a_field: 'bad' });
  check(r5.status === 422, 'HTTP 422 validation error');

  console.log('\nT6: Non-intent falls through to Ollama');
  const r6 = await req('POST', '/api/v1/chat', { messages: [{ role: 'user', content: 'What is SRE? Brief.' }], stream: true, max_tokens: 30 });
  check(r6.status === 200, 'HTTP 200');
  check(!r6.body.includes('tool_start'), 'No tool call');
  check(r6.body.includes('"type": "text"'), 'Text events present');

  console.log('\nT7: Skills CRUD');
  const c7 = tryParse((await req('POST', '/api/v1/skills', { name: 'Test', description: 't', category: 'general', systemPrompt: 't', tags: [] })).body);
  check(c7 && c7.ok === true, 'Skill created');
  const d7 = tryParse((await req('DELETE', '/api/v1/skills/' + c7.skill.id)).body);
  check(d7 && d7.ok === true, 'Skill deleted');

  console.log('\nT8: Rules CRUD');
  const c8 = tryParse((await req('POST', '/api/v1/rules', { name: 'Test', content: 't', scope: 'just-me', enabled: true })).body);
  check(c8 && c8.ok === true, 'Rule created');
  const d8 = tryParse((await req('DELETE', '/api/v1/rules/' + c8.rule.id)).body);
  check(d8 && d8.ok === true, 'Rule deleted');

  console.log('\nT9: PII clean text');
  const r9 = tryParse((await req('POST', '/api/v1/guardrails/scan', { text: 'clean text' })).body);
  check(r9 && r9.has_pii === false, 'Clean text: has_pii=false');

  console.log('\nT10: PII multiple types');
  const r10 = tryParse((await req('POST', '/api/v1/guardrails/scan', { text: 'Email: x@y.com, SSN: 123-45-6789, AWS: AKIAIOSFODNN7EXAMPLE' })).body);
  check(r10 && r10.has_pii === true, 'PII detected');
  const types = new Set((r10?.matches || []).map(m => m.type.split('_')[0]));
  check(types.size >= 3, `${types.size} distinct types: ${[...types].join(',')}`);

  console.log('\nT11: Concurrent requests (5x)');
  const promises = Array.from({ length: 5 }, () =>
    req('POST', '/api/v1/chat', { messages: [{ role: 'user', content: 'list datasources' }], stream: true }));
  const results = await Promise.all(promises);
  check(results.every(r => r.status === 200), `All 5 concurrent: ${results.map(r => r.status).join(',')}`);

  console.log('\nT12: Large message (10KB)');
  const big = 'x'.repeat(10000);
  const r12 = await req('POST', '/api/v1/chat', { messages: [{ role: 'user', content: big }], stream: true, max_tokens: 20 });
  check(r12.status === 200, `Large msg accepted: ${r12.status}`);

  console.log('\nT13: Unicode / emoji');
  const r13 = await req('POST', '/api/v1/chat', { messages: [{ role: 'user', content: 'Hello 👋 日本語 🎉' }], stream: true, max_tokens: 20 });
  check(r13.status === 200, 'Unicode accepted');

  console.log(`\n─────────────────────────`);
  console.log(`Suite 5 Results: ${PASS} passed, ${FAIL} failed`);
  console.log(`─────────────────────────`);
  process.exit(FAIL > 0 ? 1 : 0);
}
run();
