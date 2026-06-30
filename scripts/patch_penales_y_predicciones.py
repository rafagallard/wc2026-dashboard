#!/usr/bin/env python3
"""Limpia el filtro de fecha en predicciones y deja los partidos cerrados bloqueados."""

from pathlib import Path

PATH = Path("predicciones.html")


def replace_all(text: str, old: str, new: str) -> str:
    while old in text:
        text = text.replace(old, new)
    return text


def main() -> None:
    text = PATH.read_text(encoding="utf-8")

    text = text.replace("Predicciones del día", "Predicciones por fecha")
    text = text.replace(
        "No hay partidos programados para hoy.",
        "No hay partidos programados para la fecha seleccionada.",
    )

    text = text.replace(
        "${penaltyHTML(g)}${penaltyHTML(g)}<div class=\"venue\">${esc(g.venue||'')}</div></article>",
        "${penaltyHTML(g)}<div class=\"venue\">${esc(g.venue||'')}</div></article>",
    )

    duplicate_listener = "$('predictionDate')?.addEventListener('change',()=>{renderTodayMatches();buildMatchSelector();renderTodayPredictions();renderWinners();renderSelectedHistory();updateSelectedTeams()});$('predictionDate')?.addEventListener('change',()=>{renderTodayMatches();buildMatchSelector();renderTodayPredictions();renderWinners();renderSelectedHistory();updateSelectedTeams()});"
    single_listener = "$('predictionDate')?.addEventListener('change',()=>{renderTodayMatches();buildMatchSelector();renderTodayPredictions();renderWinners();renderSelectedHistory();updateSelectedTeams()});"
    text = replace_all(text, duplicate_listener, single_listener)

    text = text.replace(
        "if(!list.length){$('matchSelect').innerHTML='<option value=\"\">No hay partidos programados para hoy</option>'}",
        "if(!list.length){$('matchSelect').innerHTML='<option value=\"\">No hay partidos programados para la fecha seleccionada</option>'}",
    )

    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
