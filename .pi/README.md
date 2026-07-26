# pi project config

Project-local Pi configuration for `dell-x-nvidia-hackathon`.

## Layout

| Path | Purpose |
|------|---------|
| `settings.json` | Loads the repo-local provider extension and sets Qwen as the default model for this repo. |
| `extensions/vllm-hack.ts` | Registers `vllm-hack` against hack's LiteLLM/vLLM Qwen service. |
| `bin/vllm-hack-key` | Starts the SSH tunnel if needed and prints the LiteLLM key from `hack-litellm`. |

## Usage

From this repo:

```bash
pi -a --no-extensions --extension .pi/extensions/vllm-hack.ts --provider vllm-hack --model Qwen3.6-27B-FP8 --models vllm-hack/Qwen3.6-27B-FP8
```

After the project is trusted, plain `pi` in this repo should show and default
to `vllm-hack / Qwen3.6-27B-FP8`. The longer command above is the strict mode:
it disables globally configured extensions for the run and loads only this
repo's Qwen provider extension.

The extension uses `bin/vllm-hack-key` to start an SSH tunnel to
`hack:127.0.0.1:4000` on local port `14000` when direct access is unavailable,
and to fetch the LiteLLM key from the running `hack-litellm` container without
writing it to disk.
