#!/usr/bin/env python3
"""Propaga ganadores de eliminatorias hacia los siguientes cruces.

Este script mantiene el JSON como fuente de verdad para todas las páginas.
Cuando un partido queda en Final, toma su ganador y lo coloca en el siguiente
partido correspondiente si el campo todavía está vacío o tiene un placeholder.
"""

import json
import re
from pathlib import Path

DATA_FILE = Path("worldcup_results.json")

# Ruta de avance usada por las páginas del dashboard.
# Cada tupla indica: partido destino, fuente para team1, fuente para team2.
ADVANCEMENT_PATH = [
    (90, 73, 75),
    (89, 74, 77),
    (91, 76, 78),
    (92, 79, 80),
    (93, 83, 84),
    (94, 81, 82),
    (95, 86, 88),
    (96, 85, 87),
    (97, 90, 89),
    (98, 93, 94),
    (99, 91, 92),
    (100, 95, 96),
    (101, 97, 98),
    (102, 99, 100),
    (104, 101, 102),
]

# Partido por tercer lugar: usa perdedores de semifinales.
THIRD_PLACE_PATH = (103, 101, 102)


def parse_score(value):
    """Convierte '2 - 1' en una tupla de enteros."""
    match = re.search(r"(\d+)\s*-\s*(\d+)", str(value or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


def is_placeholder(value):
    """Detecta textos que deben reemplazarse por equipos reales."""
    text = str(value or "")
    return not text or bool(re.search(r"Round of|Winner|Loser|Ganador|Perdedor|Grupo|TBD", text, re.I))


def match_id(game):
    """Obtiene el id interno P## del partido."""
    text = str(game.get("id") or game.get("notes") or "")
    match = re.search(r"P\d+", text)
    return match.group(0) if match else text


def games_by_id(games):
    """Crea un índice por id interno P##."""
    return {match_id(game): game for game in games}


def winner(game):
    """Devuelve el ganador real de un partido finalizado.

    Si el marcador regular termina empatado y existe campo penalties,
    el ganador se decide por penales.
    """
    if not game or str(game.get("status", "")).lower() != "final":
        return None

    score = parse_score(game.get("score"))
    if not score:
        return None

    if score[0] > score[1]:
        return game.get("team1")
    if score[1] > score[0]:
        return game.get("team2")

    penalties = parse_score(game.get("penalties"))
    if not penalties:
        return None
    if penalties[0] > penalties[1]:
        return game.get("team1")
    if penalties[1] > penalties[0]:
        return game.get("team2")

    return None


def loser(game):
    """Devuelve el perdedor real de un partido finalizado."""
    if not game or str(game.get("status", "")).lower() != "final":
        return None

    win = winner(game)
    if not win:
        return None
    if game.get("team1") == win:
        return game.get("team2")
    if game.get("team2") == win:
        return game.get("team1")
    return None


def set_team_if_needed(game, field, value):
    """Reemplaza placeholders o valores obsoletos por equipos confirmados."""
    if not game or not value:
        return False
    current = game.get(field, "")
    if current == value:
        return False
    if is_placeholder(current) or str(game.get("status", "")).lower() != "final":
        game[field] = value
        return True
    return False


def add_note(game, note):
    """Agrega una nota breve sin duplicarla."""
    existing = str(game.get("notes", ""))
    if note not in existing:
        game["notes"] = f"{existing} · {note}" if existing else note


def propagate(games):
    """Propaga todos los ganadores disponibles hacia partidos futuros."""
    index = games_by_id(games)
    changed = 0

    for target_num, source_one, source_two in ADVANCEMENT_PATH:
        target = index.get(f"P{target_num}")
        first_winner = winner(index.get(f"P{source_one}"))
        second_winner = winner(index.get(f"P{source_two}"))

        if set_team_if_needed(target, "team1", first_winner):
            changed += 1
        if set_team_if_needed(target, "team2", second_winner):
            changed += 1

        if target and (first_winner or second_winner):
            add_note(target, "Knockout propagation update")

    target_num, source_one, source_two = THIRD_PLACE_PATH
    target = index.get(f"P{target_num}")
    first_loser = loser(index.get(f"P{source_one}"))
    second_loser = loser(index.get(f"P{source_two}"))

    if set_team_if_needed(target, "team1", first_loser):
        changed += 1
    if set_team_if_needed(target, "team2", second_loser):
        changed += 1

    if target and (first_loser or second_loser):
        add_note(target, "Knockout propagation update")

    return changed


def main():
    """Carga el JSON, propaga cruces y guarda si hubo cambios."""
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    games = payload.get("games", payload if isinstance(payload, list) else [])

    changed = propagate(games)
    if changed:
        DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Propagated knockout teams: {changed} field(s) updated")
    else:
        print("No knockout propagation changes needed")


if __name__ == "__main__":
    main()
