# SquidWard processing

Local-only processing for canonical event windows:

1. deterministic feature extraction and explainable rules;
2. a CPU Isolation Forest that can fail independently;
3. an optional offline PyTorch autoencoder trained from snapshot-derived features;
4. local LiteLLM investigation with a deterministic mock and no cloud fallback;
5. schema-shaped findings and code-constrained `deny_destination` recommendations.

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

Use local inference through the repository SSH tunnel:

```bash
ssh -fN -o ExitOnForwardFailure=yes \
  -L 14000:127.0.0.1:4000 dell@172.16.10.127
export LOCAL_INFERENCE_API_KEY="$(
  ssh dell@172.16.10.127 \
    'docker exec hack-litellm printenv LITELLM_MASTER_KEY'
)"
uv run --project services/processing squidward-process detect \
  --events fixtures/expected/suspicious.json \
  --baseline fixtures/expected/normal.json \
  --model services/processing/artifacts/isolation-forest.pkl \
  --local-inference
```

Add `--post-to http://localhost:8100` to post the finding and constrained
recommendation to a running ingestion API. Live detection remains rules-only if
the Isolation Forest artifact is absent or corrupt, and recommendation text
falls back to deterministic evidence if local inference is unavailable.

For the hackathon, the bundle trainer uses generated windows derived from the
frozen Squid/OpenShell fixtures, including mitmproxy-style sensitive field-name
indicators. In production, the integration layer must replace that dataset with
features obtained from ingestion's safe snapshot API. This service never opens
the live SQLite database.
