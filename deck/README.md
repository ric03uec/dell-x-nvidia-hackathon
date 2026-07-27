# SquidWard Hackathon Deck

View the published deck at **[ric03uec.github.io/dell-x-nvidia-hackathon](https://ric03uec.github.io/dell-x-nvidia-hackathon/)**.

For local use, open [`index.html`](./index.html) in a browser. It has no package or network dependencies. Changes under `deck/` on `main` are automatically deployed to GitHub Pages.

## Controls

- `Right`, `Space`, or `PageDown`: next slide
- `Left`, `Backspace`, or `PageUp`: previous slide
- `N`: toggle speaker notes
- `F`: toggle fullscreen
- Browser Print -> Save as PDF: export all slides in 16:9

The editable source narrative and speaker notes are also in [`slides.md`](./slides.md).

The main pitch is ten slides and is timed for five minutes, followed by the live demo. The eleventh slide is a short post-demo close.

## Recommended presentation flow

1. Present slides 1-10 in five minutes.
2. Leave slide 10 visible while switching to the live demo.
3. Run the normal activity, suspicious transfer, approval, and blocked retry.
4. Return to slide 11 for the closing statement.

## Claims to verify before presenting

- The complete loop works with outbound network access disabled.
- NemoClaw uses only the GB10-hosted model and has no cloud fallback.
- The dashboard visibly records detection, approval, policy application, and blocked retry.
- Any measured detection latency shown during the demo comes from the final integrated build.
