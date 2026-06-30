#!/usr/bin/env python3
"""Agrega soporte de penales y filtro de fecha para predicciones."""

from pathlib import Path


PATCH_VERSION = "2026-06-29-2"


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def replace(text: str, old: str, new: str) -> str:
    if old not in text:
        print(f"No se encontró bloque para reemplazo: {old[:80]!r}")
        return text
    return text.replace(old, new, 1)


def patch_data_script() -> None:
    text = read("scripts/update_worldcup_results.py")

    if "def penalty_score_near" not in text:
        text = replace(
            text,
            "def normalize_status(raw_status, match_obj=None):",
            '''def penalty_score_near(obj, side):\n    """Busca marcador de penales local/visitante en estructuras de FIFA o ESPN."""\n    if not isinstance(obj, dict):\n        return None\n\n    side_terms = {\n        "home": ["home", "homeTeam", "HomeTeam", "Home"],\n        "away": ["away", "awayTeam", "AwayTeam", "Away"],\n    }[side]\n\n    for path, value in all_scalar_values(obj):\n        lowered = path.lower()\n        if any(term.lower() in lowered for term in side_terms) and any(term in lowered for term in ["penalty", "penalties", "shootout"]):\n            val = to_int(value)\n            if val is not None:\n                return val\n\n    return None\n\n\ndef penalty_value_from_competitor(competitor):\n    """Obtiene goles de tanda de penales desde un competidor de ESPN."""\n    for key in ["shootoutScore", "penaltyScore", "penalties", "penaltyShootoutScore"]:\n        val = to_int((competitor or {}).get(key))\n        if val is not None:\n            return val\n    return None\n\n\ndef normalize_status(raw_status, match_obj=None):''',
        )

    text = replace(
        text,
        '    home_score = find_score_near(match, "home")\n    away_score = find_score_near(match, "away")',
        '    home_score = find_score_near(match, "home")\n    away_score = find_score_near(match, "away")\n    home_penalties = penalty_score_near(match, "home")\n    away_penalties = penalty_score_near(match, "away")',
    )
    text = replace(
        text,
        '        "scores": [home_score, away_score],\n        "score_available": status != "Programado" and home_score is not None and away_score is not None,',
        '        "scores": [home_score, away_score],\n        "penalties": [home_penalties, away_penalties],\n        "penalties_available": status == "Final" and home_penalties is not None and away_penalties is not None,\n        "score_available": status != "Programado" and home_score is not None and away_score is not None,',
    )
    text = replace(
        text,
        '    teams, scores = [], []\n    for competitor in competitors:\n        team = competitor.get("team") or {}\n        name = team.get("displayName") or team.get("shortDisplayName") or team.get("name") or ""\n        teams.append(team_key(name))\n        scores.append(str(competitor.get("score", "")).strip())',
        '    teams, scores, penalties = [], [], []\n    for competitor in competitors:\n        team = competitor.get("team") or {}\n        name = team.get("displayName") or team.get("shortDisplayName") or team.get("name") or ""\n        teams.append(team_key(name))\n        scores.append(str(competitor.get("score", "")).strip())\n        penalties.append(penalty_value_from_competitor(competitor))',
    )
    text = replace(
        text,
        '        "scores": [to_int(scores[0]), to_int(scores[1])],\n        "score_available": status != "Programado" and all(score.isdigit() for score in scores),',
        '        "scores": [to_int(scores[0]), to_int(scores[1])],\n        "penalties": penalties,\n        "penalties_available": status == "Final" and all(item is not None for item in penalties),\n        "score_available": status != "Programado" and all(score.isdigit() for score in scores),',
    )

    if "def penalties_in_dashboard_order" not in text:
        text = replace(
            text,
            "def is_placeholder(value):",
            '''def penalties_in_dashboard_order(game, update):\n    """Genera el marcador de penales en el orden del dashboard."""\n    if not update.get("penalties_available"):\n        return None\n    penalties = update.get("penalties") or []\n    if len(penalties) != 2:\n        return None\n    if team_key(game.get("team1")) == update["teams"][0]:\n        return f"{penalties[0]} - {penalties[1]}"\n    if team_key(game.get("team2")) == update["teams"][0]:\n        return f"{penalties[1]} - {penalties[0]}"\n    return f"{penalties[0]} - {penalties[1]}"\n\n\ndef is_placeholder(value):''',
        )

    text = replace(
        text,
        '    new_score = score_in_dashboard_order(game, update)\n    new_status = update["status"]',
        '    new_score = score_in_dashboard_order(game, update)\n    new_penalties = penalties_in_dashboard_order(game, update)\n    new_status = update["status"]',
    )
    text = replace(
        text,
        '        if new_status:\n            game["status"] = new_status\n            changed = True',
        '        if new_status:\n            game["status"] = new_status\n            changed = True\n\n    if new_penalties is not None and game.get("penalties", "") != new_penalties:\n        game["penalties"] = new_penalties\n        changed = True',
    )

    write("scripts/update_worldcup_results.py", text)


def patch_index() -> None:
    text = read("index.html")
    if "function penaltyHTML" not in text:
        text = text.replace(
            "function parseScore(score){const m=String(score||'').match(/(\\d+)\\s*-\\s*(\\d+)/);return m?[Number(m[1]),Number(m[2])]:null}",
            "function parseScore(score){const m=String(score||'').match(/(\\d+)\\s*-\\s*(\\d+)/);return m?[Number(m[1]),Number(m[2])]:null}function penaltyHTML(g){return g?.penalties?`<div class=\"match-meta\"><strong>Penales: ${esc(g.penalties)}</strong></div>`:''}",
        )
    text = text.replace(
        "${sideHTML(g.team1)}${sideHTML(g.team2)}<div class=\"match-meta\">",
        "${sideHTML(g.team1)}${sideHTML(g.team2)}${penaltyHTML(g)}<div class=\"match-meta\">",
    )
    text = text.replace(
        "function winnerFromGame(g){if(!g||String(g.status||'').toLowerCase()!=='final')return null;const s=parseScore(g.score);if(!s)return null;const side=s[0]>s[1]?g.team1:s[1]>s[0]?g.team2:null;if(!side)return null;const r=resolveSlot(side);return r?.name||side}",
        "function winnerFromGame(g){if(!g||String(g.status||'').toLowerCase()!=='final')return null;const s=parseScore(g.score);if(!s)return null;const p=parseScore(g.penalties);const side=s[0]>s[1]?g.team1:s[1]>s[0]?g.team2:p&&p[0]>p[1]?g.team1:p&&p[1]>p[0]?g.team2:null;if(!side)return null;const r=resolveSlot(side);return r?.name||side}",
    )
    text = text.replace(
        "function loserFromGame(g){if(!g||String(g.status||'').toLowerCase()!=='final')return null;const s=parseScore(g.score);if(!s||s[0]===s[1])return null;const side=s[0]<s[1]?g.team1:g.team2;return realTeam(side)||side}",
        "function loserFromGame(g){if(!g||String(g.status||'').toLowerCase()!=='final')return null;const s=parseScore(g.score);if(!s)return null;const p=parseScore(g.penalties);const side=s[0]<s[1]?g.team1:s[1]<s[0]?g.team2:p&&p[0]<p[1]?g.team1:p&&p[1]<p[0]?g.team2:null;return side?(realTeam(side)||side):null}",
    )
    write("index.html", text)


def patch_clasificacion() -> None:
    text = read("clasificacion.html")
    if "function penaltyHTML" not in text:
        text = text.replace(
            "function parseScore(score){const m=String(score||'').match(/(\\d+)\\s*-\\s*(\\d+)/);return m?[Number(m[1]),Number(m[2])]:null}",
            "function parseScore(score){const m=String(score||'').match(/(\\d+)\\s*-\\s*(\\d+)/);return m?[Number(m[1]),Number(m[2])]:null}function penaltyHTML(g){return g?.penalties?`<div class=\"match-date\"><strong>Penales: ${esc(g.penalties)}</strong></div>`:''}",
        )
    text = text.replace(
        "function winnerIndex(g){const s=parseScore(g.score);if(!s||String(g.status||'').toLowerCase()!=='final'||s[0]===s[1])return -1;return s[0]>s[1]?0:1}",
        "function winnerIndex(g){const s=parseScore(g.score);if(!s||String(g.status||'').toLowerCase()!=='final')return -1;if(s[0]!==s[1])return s[0]>s[1]?0:1;const p=parseScore(g.penalties);if(!p||p[0]===p[1])return -1;return p[0]>p[1]?0:1}",
    )
    text = text.replace(
        "</div><div class=\"score\">${esc(sideScore(g,1))}</div></div></article>",
        "</div><div class=\"score\">${esc(sideScore(g,1))}</div></div>${penaltyHTML(g)}</article>",
    )
    write("clasificacion.html", text)


def patch_predicciones() -> None:
    text = read("predicciones.html")
    text = text.replace("<h2>Partidos del día</h2>", "<h2>Partidos de la fecha seleccionada</h2>")
    text = text.replace("<h3>Predicciones de hoy</h3>", "<h3>Predicciones de la fecha</h3>")
    text = text.replace("<h2>Ganadores del día</h2>", "<h2>Ganadores de la fecha</h2>")
    if "predictionDate" not in text:
        text = text.replace(
            "<main>\n  <section><div class=\"section-title\"><h2>Partidos de la fecha seleccionada</h2></div>",
            "<main>\n  <section><div class=\"section-title\"><h2>Fecha de partidos</h2></div><section class=\"card\"><div class=\"card-body\"><label for=\"predictionDate\">Selecciona una fecha</label><input id=\"predictionDate\" type=\"date\" /></div></section></section>\n  <section><div class=\"section-title\"><h2>Partidos de la fecha seleccionada</h2></div>",
        )
    if "function penaltyHTML" not in text:
        text = text.replace(
            "function parseScore(score){const m=String(score||'').match(/(\\d+)\\s*-\\s*(\\d+)/);return m?[Number(m[1]),Number(m[2])]:null}",
            "function parseScore(score){const m=String(score||'').match(/(\\d+)\\s*-\\s*(\\d+)/);return m?[Number(m[1]),Number(m[2])]:null}function penaltyHTML(g){return g?.penalties?`<div class=\"venue\"><strong>Penales: ${esc(g.penalties)}</strong></div>`:''}function resultText(g){return g?.penalties?`${g.score||''} · Penales: ${g.penalties}`:(g?.score||'')}",
        )
    text = text.replace(
        "function todayLocalDate(){return localDateKey(new Date())}",
        "function selectedPredictionDate(){return $('predictionDate')?.value||localDateKey(new Date())}function todayLocalDate(){return selectedPredictionDate()}",
    )
    text = text.replace(
        "<div class=\"venue\">${esc(g.venue||'')}</div></article>",
        "${penaltyHTML(g)}<div class=\"venue\">${esc(g.venue||'')}</div></article>",
    )
    text = text.replace(
        "finalScore:g.score,stage:g.stage||r.stage||'',group:g.group||r.group||'',venue:g.venue||''",
        "finalScore:resultText(g),stage:g.stage||r.stage||'',group:g.group||r.group||'',venue:g.venue||''",
    )
    text = text.replace(
        "games=Array.isArray(payload)?payload:payload.games;$('lastUpdated').textContent=payload.updatedAt?new Date(payload.updatedAt).toLocaleString('es-MX'):new Date().toLocaleString('es-MX');renderTodayMatches();buildMatchSelector();await refreshPredictions()",
        "games=Array.isArray(payload)?payload:payload.games;if($('predictionDate')&&!$('predictionDate').value)$('predictionDate').value=localDateKey(new Date());$('lastUpdated').textContent=payload.updatedAt?new Date(payload.updatedAt).toLocaleString('es-MX'):new Date().toLocaleString('es-MX');renderTodayMatches();buildMatchSelector();await refreshPredictions()",
    )
    text = text.replace(
        "$('matchSelect').addEventListener('change',updateSelectedTeams);",
        "$('predictionDate')?.addEventListener('change',()=>{renderTodayMatches();buildMatchSelector();renderTodayPredictions();renderWinners();renderSelectedHistory();updateSelectedTeams()});$('matchSelect').addEventListener('change',updateSelectedTeams);",
    )
    write("predicciones.html", text)


def main() -> None:
    patch_data_script()
    patch_index()
    patch_clasificacion()
    patch_predicciones()


if __name__ == "__main__":
    main()
