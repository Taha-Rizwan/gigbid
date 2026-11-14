// Prepends the "generated, do not hand-edit" banner to files produced by `npm run gen:api`.
import { readFileSync, writeFileSync } from "node:fs";

const HEADER =
  "/**\n" +
  " * GENERATED FILE - DO NOT HAND-EDIT.\n" +
  " * Source: apps/web/openapi.json (exported from the FastAPI app).\n" +
  " * Regenerate with `npm run gen:api`.\n" +
  " */\n";

for (const file of process.argv.slice(2)) {
  const body = readFileSync(file, "utf8");
  if (!body.startsWith(HEADER)) writeFileSync(file, HEADER + body);
}
