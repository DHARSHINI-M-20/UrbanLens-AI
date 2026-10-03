import test from "node:test";
import assert from "node:assert/strict";
import { hasCoordinates, nullableCoordinate, nullableNumber, nullablePercent } from "../src/utils/recordValues.ts";
import { paginate } from "../src/utils/pagination.ts";

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
