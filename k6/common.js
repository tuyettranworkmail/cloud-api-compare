import http from 'k6/http';
import { check, sleep } from 'k6';
import exec from 'k6/execution';
import { Counter, Rate, Trend } from 'k6/metrics';

export const cfg = JSON.parse(open(__ENV.BENCH_RUN_CONFIG));
const samples = new Trend('request_sample_ms', true);
const handler = new Trend('handler_duration_ms', true);
const cold = new Trend('cold_request_duration_ms', true);
const warm = new Trend('warm_request_duration_ms', true);
const cpu = new Trend('cpu_endpoint_duration_ms', true);
const businessError = new Rate('application_error_rate');
const successful = new Counter('successful_requests');

// Deterministic hash: identical workload schedule across models for a given repeat.
function uniform(i) {
  let x = (i + cfg.seed) | 0;
  x = Math.imul(x ^ (x >>> 16), 0x45d9f3b);
  x = Math.imul(x ^ (x >>> 16), 0x45d9f3b);
  return ((x ^ (x >>> 16)) >>> 0) / 4294967296;
}

function substitute(value, replacements) {
  if (typeof value === 'string') {
    for (const key of Object.keys(replacements)) value = value.split(`{${key}}`).join(replacements[key]);
    return value;
  }
  if (Array.isArray(value)) return value.map(x => substitute(x, replacements));
  if (value && typeof value === 'object') {
    const out = {};
    for (const key of Object.keys(value)) out[key] = substitute(value[key], replacements);
    return out;
  }
  return value;
}

export function request(forcedEndpoint) {
  const iteration = exec.scenario.iterationInTest;
  const r = uniform(iteration);
  const endpoint = forcedEndpoint || cfg.endpoint || (r < cfg.mix.read ? 'read' : r < cfg.mix.read + cfg.mix.write ? 'write' : 'cpu');
  const ep = cfg.endpoints[endpoint];
  const phase = cfg.scenario === 'idle' ? (iteration === 0 ? 'first_after_idle' : 'measurement') : exec.scenario.name;
  const requestId = `${cfg.run_id}-a${cfg.attempt || 1}-${phase}-${iteration}`;
  const replacements = {id: cfg.read_ids[Math.floor(uniform(iteration + 12345) * cfg.read_ids.length)], run_id: cfg.run_id, write_id: `bench-${requestId}`};
  const tags = {deployment_model: cfg.model, endpoint, scenario_name: cfg.scenario, load_level: cfg.load_level, run_id: cfg.run_id, phase, data_mode: cfg.data_mode};
  const body = ep.body === null ? null : JSON.stringify(substitute(ep.body, replacements));
  const before = Date.now();
  const response = http.request(ep.method, cfg.url + substitute(ep.path, replacements), body, {
    headers: Object.assign({'Content-Type': 'application/json', 'X-Request-ID': requestId}, cfg.headers),
    timeout: `${cfg.timeout_seconds}s`, redirects: 0, tags: Object.assign({name: endpoint}, tags), responseType: 'text',
  });
  const elapsed = Date.now() - before;
  let parsed = null;
  try { parsed = response.json(); } catch (_) { /* invalid JSON is an application failure */ }
  const validStatus = ep.expected_status.indexOf(response.status) >= 0;
  let validBody = parsed !== null && typeof parsed === 'object';
  // Full JSON Schema and semantic equivalence are preflight checks. During load,
  // check required fields and optional business success path without external JS deps.
  for (const key of ep.response_schema.required || []) validBody = validBody && Object.prototype.hasOwnProperty.call(parsed || {}, key);
  if (ep.success_field) validBody = validBody && parsed[ep.success_field] === ep.success_value;
  const ok = validStatus && validBody;
  const first = String(response.headers['X-Cold-Start'] || '').toLowerCase();
  const classification = first === 'true' ? 'application_first_request' : first === 'false' ? 'confirmed_warm' : 'unknown';
  const sampleTags = Object.assign({}, tags, {
    request_id: requestId, status: String(response.status), success: String(ok),
    classification, instance_id: response.headers['X-Instance-Id'] || '',
    handler_ms: response.headers['X-Handler-Duration-Ms'] || '',
    wall_ms: String(elapsed), error_code: String(response.error_code || ''),
    scenario_start_ms: String(exec.scenario.startTime),
  });
  // This single point per request makes joins exact; never join built-in metrics by timestamp.
  samples.add(response.timings.duration, sampleTags);
  const h = Number(sampleTags.handler_ms);
  if (sampleTags.handler_ms !== '' && Number.isFinite(h)) handler.add(h, tags);
  if (classification === 'confirmed_warm') warm.add(response.timings.duration, tags);
  // Confirmed cold is established later using independent platform evidence.
  if (classification === 'confirmed_cold') cold.add(response.timings.duration, tags);
  if (endpoint === 'cpu') cpu.add(response.timings.duration, tags);
  businessError.add(!validBody, tags);
  successful.add(ok ? 1 : 0, tags);
  check(response, {'expected status': () => validStatus, 'valid application payload': () => validBody}, tags);
  if (cfg.scenario === 'idle' && iteration < cfg.warm_requests) sleep(cfg.interval_seconds);
}

export function summary(data) {
  return {[cfg.summary_path]: JSON.stringify(data, null, 2)};
}

export function optionsFor(kind) {
  const base = {discardResponseBodies: false, summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(95)', 'p(99)'],
    tags: {run_id: cfg.run_id, deployment_model: cfg.model, scenario_name: cfg.scenario, load_level: cfg.load_level},
    thresholds: {'http_req_failed': [{threshold: 'rate<0.25', abortOnFail: true, delayAbortEval: '15s'}]}, scenarios: {}};
  const allocation = {preAllocatedVUs: cfg.preallocated_vus, maxVUs: cfg.max_vus, timeUnit: '1s', gracefulStop: `${cfg.graceful_stop_seconds}s`};
  if (kind === 'idle') {
    base.scenarios.idle = {executor: 'shared-iterations', vus: 1, iterations: cfg.warm_requests + 1, maxDuration: `${(cfg.warm_requests + 1) * (cfg.timeout_seconds + cfg.interval_seconds) + 10}s`};
    return base;
  }
  if (cfg.warmup_seconds > 0) base.scenarios.warmup = Object.assign({}, allocation, {executor: 'constant-arrival-rate', rate: cfg.rate, duration: `${cfg.warmup_seconds}s`, gracefulStop: '0s'});
  if (kind === 'burst') {
    base.scenarios.measurement = Object.assign({}, allocation, {executor: 'ramping-arrival-rate', startRate: cfg.baseline_rps, startTime: `${cfg.warmup_seconds}s`, stages: [
      {duration: `${cfg.baseline_seconds}s`, target: cfg.baseline_rps},
      {duration: `${cfg.ramp_seconds}s`, target: cfg.peak_rps},
      {duration: `${cfg.hold_seconds}s`, target: cfg.peak_rps},
      {duration: `${cfg.ramp_seconds}s`, target: cfg.baseline_rps},
      {duration: `${cfg.recovery_seconds}s`, target: cfg.baseline_rps},
    ]});
  } else {
    base.scenarios.measurement = Object.assign({}, allocation, {executor: 'constant-arrival-rate', rate: cfg.rate, duration: `${cfg.measurement_seconds}s`, startTime: `${cfg.warmup_seconds}s`});
  }
  return base;
}
