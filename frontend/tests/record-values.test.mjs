import test from "node:test";
import assert from "node:assert/strict";
import { hasCoordinates, nullableCoordinate, nullableNumber, nullablePercent } from "../src/utils/recordValues.ts";
import { paginate } from "../src/utils/pagination.ts";
import { getBedrockExecutionStatus } from "../src/utils/bedrockExecution.ts";

test("missing numeric values remain distinct from known zero", () => {
  assert.equal(nullableNumber(undefined), null);
  assert.equal(nullableNumber(null), null);
  assert.equal(nullableNumber("  "), null);
  assert.equal(nullableNumber("0"), 0);
  assert.equal(nullablePercent(undefined), null);
  assert.equal(nullablePercent(0), 0);
  assert.equal(nullablePercent(0.7), 70);
});

test("invalid coordinates are unavailable while the valid zero coordinate remains valid", () => {
  assert.equal(hasCoordinates(null, 0), false);
  assert.equal(hasCoordinates(0, 0), true);
  assert.equal(hasCoordinates(91, 0), false);
  assert.equal(nullableCoordinate(0, 90), 0);
  assert.equal(nullableCoordinate(91, 90), null);
});

test("client pages have stable bounds and report loaded record totals", () => {
  const result = paginate([1, 2, 3, 4, 5], 9, 2);
  assert.deepEqual(result, { items: [5], page: 3, pageCount: 3, total: 5 });
});

test("Bedrock execution is verified only from a successful invocation record with a timestamp", () => {
  const result = getBedrockExecutionStatus([{
    bedrock_status: "success", bedrock_invocations: 1, bedrock_invocation_attempts: 1,
    timestamp: "2026-10-16T12:30:00Z", bedrock_latency_ms: 1438.22,
  }]);
  assert.equal(result.verified, true);
  assert.match(result.message, /1 successful invocation/);
  assert.match(result.message, /2026-10-16T12:30:00Z/);
});

test("Bedrock configuration, latency, and missing timestamps do not verify execution", () => {
  assert.equal(getBedrockExecutionStatus([]).verified, false);
  const missingCount = getBedrockExecutionStatus([{
    bedrock_status: "success", bedrock_invocations: 0, bedrock_invocation_attempts: 1,
    timestamp: "2026-10-16T12:30:00Z", bedrock_latency_ms: 1438.22,
  }]);
  assert.equal(missingCount.verified, false);
  const missingTimestamp = getBedrockExecutionStatus([{
    bedrock_status: "success", bedrock_invocations: 1, bedrock_invocation_attempts: 1,
    bedrock_latency_ms: 1438.22,
  }]);
  assert.equal(missingTimestamp.verified, false);
  assert.match(missingTimestamp.message, /timestamp is missing/);
});

test("already-reviewed runs remain unverified when they report zero new invocations", () => {
  const result = getBedrockExecutionStatus([{
    bedrock_status: "already_reviewed", bedrock_invocations: 0, bedrock_invocation_attempts: 0,
    bedrock_latency_ms: 1438.22,
  }]);
  assert.equal(result.verified, false);
  assert.match(result.message, /already_reviewed/);
  assert.match(result.message, /retained latency does not prove execution/);
});

test("persisted Bedrock review result verifies execution when the metrics row was already reviewed", () => {
  const result = getBedrockExecutionStatus([{
    bedrock_status: "already_reviewed", bedrock_invocations: 0, bedrock_invocation_attempts: 0,
    bedrock_latency_ms: 1438.22,
  }], [{
    bedrock_review: {
      status: "attempted_success", attempted: true, aws_service: "Amazon Bedrock Runtime",
      processing_route: "bedrock_nova_lite_escalation", result: { visible_floor_count: 3 },
    },
  }]);
  assert.equal(result.verified, true);
  assert.match(result.message, /successful Bedrock result is persisted/);
  assert.match(result.message, /timestamp is unavailable/);
  assert.doesNotMatch(result.message, /invocation\(s\)/);
});
