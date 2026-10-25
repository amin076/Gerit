"""CLI for validating/previewing a Gerit experiment configuration."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Gerit experiment setup (solver not yet implemented)")
    parser.add_argument("--config", default="configs/five-squares.json", help="JSON configuration path")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print plan (no optimization)")
    args = parser.parse_args()
    config = load_config(args.config)
    summary = {
        "status": "configuration_only",
        "note": "The geometric validator and evolutionary solver are not implemented yet.",
        "config": asdict(config),
        "selection_slots": config.selection_slots(),
        "maximum_child_proposals_per_generation": (
            config.next_generation_population * config.offspring_per_parent
        ),
        "first_generation_child_proposals": (
            config.initial_population * config.offspring_per_parent
        ),
    }
    if not args.dry_run:
        parser.error("Optimization is not implemented yet. Use --dry-run to validate settings.")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
