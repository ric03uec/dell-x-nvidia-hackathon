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
just s processing train
just s processing demo
```

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

The offline trainer accepts only feature windows supplied by the caller. The
integration layer must obtain those from ingestion's safe snapshot API; this
service never opens the live SQLite database.
