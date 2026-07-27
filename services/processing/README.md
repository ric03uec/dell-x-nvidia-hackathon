# SquidWard processing

Local-only processing for canonical event windows:

1. deterministic feature extraction and explainable rules;
2. a CPU Isolation Forest that can fail independently;
3. an optional offline PyTorch autoencoder trained from snapshot-derived features;
4. schema-shaped findings persisted for OpenClaw investigation;
5. no cloud or mock-inference runtime fallback.

## Demo

```bash
just s processing setup
just s processing generate   # 800 train-normal + 400 labeled evaluation windows
just s processing train      # Isolation Forest + PyTorch autoencoder + promotion gates
just s processing demo
```

Generation writes deterministic, synthetic-only windows to `synthetic-data/`.
Ground truth is kept in a separate `expected.json`, so labels never leak into
the model inputs. Training writes versioned artifacts and measured false/true
positive rates to `artifacts/training-report.json`. Both directories are ignored
because generated data and binary model artifacts are reproducible and should
not be merged or hand-edited.

Post deterministic findings to a running ingestion service:

```bash
uv run --project services/processing squidward-process detect \
  --events fixtures/expected/suspicious.json \
  --baseline fixtures/expected/normal.json \
  --model services/processing/artifacts/isolation-forest.pkl \
  --post-to http://127.0.0.1:8100
```

The OpenClaw security agent reads persisted evidence over FastMCP and creates
the investigation and constrained recommendation. Live detection remains
rules-only if the Isolation Forest artifact is absent or corrupt.

For the hackathon, the bundle trainer uses generated windows derived from the
frozen Squid/OpenShell fixtures, including mitmproxy-style sensitive field-name
indicators. In production, the integration layer must replace that dataset with
features obtained from ingestion's safe snapshot API. This service never opens
the live SQLite database.
