const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

function compareUtf8Bytes(a, b) {
  const ab = Buffer.from(a, "utf8");
  const bb = Buffer.from(b, "utf8");
  const min = Math.min(ab.length, bb.length);
  for (let i = 0; i < min; i += 1) {
    if (ab[i] !== bb[i]) return ab[i] - bb[i];
  }
  return ab.length - bb.length;
}

function canonicalize(value) {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isInteger(value)) throw new Error("non-integer number not allowed");
    return String(value);
  }
  if (typeof value === "string") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map((v) => canonicalize(v)).join(",") + "]";
  if (typeof value === "object") {
    const keys = Object.keys(value).sort(compareUtf8Bytes);
    const parts = keys.map((k) => JSON.stringify(k) + ":" + canonicalize(value[k]));
    return "{" + parts.join(",") + "}";
  }
  throw new Error(`unsupported type: ${typeof value}`);
}

function digestHex(text) {
  return crypto.createHash("sha256").update(Buffer.from(text, "utf8")).digest("hex");
}

function classifyRaw(raw) {
  const decoded = raw.toString("utf8");
  if (!raw.equals(Buffer.from(decoded, "utf8"))) return "E_DIGEST_INVALID_UTF8";
  if (decoded.includes("\r")) return "E_DIGEST_NORMALIZATION_MISMATCH";
  if (!decoded.endsWith("\n")) return "E_DIGEST_TRAILING_NEWLINE_REQUIRED";
  if (decoded.endsWith("\n\n")) return "E_DIGEST_NORMALIZATION_MISMATCH";
  return null;
}

function main() {
  const vectorsPath = path.resolve(__dirname, "../../tests/kernel/v1/vectors/digest-v1.json");
  const payload = JSON.parse(fs.readFileSync(vectorsPath, "utf8"));

  if (payload.version !== "digest-v1") throw new Error(`unexpected version=${payload.version}`);
  if (payload.algorithm !== "sha256") throw new Error(`unexpected algorithm=${payload.algorithm}`);

  let checked = 0;
  for (const vector of payload.vectors) {
    if (Object.prototype.hasOwnProperty.call(vector, "input")) {
      const canonical = canonicalize(vector.input);
      const digest = digestHex(canonical);
      if (canonical !== vector.canonical) {
        throw new Error(`canonical mismatch vector=${vector.name}`);
      }
      if (digest !== vector.digest_hex) {
        throw new Error(`digest mismatch vector=${vector.name}`);
      }
      checked += 1;
      continue;
    }
    const raw = Object.prototype.hasOwnProperty.call(vector, "raw_utf8")
      ? Buffer.from(vector.raw_utf8, "utf8")
      : Buffer.from(vector.raw_b64, "base64");
    const err = classifyRaw(raw);
    if (err !== vector.expect_error) {
      throw new Error(`raw vector error mismatch vector=${vector.name} got=${err} want=${vector.expect_error}`);
    }
    checked += 1;
  }

  process.stdout.write(`ts_conformance=PASS checked=${checked}\n`);
}

main();

