import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));
const read = (path) => readFile(resolve(frontendRoot, path), "utf8");

test("dashboard route wiring and five-query UI keep provenance and unavailable states visible", async () => {
  const [html, app, queryPage] = await Promise.all([
    read("index.html"), read("src/App.tsx"), read("src/pages/ChallengeQueriesPage.tsx"),
  ]);
  assert.match(html, /id="root"/);
  assert.match(app, /lazy\(\(\) => import\("\.\/pages\/ChallengeQueriesPage"\)\)/);
  for (const route of ["buildings-over-2-floors-without-match", "streets-without-streetlights",
    "low-confidence-floor-counts", "unmatched-buildings-by-street", "routed-vs-all-vlm"]) {
    assert.ok(queryPage.includes(route), `missing challenge query route ${route}`);
  }
  assert.match(queryPage, /NOT_EVALUABLE/);
  assert.match(queryPage, /NOT REAL STREET VIEW/);
  assert.match(queryPage, /Fixed cloud demo dataset/);
});
