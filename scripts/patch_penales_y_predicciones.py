#!/usr/bin/env python3
"""Corrige el cruce de octavos Canadá vs Marruecos en datos y bracket."""

import json
from pathlib import Path

PATCH_RUN = "2026-06-30-01"
DATA_PATH = Path("worldcup_results.json")
BRACKET_PATH = Path("clasificacion.html")


def patch_results() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    games = payload.get("games", payload if isinstance(payload, list) else [])

    for game in games:
        game_id = str(game.get("id", ""))

        if game_id == "P90":
            game["team1"] = "Canadá"
            game["team2"] = "Marruecos"
            notes = str(game.get("notes", ""))
            marker = "Cruce confirmado: Canadá vs Marruecos"
            if marker not in notes:
                game["notes"] = f"{notes} · {marker}" if notes else marker

        if game_id == "P89":
            game["team1"] = "Paraguay"
            game["team2"] = "Ganador P77"
            notes = str(game.get("notes", ""))
            marker = "Cruce confirmado: Paraguay vs ganador P77"
            if marker not in notes:
                game["notes"] = f"{notes} · {marker}" if notes else marker

    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def patch_bracket() -> None:
    text = BRACKET_PATH.read_text(encoding="utf-8")
    text = text.replace(
        "leftR16=[[89,3],[90,10],[93,18],[94,25]]",
        "leftR16=[[90,3],[89,10],[93,18],[94,25]]",
    )
    BRACKET_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    patch_results()
    patch_bracket()


if __name__ == "__main__":
    main()
