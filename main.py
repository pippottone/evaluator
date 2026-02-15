from __future__ import annotations

import argparse
import json
from pathlib import Path

from api_client import APISportsClient
from evaluator import evaluate_betslip
from models import Market, Selection


def load_input(path: Path) -> tuple[str, list[Selection]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    base_url = payload["base_url"]

    selections = []
    for item in payload.get("selections", []):
        selections.append(
            Selection(
                fixture_id=int(item["fixture_id"]),
                market=Market(item["market"]),
                pick=str(item["pick"]),
                line=float(item["line"]) if "line" in item and item["line"] is not None else None,
                team=str(item["team"]).upper() if "team" in item and item["team"] is not None else None,
            )
        )

    return base_url, selections


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a parsed betslip via API historical data")
    parser.add_argument("--input", required=True, help="Path to slip JSON")
    parser.add_argument("--api-key", required=False, help="API-Sports key (optional if API_SPORTS_KEY is set)")
    args = parser.parse_args()

    base_url, selections = load_input(Path(args.input))
    client = APISportsClient(base_url=base_url, api_key=args.api_key)
    result = evaluate_betslip(client, selections)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
