/**
 * SafeFlow Load Test Configuration
 *
 * Simulates WhatsApp message traffic to the inbound webhook endpoint.
 *
 * Prerequisites:
 *   - k6 installed (https://k6.io)
 *   - Staging environment configured
 *
 * Usage:
 *   k6 run tests/load/k6-config.js
 *   k6 run --env WEBHOOK_URL=https://hook.eu2.make.com/xxx tests/load/k6-config.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const messageLatency = new Trend('message_latency');

// Configuration
export const options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp up to 50 VUs over 2 minutes
    { duration: '11m', target: 50 },   // Hold at 50 VUs for 11 minutes
    { duration: '2m', target: 0 },     // Ramp down over 2 minutes
  ],
  thresholds: {
    http_req_duration: ['p(95)<5000'],  // P95 latency < 5 seconds
    errors: ['rate<0.05'],              // Error rate < 5%
    http_req_failed: ['rate<0.05'],     // HTTP failure rate < 5%
  },
};

// UK building names for test data
const buildings = [
  'Meridian House', 'Victoria House', 'Kings Court', 'The Exchange',
  'Harbourside', 'Castle Business Park', 'Ashton Gate', 'Crown Chambers',
  'Phoenix House', 'Riverside', 'Canary Wharf Tower', 'St James Square',
  'Broadgate Circle', 'One Canada Square', 'The Gherkin Offices',
];

const floors = ['ground', 'first', 'second', 'third', 'fourth', 'fifth', 'basement'];
const areas = ['kitchen', 'WC', 'reception', 'office', 'meeting room', 'car park', 'plant room', 'corridor'];

const issues = [
  'The tap in the {area} is dripping constantly',
  'Light flickering on the {floor} floor of {building}',
  'Radiator in {area} on {floor} floor is cold',
  'Door handle broken on {floor} floor',
  'Thermostat in {area} not responding',
  'Window won\'t close properly in {area}',
  'Ceiling tile stained in {area} at {building}',
  'Car park barrier not working',
  'Intercom at main entrance is faulty',
  'Blocked drain in the {area}',
  'Minor leak under the sink in {area}',
  'Hand dryer not working in the {area}',
  'Carpet coming loose in {area}',
  'Blind broken in {area} on {floor} floor',
  'Extractor fan very noisy in {area}',
  'No hot water in the {area} on {floor} floor at {building}',
  'Boiler making strange noises',
  'Mouse spotted in the {area}',
  'Paint peeling on {floor} floor corridor',
  'Signage needs updating in reception',
];

function randomItem(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function generateMessage() {
  let template = randomItem(issues);
  template = template.replace('{building}', randomItem(buildings));
  template = template.replace('{floor}', randomItem(floors));
  template = template.replace('{area}', randomItem(areas));
  return template;
}

function generatePhoneNumber() {
  const suffix = String(Math.floor(Math.random() * 900000) + 100000);
  return `44770090${suffix}`;
}

function generatePayload() {
  const phone = generatePhoneNumber();
  const messageId = `wamid.load_test_${Date.now()}_${Math.random().toString(36).substring(7)}`;

  return {
    object: 'whatsapp_business_account',
    entry: [{
      id: 'WHATSAPP_BUSINESS_ACCOUNT_ID',
      changes: [{
        value: {
          messaging_product: 'whatsapp',
          metadata: {
            display_phone_number: '447700900001',
            phone_number_id: 'PHONE_NUMBER_ID',
          },
          contacts: [{
            profile: { name: `Load Test User ${phone.slice(-4)}` },
            wa_id: phone,
          }],
          messages: [{
            from: phone,
            id: messageId,
            timestamp: String(Math.floor(Date.now() / 1000)),
            type: 'text',
            text: { body: generateMessage() },
          }],
        },
        field: 'messages',
      }],
    }],
  };
}

export default function () {
  const webhookUrl = __ENV.WEBHOOK_URL || 'https://hook.eu2.make.com/STAGING_SCENARIO_A';

  const payload = JSON.stringify(generatePayload());

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'D360-API-KEY': __ENV.DIALOG_API_KEY || 'load-test-key',
    },
    timeout: '10s',
  };

  const startTime = Date.now();
  const response = http.post(webhookUrl, payload, params);
  const latency = Date.now() - startTime;

  messageLatency.add(latency);

  const success = check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 5s': (r) => r.timings.duration < 5000,
  });

  errorRate.add(!success);

  // Target ~4 messages per second per VU = ~200 msg/min at 50 VUs
  // Each VU sends 1 message per iteration with ~0.3s sleep
  sleep(0.3 + Math.random() * 0.2);
}

export function handleSummary(data) {
  return {
    stdout: textSummary(data, { indent: '  ', enableColors: true }),
    'k6-results/summary.json': JSON.stringify(data, null, 2),
  };
}

function textSummary(data, opts) {
  const metrics = data.metrics;
  const lines = [
    '',
    '='.repeat(60),
    '  SafeFlow Load Test Results',
    '='.repeat(60),
    '',
    `  Total Requests:  ${metrics.http_reqs ? metrics.http_reqs.values.count : 'N/A'}`,
    `  Error Rate:      ${metrics.errors ? (metrics.errors.values.rate * 100).toFixed(1) + '%' : 'N/A'}`,
    `  Avg Latency:     ${metrics.http_req_duration ? metrics.http_req_duration.values.avg.toFixed(0) + 'ms' : 'N/A'}`,
    `  P95 Latency:     ${metrics.http_req_duration ? metrics.http_req_duration.values['p(95)'].toFixed(0) + 'ms' : 'N/A'}`,
    `  P99 Latency:     ${metrics.http_req_duration ? metrics.http_req_duration.values['p(99)'].toFixed(0) + 'ms' : 'N/A'}`,
    '',
    '='.repeat(60),
  ];
  return lines.join('\n');
}
