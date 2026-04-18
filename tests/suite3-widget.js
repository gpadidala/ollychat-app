#!/usr/bin/env node
/**
 * Suite 3: UI Widget / SSE Parser simulation (22 tests)
 * Simulates the browser widget's SSE parsing logic to catch streaming bugs.
 *
 * Run: node suite3-widget.js
 */

const http = require('http');

function simulate(query, headers = {}) {
  return new Promise((resolve) => {
    const data = JSON.stringify({
      messages: [{ role: 'user', content: query }],
      stream: true
    });

    const events = [];
    let acc = '';
    let buf = '';

    const req = http.request({
      hostname: 'localhost',
      port: 8000,
      path: '/api/v1/chat',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data),
        'Origin': 'http://localhost:3200',
        'X-Grafana-User': 'admin',
        ...headers
      }
    }, (res) => {
      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        buf += chunk;
        // CRLF -> LF normalization (the fix)
        buf = buf.replace(/\r\n/g, '\n');
        let sep;
        while ((sep = buf.indexOf('\n\n')) !== -1) {
          const frame = buf.slice(0, sep);
          buf = buf.slice(sep + 2);
          for (const line of frame.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            const js = line.slice(6);
            if (js === '[DONE]') continue;
            try {
              const ev = JSON.parse(js);
              events.push(ev);
              if (ev.type === 'text') acc += ev.delta;
            } catch (e) { /* ignore parse errors */ }
          }
        }
      });
      res.on('end', () => resolve({ events, acc, status: res.statusCode, headers: res.headers }));
    });

    req.on('error', (e) => resolve({ error: e.message }));
    req.write(data);
    req.end();
  });
}

async function run() {
  let PASS = 0, FAIL = 0;
  const check = (cond, name) => { if (cond) { console.log(`  PASS: ${name}`); PASS++; } else { console.log(`  FAIL: ${name}`); FAIL++; } };

  console.log('═══ SUITE 3: UI / SSE PARSER ═══\n');

  console.log('T1-T3: HTTP status + content-type + CORS');
  const r1 = await simulate('list dashboards');
  check(r1.status === 200, 'HTTP 200');
  check((r1.headers['content-type'] || '').includes('text/event-stream'), 'Content-Type: text/event-stream');
  check(r1.headers['access-control-allow-origin'] === 'http://localhost:3200', 'CORS origin echoed');

  console.log('\nT4-T8: SSE event types');
  const types = [...new Set(r1.events.map(e => e.type))];
  check(types.includes('tool_start'), 'tool_start event emitted');
  check(types.includes('tool_result'), 'tool_result event emitted');
  check(types.includes('text'), 'text event emitted');
  check(types.includes('usage'), 'usage event emitted');
  check(types.includes('done'), 'done event emitted');

  console.log('\nT9-T12: Content correctness');
  check(r1.acc.length > 500, `Content length ${r1.acc.length} > 500`);
  check(r1.acc.includes('dashboard'), 'Content mentions "dashboard"');
  check(r1.acc.includes('**'), 'Markdown bold present');
  check(r1.acc.includes('['), 'Markdown links present');

  console.log('\nT13-T15: Tool call metadata');
  const toolStart = r1.events.find(e => e.type === 'tool_start');
  check(toolStart && toolStart.name === 'list_dashboards', 'tool_start.name is list_dashboards');
  check(toolStart && toolStart.id, 'tool_start has id');
  const toolResult = r1.events.find(e => e.type === 'tool_result');
  check(toolResult && toolResult.durationMs !== undefined, 'tool_result has durationMs');

  console.log('\nT16: CRLF line ending fix');
  check(r1.events.length > 5, `Parsed ${r1.events.length} events (CRLF fix working)`);

  console.log('\nT17-T20: Multiple queries in sequence');
  const r2a = await simulate('list datasources');
  const r2b = await simulate('check grafana health');
  const toolA = r2a.events.find(e => e.type === 'tool_start');
  const toolB = r2b.events.find(e => e.type === 'tool_start');
  check(toolA && toolA.name === 'list_datasources', 'Query A: list_datasources');
  check(toolB && toolB.name === 'health_check', 'Query B: health_check');
  check(r2a.acc.includes('Mimir') || r2a.acc.includes('Loki'), 'Datasources content has Mimir/Loki');
  check(r2b.acc.toLowerCase().includes('version'), 'Health content has "Version"');

  console.log('\nT21-T22: Dashboard search');
  const r3 = await simulate('search dashboards aks');
  const tool3 = r3.events.find(e => e.type === 'tool_start');
  check(tool3 && tool3.name === 'search_dashboards', 'search_dashboards matched');
  check(tool3 && tool3.input && tool3.input.query === 'aks', `query arg = 'aks' (got ${JSON.stringify(tool3?.input)})`);

  console.log(`\n─────────────────────────`);
  console.log(`Suite 3 Results: ${PASS} passed, ${FAIL} failed`);
  console.log(`─────────────────────────`);
  process.exit(FAIL > 0 ? 1 : 0);
}
run();
