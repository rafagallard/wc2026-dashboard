#!/usr/bin/env python3
"""Actualiza cruces confirmados de octavos."""

import json
from pathlib import Path

DATA_PATH = Path("worldcup_results.json")
BRACKET_PATH = Path("clasificacion.html")

UPDATES = {
    "P89": {"team1": "Paraguay", "team2": "Francia", "score": "0 - 1", "status": "Final"},
    "P90": {"team1": "Canadá", "team2": "Marruecos", "score": "0 - 3", "status": "Final"},
    "P91": {"team1": "Brasil", "team2": "Noruega", "status": "Por definir"},
    "P92": {"team1": "México", "team2": "Inglaterra", "status": "Por definir"},
    "P97": {"team1": "Marruecos", "team2": "Francia", "status": "Por definir"},
}


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    games = payload.get("games", payload if isinstance(payload, list) else [])

    for game in games:
        update = UPDATES.get(str(game.get("id", "")))
        if update:
            game.update(update)

    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    text = BRACKET_PATH.read_text(encoding="utf-8")
    text = text.replace("leftR16=[[89,3],[90,10],[93,18],[94,25]]", "leftR16=[[90,3],[89,10],[93,18],[94,25]]")
    BRACKET_PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
