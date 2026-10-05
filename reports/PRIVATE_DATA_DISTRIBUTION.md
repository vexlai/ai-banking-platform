# Private data distribution — v1

Existing DuckDB snapshots packaged without rerunning ingestion/EDA or changing sources.
DuckDB version: 1.5.6. Build hashes checked before/after; read-only source connections.
Packages are local under `.tmp/distribution/`, excluded from Git; no cloud upload performed.

| Package | Compressed bytes | Database bytes | Package SHA-256 |
|---|---:|---:|---|
| banking-serving-v1.zip | 409187286 | 900214784 | 799b3912a11bc1a3334a82fbc361861ff0f9a51a0047d65e7dfa5747cfd631bf |
| banking-analytics-v1.zip | 929923198 | 1453862912 | ddf9b1c2b1f531b68c5fdeb0fb05c8005668393d8706290006f9871bad067ba9 |

Each package has a `.zip.sha256` sidecar and an internal `manifest.json` with table
counts and the uncompressed database digest. Source database SHA-256:

- serving: `8b9005ede7618606721015b9b1155625bf9e82d418a16edef96003da6a203bf2`
- analytics: `bd6d87c315103fa6d4e771b52dae2df69a382d7e223378a6464ecb1adecf2b8d`

Serving: 4,425,008 transactions, 400,000 products, 150,000 customers plus metadata.
Analytics: 22 physical tables, including 15,620,994 digital events, 686,296 service
interactions and existing customer aggregates. This is a projected cache, not full raw.

Implementation: scripts/package_banking_data.py, tests/test_data_distribution.py,
docs/PRIVATE_DATA_DISTRIBUTION.md and a README link. No runtime changes.
Four distribution tests pass: roundtrip/no overwrite, incorrect outer hash, invalid
archive members/traversal and corrupt inner hash. Ruff passes. Real serving package
installed to ignored `data/serving/`, SHA-256 verified, permissions 0400; DatasetTools
startup validation passed. This local copy is a receiver smoke test, not a runtime
configuration change. Existing `.tmp/banking_serving/` source retained unchanged.

Final verification: both ZIPs passed complete outer and inner SHA-256 checks.
Full regression suite: 182 PASS (178 existing + four distribution tests).
Frozen verification: 232 protected outputs, 384 baseline predictions and 132 retrieval
fixtures preserved; 7,671 raw sizes checked, not content-rehashed. Preexisting import
manifest discrepancies remain documented by the verifier; none repaired here.

No tokens, secrets, operational SQLite, raw files or FAISS included. The ZIPs are not
encrypted; storage must be private and access-controlled. IDs and historical source
paths can exist inside analytics; not anonymization-certified. Verify hashes using
a trusted independently communicated checksum. Respect organizer redistribution terms.

`src.data.ingest` does not exist and the current Docker Compose is legacy scaffold.
No FAISS is required by this MVP. Distribution is ready; Docker onboarding of the
current runtime remains a separate task, with read-only data mounts, durable SQLite,
runtime dependencies and trusted identity configuration.
