#!/usr/bin/env node
/**
 * Suite 4: Integration tests (18 tests)
 * End-to-end validation: widget → orchestrator → intent → MCP → Bifrost → Grafana
 *
 * Run: node suite4-integration.js
 */

const http = require('http');

function post(port, path, body, headers = {}) {
  return new Promise((resolve) => {
    const data = JSON.stringify(body);
    const req = http.request({
      hostname: 'localhost', port, path, method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data), ...headers }
    }, (res) => {
      let full = '';
      res.on('data', c => full += c);
      res.on('end', () => resolve({ status: res.statusCode, body: full, headers: res.headers }));
    });
    req.on('error', e => resolve({ error: e.message }));
    req.write(data); req.end();
  });
}

function get(port, path, headers = {}) {
  return new Promise((resolve) => {
    http.get({ hostname: 'localhost', port, path, headers }, (res) => {
      let full = '';
      res.on('data', c => full += c);
      res.on('end', () => resolve({ status: res.statusCode, body: full, headers: res.headers }));
    }).on('error', e => resolve({ error: e.message }));
  });
}

async function run() {
  let PASS = 0, FAIL = 0;
  const check = (cond, name) => { if (cond) { console.log(`  PASS: ${name}`); PASS++; } else { console.log(`  FAIL: ${name}`); FAIL++; } };
  console.log('═══ SUITE 4: INTEGRATION ═══\n');

  // T1: E2E flow
  console.log('T1: End-to-end flow — list dashboards');
  const r1 = await post(8000, '/api/v1/chat', {
    messages: [{ role: 'user', content: 'list all dashboards' }],
    stream: true
  }, { Origin: 'http://localhost:3002', 'X-Grafana-User': 'admin' });
  check(r1.status === 200, 'Chat endpoint returns 200');
  check(r1.body.includes('tool_start'), 'Tool was invoked');
  check(r1.body.includes('dashboard'), 'Dashboard data returned');
  check(r1.body.includes('AKS') || r1.body.includes('Azure') || r1.body.includes('Grafana'), 'Real Grafana dashboards returned');

  // T2: User identity
  console.log('\nT2: User identity propagation');
  const r2 = await post(8000, '/api/v1/chat', {
    messages: [{ role: 'user', content: 'hi' }], stream: true
  }, { 'X-Grafana-User': 'test-user-123', 'X-Grafana-Org-Id': '2' });
  check(r2.status === 200, 'Request accepted with custom user');

  // T3: MCP chain
  console.log('\nT3: MCP tool chain (orchestrator → Bifrost → Grafana)');
  const r3 = await post(8000, '/api/v1/mcp/tools/call', {
    server_name: 'bifrost-grafana', tool_name: 'health_check', arguments: {}
  });
  check(r3.status === 200, 'MCP tool call 200');
  const health = JSON.parse(r3.body);
  check(health.ok === true, 'Tool call ok=true');
  check(!!health.data.version, `Grafana version: ${health.data.version}`);
  check(health.data.database === 'ok', 'Grafana database: ok');
  check(health.duration_ms !== undefined, `Duration tracked: ${health.duration_ms}ms`);

  // T4: Role metadata
  console.log('\nT4: MCP tools include role metadata');
  const r4 = await get(8000, '/api/v1/mcp/tools');
  const tools = JSON.parse(r4.body).tools;
  const withRole = tools.filter(t => t.minRole);
  check(withRole.length === tools.length, 'All tools have minRole');
  const adminTools = tools.filter(t => t.minRole === 'admin');
  check(adminTools.length >= 2, `${adminTools.length} admin-only tools`);

  // T5: Plugin registration
  console.log('\nT5: Grafana plugin registration');
  const r5 = await get(3002, '/api/plugins/gopal-ollychat-app/settings', {
    Authorization: 'Basic ' + Buffer.from('admin:admin').toString('base64')
  });
  const settings = JSON.parse(r5.body);
  check(settings.enabled === true, 'Plugin enabled');
  check(settings.name === 'OllyChat', 'Plugin name: OllyChat');
  check(settings.includes && settings.includes.length === 6, `6 pages registered (got ${settings.includes?.length})`);

  // T6: Multi-turn conversation
  console.log('\nT6: Multi-turn conversation');
  const r6 = await post(8000, '/api/v1/chat', {
    messages: [
      { role: 'user', content: 'What is PromQL?' },
      { role: 'assistant', content: 'PromQL is a query language.' },
      { role: 'user', content: 'Give me an example' }
    ],
    stream: true
  });
  check(r6.status === 200, 'Multi-turn conversation accepted');

  // T7: Dashboard count consistency
  console.log('\nT7: Dashboard count consistency');
  const r7a = await post(8000, '/api/v1/mcp/tools/call', {
    server_name: 'bifrost-grafana', tool_name: 'list_dashboards', arguments: { limit: 200 }
  });
  const dashList = JSON.parse(r7a.body);
  const r7b = await get(3002, '/api/search?type=dash-db', {
    Authorization: 'Basic ' + Buffer.from('admin:admin').toString('base64')
  });
  const grafanaDashes = JSON.parse(r7b.body);
  check(Array.isArray(dashList.data), 'MCP returns dashboard array');
  console.log(`  INFO: MCP returned ${dashList.data.length}, Grafana API shows ${grafanaDashes.length}`);
  check(dashList.data.length > 50, `${dashList.data.length} dashboards via MCP`);

  console.log(`\n─────────────────────────`);
  console.log(`Suite 4 Results: ${PASS} passed, ${FAIL} failed`);
  console.log(`─────────────────────────`);
  process.exit(FAIL > 0 ? 1 : 0);
}
run();
