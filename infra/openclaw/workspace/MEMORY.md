# Long-Term Memory

- This OpenClaw gateway runs directly on the DGX GB10 host named `hack`.
- Inference uses the existing authenticated LiteLLM service and the virtual
  model `Qwen3.6-27B-FP8`.
- Repository configuration under `infra/openclaw/` is authoritative for the
  operator-authored workspace and settings.
- Never create a cloud inference fallback.
