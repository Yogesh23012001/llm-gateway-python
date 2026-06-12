import http from 'k6/http';
import { check } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 3 },   // gentle — these cost money + hit Anthropic
    { duration: '20s', target: 3 },
    { duration: '5s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'],
  },
};

const BASE = __ENV.GATEWAY_URL;

const payload = JSON.stringify({
  model: 'claude-haiku-4-5',
  messages: [{ role: 'user', content: 'Reply with one word.' }],
  max_tokens: 5,
});

export default function () {
  const res = http.post(`${BASE}/v1/chat/completions`, payload, {
    headers: { 'Content-Type': 'application/json' },
  });
  check(res, {
    'status 200': (r) => r.status === 200,
  });
}