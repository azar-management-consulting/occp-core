/**
 * OCCP Brain API load test — k6 script.
 *
 * Usage:
 *   TARGET_URL=https://api.occp.ai TOKEN=<jwt> k6 run scripts/loadtest-brain.js
 *
 * Targets:
 *   - 50 concurrent requests POST /api/v1/brain/message
 *   - p95 response time < 5s
 *   - Error rate < 1%
 *
 * Validate syntax (no execution):
 *   k6 validate scripts/loadtest-brain.js
 */
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const brainLatency = new Trend('brain_latency_ms', true);

const TARGET = __ENV.TARGET_URL || 'https://api.occp.ai';
const TOKEN = __ENV.TOKEN;

if (!TOKEN) {
  throw new Error('TOKEN env var required (JWT from /api/v1/auth/login)');
}

export const options = {
  scenarios: {
    steady_state: {
      executor: 'constant-vus',
      vus: 50,
      duration: '2m',
      gracefulStop: '30s',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<5000'],
    http_req_failed: ['rate<0.01'],
    errors: ['rate<0.01'],
  },
};

const PROMPTS = [
  'What is the current system status?',
  'Summarize the last pipeline run',
  'Check the health of node hetzner-brain',
  'How many tasks are in the queue?',
  'What is the L6 readiness score?',
];

export default function () {
  const url = `${TARGET}/api/v1/brain/message`;
  const payload = JSON.stringify({
    message: PROMPTS[Math.floor(Math.random() * PROMPTS.length)],
    user_id: `loadtest_${__VU}_${__ITER}`,
  });

  const params = {
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
    },
    timeout: '30s',
    tags: { endpoint: 'brain_message' },
  };

  const start = Date.now();
  const res = http.post(url, payload, params);
  const elapsed = Date.now() - start;

  brainLatency.add(elapsed);

  const ok = check(res, {
    'status 200/201': (r) => r.status === 200 || r.status === 201,
    'response has body': (r) => r.body && r.body.length > 0,
  });

  errorRate.add(!ok);
  sleep(1);
}

export function handleSummary(data) {
  return {
    stdout: `\n=== OCCP Brain Load Test Summary ===
VUs: 50 | Duration: 2m | Target: ${TARGET}
p95 latency: ${data.metrics.http_req_duration.values['p(95)'].toFixed(0)}ms
p99 latency: ${data.metrics.http_req_duration.values['p(99)'].toFixed(0)}ms
Error rate: ${(data.metrics.errors.values.rate * 100).toFixed(2)}%
Total requests: ${data.metrics.http_reqs.values.count}
\n`,
  };
}
