"""CLI using synthetic input unless an incident is supplied."""

import argparse
import json
import sys

from .triage import TriageError, default_backend, triage


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LLM incident triage")
    parser.add_argument("incident", nargs="?", default="Synthetic payment API timeout increased after a test deployment.")
    args = parser.parse_args()
    try:
        result = triage(args.incident, default_backend())
    except (TriageError, ValueError) as exc:
        print(f"triage failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result.dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
