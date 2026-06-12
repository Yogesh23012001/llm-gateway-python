import http from 'k6/http';
import { check } from 'k6';

export const options = {
  stages: [
    { duration: '20s', target: 20 },  // ramp to 20 virtual users
    { duration: '30s', target: 20 },  // hold
    { duration: '10s', target: 0 },   // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% under 500ms
    http_req_failed: ['rate<0.01'],    // <1% errors
  },
};

const BASE = __ENV.GATEWAY_URL;

export default function () {
  const res = http.get(`${BASE}/health`);
  check(res, {
    'status 200': (r) => r.status === 200,
  });
}