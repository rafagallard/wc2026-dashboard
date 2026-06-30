#!/usr/bin/env python3
"""Actualiza automáticamente worldcup_results.json para el dashboard.

Fuentes usadas:
1. FIFA official matches API.
2. ESPN public scoreboard como respaldo.

Notas de mantenimiento:
- Los partidos de fase de grupos se empatan por id, fecha y equipos.
- Los partidos eliminatorios se empatan por fecha/hora local porque el JSON local usa ids internos
  como P73, P74, etc., mientras ESPN/FIFA usan otros ids.
- ESPN entrega fechas en UTC; este script las convierte a America/Mexico_City antes de comparar.
- Cuando un partido eliminatorio ya tiene equipos reales, se reemplazan placeholders como
  "2º Grupo A" o "Ganador P73" por el nombre real del equipo.
"""

import datetime
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_FILE = Path("worldcup_results.json")
LOCAL_TZ = ZoneInfo("America/Mexico_City")

FIFA_URL = os.getenv(
    "FIFA_MATCHES_URL",
    "https://api.fifa.com/api/v3/calendar/matches?language=en&count=500&idSeason=285023",
)

ESPN_URL_TEMPLATE = os.getenv(
    "ESPN_SCOREBOARD_URL_TEMPLATE",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?limit=300&dates={date}",
)

ESPN_RANGE_URL = os.getenv(
    "ESPN_SCOREBOARD_RANGE_URL",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?limit=300&dates=20260611-20260719",
)

ALIASES = {
    "mexico": "México", "méxico": "México", "south africa": "Sudáfrica",
    "korea republic": "Corea del Sur", "south korea": "Corea del Sur", "republic of korea": "Corea del Sur",
    "czechia": "Chequia", "czech republic": "Chequia", "canada": "Canadá",
    "bosnia and herz.": "Bosnia y Herzegovina", "bosnia and herzegovina": "Bosnia y Herzegovina",
    "qatar": "Qatar", "switzerland": "Suiza", "suisse": "Suiza",
    "united states": "Estados Unidos", "usa": "Estados Unidos", "u s a": "Estados Unidos", "us": "Estados Unidos",
    "australia": "Australia", "paraguay": "Paraguay", "turkey": "Turquía", "türkiye": "Turquía",
    "brazil": "Brasil", "morocco": "Marruecos", "haiti": "Haití", "scotland": "Escocia",
    "germany": "Alemania", "curacao": "Curazao", "curaçao": "Curazao",
    "ivory coast": "Costa de Marfil", "cote d ivoire": "Costa de Marfil", "côte d’ivoire": "Costa de Marfil",
    "côte d'ivoire": "Costa de Marfil", "ecuador": "Ecuador", "netherlands": "Países Bajos",
    "japan": "Japón", "sweden": "Suecia", "tunisia": "Túnez", "belgium": "Bélgica",
    "egypt": "Egipto", "iran": "Irán", "new zealand": "Nueva Zelanda", "spain": "España",
    "cape verde": "Cabo Verde", "saudi arabia": "Arabia Saudita", "uruguay": "Uruguay",
    "france": "Francia", "senegal": "Senegal", "iraq": "Irak", "norway": "Noruega",
    "argentina": "Argentina", "algeria": "Argelia", "austria": "Austria", "jordan": "Jordania",
    "portugal": "Portugal", "dr congo": "RD Congo", "congo dr": "RD Congo", "democratic republic of congo": "RD Congo",
    "uzbekistan": "Uzbekistán", "colombia": "Colombia", "england": "Inglaterra",
    "croatia": "Croacia", "ghana": "Ghana", "panama": "Panamá",
}


def now_iso():
    """Devuelve la fecha/hora actual en formato ISO para registrar la actualización."""
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json_url(url):
    """Descarga JSON desde una URL con un User-Agent válido para evitar bloqueos simples."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=35) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_text(value):
    """Normaliza texto para comparar nombres de equipos y estados sin depender de mayúsculas o signos."""
    value = str(value or "").strip().lower().replace("’", "'")
    value = re.sub(r"[^a-z0-9áéíóúüñç' ]+", " ", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def ascii_fold(value):
    """Remueve acentos comunes para comparar aliases en inglés y español."""
    return (value.replace("á", "a").replace("é", "e").replace("í", "i")
                 .replace("ó", "o").replace("ú", "u").replace("ü", "u")
                 .replace("ñ", "n"))


def team_key(value):
    """Convierte un nombre de equipo a la versión canónica usada por el dashboard."""
    cleaned = normalize_text(value)
    folded = ascii_fold(cleaned)
    return ALIASES.get(cleaned) or ALIASES.get(folded) or str(value or "")


def pair_key(team1, team2):
    """Crea una llave estable para comparar dos equipos sin importar el orden."""
    return tuple(sorted([team_key(team1), team_key(team2)]))


def date_pair_key(date, team1, team2):
    """Crea una llave por fecha y pareja de equipos."""
    return (str(date or ""),) + pair_key(team1, team2)


def date_time_key(date, time_value):
    """Crea una llave por fecha y hora local del partido."""
    return (str(date or ""), str(time_value or "")[:5])


def source_datetime_to_local(raw_date):
    """Convierte fecha/hora de una fuente externa a fecha y hora local del dashboard.

    ESPN normalmente entrega ISO en UTC con sufijo Z. Al convertirlo a America/Mexico_City,
    el P73 queda 2026-06-28 13:00 y ya puede empatar contra el JSON local.
    """
    raw = str(raw_date or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        return "", ""

    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", raw):
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return raw[:10], raw[11:16]
            local = parsed.astimezone(LOCAL_TZ)
            return local.strftime("%Y-%m-%d"), local.strftime("%H:%M")
        except ValueError:
            return raw[:10], raw[11:16]

    return raw[:10], ""


def first_value(obj, keys):
    """Busca el primer valor presente dentro de un diccionario para una lista de llaves posibles."""
    if not isinstance(obj, dict):
        return None
    for key in keys:
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
    return None


def all_scalar_values(obj, path=""):
    """Recorre una estructura JSON y entrega todas las hojas escalares con su ruta."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from all_scalar_values(value, f"{path}.{key}" if path else key)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from all_scalar_values(value, f"{path}[{index}]")
    else:
        yield path, obj


def text_from_localized(value):
    """Extrae texto desde estructuras localizadas de FIFA."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                locale = normalize_text(item.get("Locale") or item.get("locale") or item.get("Language") or item.get("language"))
                if locale in {"en", "en us", "en gb"}:
                    text = text_from_localized(first_value(item, ["Description", "description", "Name", "name", "Text", "text"]))
                    if text:
                        return text
        for item in value:
            text = text_from_localized(item)
            if text:
                return text
    if isinstance(value, dict):
        direct = first_value(value, [
            "Description", "description", "Name", "name", "DisplayName", "displayName",
            "ShortName", "shortName", "Abbreviation", "abbreviation", "Text", "text", "Value", "value",
        ])
        return text_from_localized(direct) if direct is not None else ""
    return ""


def extract_team_name(team_obj):
    """Extrae nombre de equipo desde un string o estructura de equipo."""
    if isinstance(team_obj, str):
        return team_obj
    if isinstance(team_obj, dict):
        for key in [
            "Name", "name", "TeamName", "teamName", "DisplayName", "displayName",
            "ShortName", "shortName", "CountryName", "countryName", "Abbreviation", "abbreviation",
        ]:
            text = text_from_localized(team_obj.get(key))
            if text:
                return text
    return text_from_localized(team_obj)


def to_int(value):
    """Convierte un valor a entero si contiene un marcador válido."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        match = re.search(r"\d+", str(value))
        return int(match.group(0)) if match else None


def find_score_near(obj, side):
    """Busca marcador local/visitante dentro de estructuras anidadas."""
    if not isinstance(obj, dict):
        return None

    side_words = {
        "home": ["home", "homeTeam", "HomeTeam", "Home"],
        "away": ["away", "awayTeam", "AwayTeam", "Away"],
    }[side]

    direct_keys = []
    for side_word in side_words:
        direct_keys.extend([
            f"{side_word}Score", f"{side_word}TeamScore", f"{side_word}Goals",
            f"{side_word}TeamGoals", f"{side_word}Result", f"{side_word}FTScore",
        ])

    expanded = set(direct_keys)
    for key in list(direct_keys):
        expanded.add(key[:1].upper() + key[1:])
        expanded.add(key[:1].lower() + key[1:])

    for key in expanded:
        if key in obj:
            val = to_int(obj[key])
            if val is not None:
                return val

    team_obj = first_value(obj, side_words)
    if isinstance(team_obj, dict):
        nested = first_value(team_obj, [
            "Score", "score", "Goals", "goals", "TeamScore", "teamScore",
            "TotalScore", "totalScore", "Result", "result",
        ])
        val = to_int(nested)
        if val is not None:
            return val

    for container_key in ["Result", "result", "Score", "score", "MatchResult", "matchResult"]:
        container = obj.get(container_key)
        if isinstance(container, dict):
            val = find_score_near(container, side)
            if val is not None:
                return val

    for path, value in all_scalar_values(obj):
        p = path.lower()
        if side in p and any(word in p for word in ["score", "goal", "goals"]):
            val = to_int(value)
            if val is not None:
                return val

    return None


def penalty_score_near(obj, side):
    """Busca marcador de penales local/visitante en estructuras de FIFA o ESPN."""
    if not isinstance(obj, dict):
        return None

    side_terms = {
        "home": ["home", "homeTeam", "HomeTeam", "Home"],
        "away": ["away", "awayTeam", "AwayTeam", "Away"],
    }[side]

    for path, value in all_scalar_values(obj):
        lowered = path.lower()
        if any(term.lower() in lowered for term in side_terms) and any(term in lowered for term in ["penalty", "penalties", "shootout"]):
            val = to_int(value)
            if val is not None:
                return val

    return None


def penalty_value_from_competitor(competitor):
    """Obtiene goles de tanda de penales desde un competidor de ESPN."""
    for key in ["shootoutScore", "penaltyScore", "penalties", "penaltyShootoutScore"]:
        val = to_int((competitor or {}).get(key))
        if val is not None:
            return val
    return penalty_score_near(competitor, "home")


def normalize_status(raw_status, match_obj=None):
    """Normaliza estatus de partido evitando marcar como en vivo por códigos numéricos ambiguos."""
    raw_text = text_from_localized(raw_status) if isinstance(raw_status, (dict, list)) else str(raw_status or "")
    status_text = normalize_text(raw_text)

    if status_text in {
        "ft", "full time", "fulltime", "finished", "final", "played", "completed",
        "result", "post match", "postmatch", "ended", "match finished",
    }:
        return "Final"

    if status_text in {
        "live", "in progress", "first half", "second half", "half time", "halftime", "ht",
    }:
        return "En vivo"

    if isinstance(match_obj, dict):
        for path, value in all_scalar_values(match_obj):
            p = path.lower()
            if any(word in p for word in ["status", "period", "phase", "state"]):
                text = normalize_text(value)
                if text in {"ft", "full time", "fulltime", "finished", "final", "played", "completed", "ended"}:
                    return "Final"
                if text in {"live", "in progress", "first half", "second half", "half time", "halftime", "ht"}:
                    return "En vivo"

        finished_flag = first_value(match_obj, ["Finished", "finished", "IsFinished", "isFinished", "Completed", "completed"])
        if str(finished_flag).lower() in {"true", "1", "yes"}:
            return "Final"

    return "Programado"


def find_matches_list(payload):
    """Encuentra la lista de partidos dentro de las diferentes formas de respuesta de FIFA."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in ["Results", "results", "Matches", "matches", "Items", "items", "Data", "data"]:
        value = payload.get(key)
        if isinstance(value, list):
            return value

    candidates = []

    def walk(value):
        if isinstance(value, list):
            score = 0
            for item in value[:5]:
                if isinstance(item, dict) and (set(item.keys()) & {"IdMatch", "idMatch", "MatchId", "HomeTeam", "AwayTeam", "Home", "Away"}):
                    score += 1
            if score:
                candidates.append((score, value))
        elif isinstance(value, dict):
            for child in value.values():
                walk(child)

    walk(payload)
    return sorted(candidates, key=lambda item: item[0], reverse=True)[0][1] if candidates else []


def extract_fifa_update(match):
    """Convierte un partido de FIFA al formato interno de actualización."""
    if not isinstance(match, dict):
        return None

    match_id = first_value(match, ["IdMatch", "idMatch", "MatchId", "matchId", "Id", "id"])
    date_raw = first_value(match, ["Date", "date", "MatchDate", "matchDate", "MatchDateTime", "matchDateTime", "LocalDate", "localDate", "DateLocal", "dateLocal"])
    date, time_value = source_datetime_to_local(date_raw)

    home_team_obj = first_value(match, ["HomeTeam", "homeTeam", "Home", "home"])
    away_team_obj = first_value(match, ["AwayTeam", "awayTeam", "Away", "away"])
    home_team = extract_team_name(home_team_obj)
    away_team = extract_team_name(away_team_obj)

    if not home_team or not away_team:
        return None

    home_score = find_score_near(match, "home")
    away_score = find_score_near(match, "away")
    home_penalties = penalty_score_near(match, "home")
    away_penalties = penalty_score_near(match, "away")
    status_raw = first_value(match, [
        "MatchStatus", "matchStatus", "Status", "status", "MatchStatusName", "matchStatusName",
        "Period", "period", "MatchPeriod", "matchPeriod", "Phase", "phase",
    ])
    status = normalize_status(status_raw, match)

    return {
        "source": "FIFA",
        "event_id": str(match_id or ""),
        "date": date,
        "time": time_value,
        "teams": [team_key(home_team), team_key(away_team)],
        "scores": [home_score, away_score],
        "penalties": [home_penalties, away_penalties],
        "penalties_available": status == "Final" and home_penalties is not None and away_penalties is not None,
        "score_available": status != "Programado" and home_score is not None and away_score is not None,
        "status": status,
        "raw_teams": [team_key(home_team), team_key(away_team)],
    }


def extract_espn_update(event):
    """Convierte un partido de ESPN al formato interno de actualización."""
    comp = (event.get("competitions") or [{}])[0]
    competitors = comp.get("competitors") or []
    if len(competitors) != 2:
        return None

    teams, scores, penalties = [], [], []
    for competitor in competitors:
        team = competitor.get("team") or {}
        name = team.get("displayName") or team.get("shortDisplayName") or team.get("name") or ""
        teams.append(team_key(name))
        scores.append(str(competitor.get("score", "")).strip())
        penalties.append(penalty_value_from_competitor(competitor))

    status_type = (comp.get("status") or {}).get("type") or {}
    status_name = str(status_type.get("name") or status_type.get("state") or "").upper()
    completed = bool(status_type.get("completed"))

    if completed or status_name in {"STATUS_FINAL", "STATUS_FULL_TIME", "FINAL", "FULL_TIME", "POST"}:
        status = "Final"
    elif status_name in {"STATUS_IN_PROGRESS", "STATUS_HALFTIME", "STATUS_FIRST_HALF", "STATUS_SECOND_HALF", "IN", "LIVE"}:
        status = "En vivo"
    else:
        status = "Programado"

    date, time_value = source_datetime_to_local(event.get("date"))

    return {
        "source": "ESPN",
        "event_id": str(event.get("id") or ""),
        "date": date,
        "time": time_value,
        "teams": teams,
        "scores": [to_int(scores[0]), to_int(scores[1])],
        "penalties": penalties,
        "penalties_available": status == "Final" and all(item is not None for item in penalties),
        "score_available": status != "Programado" and all(score.isdigit() for score in scores),
        "status": status,
        "raw_teams": teams,
    }


def game_indexes(games):
    """Construye índices para empatar actualizaciones con juegos del dashboard."""
    by_id, by_date_pair, by_pair, by_date_time = {}, {}, {}, {}
    for game in games:
        if game.get("id"):
            by_id[str(game.get("id"))] = game
        by_date_pair[date_pair_key(game.get("date"), game.get("team1"), game.get("team2"))] = game
        by_pair[pair_key(game.get("team1"), game.get("team2"))] = game
        key = date_time_key(game.get("date"), game.get("time"))
        by_date_time.setdefault(key, []).append(game)
    return by_id, by_date_pair, by_pair, by_date_time


def find_matching_game(update, by_id, by_date_pair, by_pair, by_date_time):
    """Busca el juego local correspondiente a una actualización externa."""
    if update["event_id"] and update["event_id"] in by_id:
        return by_id[update["event_id"]], "id"

    dated = by_date_pair.get((update["date"],) + tuple(sorted(update["teams"])))
    if dated:
        return dated, "date_pair"

    paired = by_pair.get(tuple(sorted(update["teams"])))
    if paired:
        return paired, "pair"

    candidates = by_date_time.get(date_time_key(update.get("date"), update.get("time")), [])
    ko_candidates = [game for game in candidates if game.get("group") == "KO"]
    if len(ko_candidates) == 1:
        return ko_candidates[0], "date_time"

    return None, ""


def score_in_dashboard_order(game, update):
    """Genera el marcador en el orden en el que se muestra el partido en el dashboard."""
    if not update["score_available"]:
        return None
    if team_key(game.get("team1")) == update["teams"][0]:
        return f"{update['scores'][0]} - {update['scores'][1]}"
    if team_key(game.get("team2")) == update["teams"][0]:
        return f"{update['scores'][1]} - {update['scores'][0]}"
    return f"{update['scores'][0]} - {update['scores'][1]}"


def penalties_in_dashboard_order(game, update):
    """Genera el marcador de penales en el orden del dashboard."""
    if not update.get("penalties_available"):
        return None
    penalties = update.get("penalties") or []
    if len(penalties) != 2:
        return None
    if team_key(game.get("team1")) == update["teams"][0]:
        return f"{penalties[0]} - {penalties[1]}"
    if team_key(game.get("team2")) == update["teams"][0]:
        return f"{penalties[1]} - {penalties[0]}"
    return f"{penalties[0]} - {penalties[1]}"


def is_placeholder(value):
    """Detecta placeholders de cruces eliminatorios."""
    text = str(value or "")
    return bool(re.search(r"Grupo|Ganador|Perdedor|^\d[A-L]$", text))


def should_apply_update(game, new_score, new_status, match_method):
    """Decide si la actualización externa debe modificar el juego local."""
    old_score = game.get("score", "")
    old_status = game.get("status", "")

    if old_status == "Final" and new_status != "Final":
        return False
    if old_status == "Final" and old_score and new_score is None:
        return False
    if new_status == "Programado":
        return False

    return (new_score is not None and old_score != new_score) or (new_status and old_status != new_status)


def apply_update(game, update, match_method):
    """Aplica una actualización externa al juego local."""
    changed = False

    if match_method == "date_time" and game.get("group") == "KO":
        if is_placeholder(game.get("team1")) and update["raw_teams"][0]:
            game["team1"] = update["raw_teams"][0]
            changed = True
        if is_placeholder(game.get("team2")) and update["raw_teams"][1]:
            game["team2"] = update["raw_teams"][1]
            changed = True

    new_score = score_in_dashboard_order(game, update)
    new_penalties = penalties_in_dashboard_order(game, update)
    new_status = update["status"]

    if should_apply_update(game, new_score, new_status, match_method):
        if new_score is not None:
            game["score"] = new_score
            changed = True
        if new_status:
            game["status"] = new_status
            changed = True

    if new_penalties is not None and game.get("penalties", "") != new_penalties:
        game["penalties"] = new_penalties
        changed = True

    if changed:
        source_note = f"{update['source']} automatic update"
        existing_notes = game.get("notes", "")
        if source_note not in existing_notes:
            game["notes"] = f"{existing_notes} · {source_note}" if existing_notes else source_note
        print(f"Applied {update['source']} update: {game.get('team1')} {game.get('score')} {game.get('team2')} [{game.get('status')}] via {match_method}")

    return changed


def collect_fifa_updates():
    """Descarga y normaliza actualizaciones desde FIFA."""
    try:
        payload = load_json_url(FIFA_URL)
    except Exception as exc:
        print(f"Unable to load FIFA feed: {exc}")
        return []

    matches = find_matches_list(payload)
    updates = [update for match in matches if (update := extract_fifa_update(match))]
    finals = sum(1 for update in updates if update["status"] == "Final")
    with_scores = sum(1 for update in updates if update["score_available"])
    print(f"Fetched FIFA matches: {len(updates)} updates, {with_scores} with scores, {finals} final")
    return updates


def collect_espn_updates(dates):
    """Descarga y normaliza actualizaciones desde ESPN por fecha y por rango."""
    events_by_id = {}

    for date in sorted(set(dates)):
        espn_date = str(date or "").replace("-", "")[:8]
        if not espn_date:
            continue

        try:
            feed = load_json_url(ESPN_URL_TEMPLATE.format(date=espn_date))
            for event in feed.get("events", []):
                event_id = str(event.get("id") or f"{espn_date}-{len(events_by_id)}")
                events_by_id[event_id] = event
            print(f"Fetched ESPN date {espn_date}: {len(feed.get('events', []))} events")
        except Exception as exc:
            print(f"Unable to load ESPN date {espn_date}: {exc}")

        time.sleep(0.15)

    try:
        feed = load_json_url(ESPN_RANGE_URL)
        for event in feed.get("events", []):
            event_id = str(event.get("id") or f"range-{len(events_by_id)}")
            events_by_id[event_id] = event
        print(f"Fetched ESPN range: {len(feed.get('events', []))} events")
    except Exception as exc:
        print(f"Unable to load ESPN range feed: {exc}")

    updates = [update for event in events_by_id.values() if (update := extract_espn_update(event))]
    finals = sum(1 for update in updates if update["status"] == "Final")
    with_scores = sum(1 for update in updates if update["score_available"])
    print(f"Fetched ESPN updates: {len(updates)} updates, {with_scores} with scores, {finals} final")
    return updates


def main():
    """Ejecuta el proceso completo de actualización del JSON."""
    if not DATA_FILE.exists():
        print("worldcup_results.json not found")
        return 1

    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    games = payload["games"] if isinstance(payload, dict) else payload
    dates = [game.get("date") for game in games if game.get("date")]

    by_id, by_date_pair, by_pair, by_date_time = game_indexes(games)
    updates = collect_fifa_updates() + collect_espn_updates(dates)

    matched = 0
    changed = 0

    for update in updates:
        game, match_method = find_matching_game(update, by_id, by_date_pair, by_pair, by_date_time)
        if not game:
            continue

        matched += 1
        if apply_update(game, update, match_method):
            changed += 1
            by_id, by_date_pair, by_pair, by_date_time = game_indexes(games)

    print(f"Matched source updates to dashboard games: {matched}")

    if changed:
        output = {
            "updatedAt": now_iso(),
            "timezone": payload.get("timezone", "America/Mexico_City") if isinstance(payload, dict) else "America/Mexico_City",
            "refreshHours": 1,
            "sourceLabel": "FIFA official matches API + ESPN public scoreboard",
            "games": games,
        }
        DATA_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Updated {changed} matches")
    else:
        print("No match score changes found")

    return 0


if __name__ == "__main__":
    sys.exit(main())
