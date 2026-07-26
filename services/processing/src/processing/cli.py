"""Command-line entry points for training and fixture/live scoring."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from processing.anomaly import IsolationForestModel, safe_load
from processing.autoencoder import AutoencoderConfig, AutoencoderModel
from processing.client import IngestionClient
from processing.dataset import augmented_normal_windows, load_events
from processing.inference import LocalLiteLLMInvestigator, MockInvestigator
from processing.live import LiveScorer
from processing.pipeline import detect_window, recommend_policy


def _known_destinations(events: list[dict[str, object]]) -> set[str]:
    return {
        str(event["destination"]) for event in events if isinstance(event.get("destination"), str)
    }


def _train_iforest(args: argparse.Namespace) -> None:
    normal = load_events(args.normal)
    vectors = augmented_normal_windows(normal, count=args.windows, seed=args.seed)
    model = IsolationForestModel.train(vectors, random_state=args.seed)
    model.save(args.output)
    print(json.dumps({"model_version": model.version, "windows": len(vectors)}))


def _train_autoencoder(args: argparse.Namespace) -> None:
    normal = load_events(args.normal)
    vectors = augmented_normal_windows(normal, count=args.windows, seed=args.seed)
    config = AutoencoderConfig(epochs=args.epochs, seed=args.seed)
    model = AutoencoderModel.train(vectors, config)
    model.save(args.output, snapshot_id=args.snapshot_id)
    print(json.dumps({"model_version": model.version, "windows": len(vectors)}))


def _detect(args: argparse.Namespace) -> None:
    events = load_events(args.events)
    baseline = load_events(args.baseline) if args.baseline else []
    model = safe_load(args.model)
    detection = detect_window(
        events,
        known_destinations=_known_destinations(baseline),
        anomaly_model=model,
        threshold=args.threshold,
    )
    output: dict[str, object] = {
        "risk_score": detection.risk_score,
        "anomaly_score": detection.anomaly_score,
        "features": detection.features.as_dict(),
        "finding": detection.finding,
    }
    if detection.finding is not None:
        investigator = (
            LocalLiteLLMInvestigator.from_env() if args.local_inference else MockInvestigator()
        )
        finding, recommendation = recommend_policy(detection, investigator)
        output["finding"] = finding
        output["recommendation"] = recommendation
        if args.post_to:
            client = IngestionClient(args.post_to)
            client.post_finding(finding)
            client.post_recommendation(recommendation)
    print(json.dumps(output, indent=2, sort_keys=True))


def _live(args: argparse.Namespace) -> None:
    baseline = load_events(args.baseline) if args.baseline else []
    scorer = LiveScorer(
        args.ingestion_url,
        model=safe_load(args.model),
        known_destinations=_known_destinations(baseline),
        window_size=args.window_size,
        threshold=args.threshold,
    )
    scorer.run(interval=args.interval)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    train = commands.add_parser("train-iforest", help="Train the live CPU anomaly model.")
    train.add_argument("--normal", type=Path, required=True)
    train.add_argument("--output", type=Path, required=True)
    train.add_argument("--windows", type=int, default=256)
    train.add_argument("--seed", type=int, default=42)
    train.set_defaults(handler=_train_iforest)

    offline = commands.add_parser("train-autoencoder", help="Train the offline model.")
    offline.add_argument("--normal", type=Path, required=True)
    offline.add_argument("--output", type=Path, required=True)
    offline.add_argument("--snapshot-id", required=True)
    offline.add_argument("--windows", type=int, default=256)
    offline.add_argument("--epochs", type=int, default=150)
    offline.add_argument("--seed", type=int, default=42)
    offline.set_defaults(handler=_train_autoencoder)

    detect = commands.add_parser("detect", help="Score one JSON/JSONL event window.")
    detect.add_argument("--events", type=Path, required=True)
    detect.add_argument("--baseline", type=Path)
    detect.add_argument("--model", type=Path)
    detect.add_argument("--threshold", type=float, default=70.0)
    detect.add_argument("--local-inference", action="store_true")
    detect.add_argument("--post-to", help="Ingestion base URL, e.g. http://localhost:8100")
    detect.set_defaults(handler=_detect)

    live = commands.add_parser("live", help="Poll ingestion and emit findings continuously.")
    live.add_argument("--ingestion-url", default="http://127.0.0.1:8100")
    live.add_argument("--baseline", type=Path)
    live.add_argument("--model", type=Path)
    live.add_argument("--window-size", type=int, default=20)
    live.add_argument("--threshold", type=float, default=70.0)
    live.add_argument("--interval", type=float, default=1.0)
    live.set_defaults(handler=_live)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
