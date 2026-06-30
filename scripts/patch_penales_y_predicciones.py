#!/usr/bin/env python3
"""Actualiza resultados conocidos que se definieron por penales."""

import json
from pathlib import Path

DATA_FILE = Path("worldcup_results.json")

PENALTY_UPDATES = {
    "P74": {
        "penalties": "3 - 4",
        "note": "Penales: Paraguay 4 - 3 Alemania",
    },
    "P75": {
        "penalties": "2 - 3",
        "note": "Penales: Marruecos 3 - 2 Países Bajos",
    },
}


def main() -> None:
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    games = payload.get("games", payload if isinstance(payload, list) else [])

    for game in games:
        update = PENALTY_UPDATES.get(str(game.get("id")))
        if not update:
            continue
        game["penalties"] = update["penalties"]
        notes = str(game.get("notes", ""))
        if update["note"] not in notes:
            game["notes"] = f"{notes} · {update['note']}" if notes else update["note"]

    DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
