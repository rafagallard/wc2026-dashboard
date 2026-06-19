#!/usr/bin/env python3
"""Fully automated World Cup dashboard results updater.

Sources:
1. FIFA official calendar matches API as primary source.
2. ESPN public scoreboard as fallback source.

This version is more tolerant with FIFA's JSON structure:
- It searches team names, scores and status in common and nested fields.
- It logs how many FIFA/ESPN updates were found and matched.
- It does not use manual overrides.
"""

import json
import os
import re
import sys
import time
import urllib.request
import datetime
from pathlib import Path

DATA_FILE = Path("worldcup_results.json")

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
    "portugal": "Portugal", "dr congo": "RD Congo", "congo dr": "RD Congo",
    "uzbekistan": "Uzbekistán", "colombia": "Colombia", "england": "Inglaterra",
    "croatia": "Croacia", "ghana": "Ghana", "panama": "Panamá",
}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=35) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_text(value):
    value = str(value or "").strip().lower().replace("’", "'")
    value = re.sub(r"[^a-z0-9áéíóúüñç' ]+", " ", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def ascii_fold(value):
    return (value.replace("á", "a").replace("é", "e").replace("í", "i")
                 .replace("ó", "o").replace("ú", "u").replace("ü", "u")
                 .replace("ñ", "n"))


def team_key(value):
    cleaned = normalize_text(value)
    folded = ascii_fold(cleaned)
    return ALIASES.get(cleaned) or ALIASES.get(folded) or str(value or "")


def pair_key(team1, team2):
    return tuple(sorted([team_key(team1), team_key(team2)]))


def date_pair_key(date, team1, team2):
    return (str(date or ""),) + pair_key(team1, team2)


def first_value(obj, keys):
    if not isinstance(obj, dict):
        return None
    for key in keys:
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
    return None


def all_scalar_values(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from all_scalar_values(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from all_scalar_values(v, f"{path}[{i}]")
    else:
        yield path, obj


def text_from_localized(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        # Prefer English localized rows if available.
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
            "ShortName", "shortName", "Abbreviation", "abbreviation", "Text", "text", "Value", "value"
        ])
        return text_from_localized(direct) if direct is not None else ""
    return ""


def extract_team_name(team_obj):
    if isinstance(team_obj, str):
        return team_obj
    if isinstance(team_obj, dict):
        for key in [
            "Name", "name", "TeamName", "teamName", "DisplayName", "displayName",
            "ShortName", "shortName", "CountryName", "countryName", "Abbreviation", "abbreviation"
        ]:
            text = text_from_localized(team_obj.get(key))
            if text:
                return text
    return text_from_localized(team_obj)


def to_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        match = re.search(r"\d+", str(value))
        return int(match.group(0)) if match else None


def find_score_near(obj, side):
    """Find score/goals for home/away in nested FIFA structures."""
    if not isinstance(obj, dict):
        return None

    side_words = {
        "home": ["home", "homeTeam", "HomeTeam", "Home"],
        "away": ["away", "awayTeam", "AwayTeam", "Away"],
    }[side]

    # 1) Direct fields on root.
    direct_keys = []
    for side_word in side_words:
        direct_keys.extend([
            f"{side_word}Score", f"{side_word}TeamScore", f"{side_word}Goals",
            f"{side_word}TeamGoals", f"{side_word}Result", f"{side_word}FTScore"
        ])

    # Add common casing variants.
    expanded = set(direct_keys)
    for key in list(direct_keys):
        expanded.add(key[:1].upper() + key[1:])
        expanded.add(key[:1].lower() + key[1:])

    for key in expanded:
        if key in obj:
            val = to_int(obj[key])
            if val is not None:
                return val

    # 2) Nested HomeTeam/AwayTeam object.
    team_obj = first_value(obj, side_words)
    if isinstance(team_obj, dict):
        nested = first_value(team_obj, [
            "Score", "score", "Goals", "goals", "TeamScore", "teamScore",
            "TotalScore", "totalScore", "Result", "result"
        ])
        val = to_int(nested)
        if val is not None:
            return val

    # 3) Result/Score containers.
    for container_key in ["Result", "result", "Score", "score", "MatchResult", "matchResult"]:
        container = obj.get(container_key)
        if isinstance(container, dict):
            val = find_score_near(container, side)
            if val is not None:
                return val

    # 4) Generic path search: path should include home/away and score/goal.
    for path, value in all_scalar_values(obj):
        p = path.lower()
        if side in p and any(word in p for word in ["score", "goal", "goals"]):
            val = to_int(value)
            if val is not None:
                return val

    return None


def normalize_status(raw_status, match_obj=None):
    raw_text = text_from_localized(raw_status) if isinstance(raw_status, (dict, list)) else str(raw_status or "")
    status_text = normalize_text(raw_text)

    if status_text in {
        "ft", "full time", "fulltime", "finished", "final", "played", "completed",
        "result", "post match", "postmatch", "ended", "match finished"
    }:
        return "Final"

    if status_text in {
        "live", "in progress", "first half", "second half", "half time", "halftime", "ht"
    }:
        return "En vivo"

    # Numeric status fallback. FIFA often uses numeric status codes in some feeds.
    # These mappings are intentionally conservative.
    if status_text in {"3", "12"}:
        return "Final"
    if status_text in {"1", "2", "4", "5", "6", "7", "8", "9", "10", "11"}:
        return "En vivo"

    if isinstance(match_obj, dict):
        # Search all scalar status-ish fields for FT/full-time/final.
        for path, value in all_scalar_values(match_obj):
            p = path.lower()
            if any(word in p for word in ["status", "period", "phase"]):
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
    if not isinstance(match, dict):
        return None

    match_id = first_value(match, ["IdMatch", "idMatch", "MatchId", "matchId", "Id", "id"])
    date_raw = first_value(match, ["Date", "date", "MatchDate", "matchDate", "MatchDateTime", "matchDateTime", "LocalDate", "localDate", "DateLocal", "dateLocal"])
    date = str(date_raw or "")[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", str(date_raw or "")) else ""

    home_team_obj = first_value(match, ["HomeTeam", "homeTeam", "Home", "home"])
    away_team_obj = first_value(match, ["AwayTeam", "awayTeam", "Away", "away"])

    home_team = extract_team_name(home_team_obj)
    away_team = extract_team_name(away_team_obj)

    if not home_team or not away_team:
        return None

    home_score = find_score_near(match, "home")
    away_score = find_score_near(match, "away")

    status_raw = first_value(match, [
        "MatchStatus", "matchStatus", "Status", "status", "MatchStatusName", "matchStatusName",
        "Period", "period", "MatchPeriod", "matchPeriod", "Phase", "phase"
    ])
    status = normalize_status(status_raw, match)

    # If a feed has a score and the visual status is absent, do not force Final.
    # But if status is final and score is present, apply it.
    return {
        "source": "FIFA",
        "event_id": str(match_id or ""),
        "date": date,
        "teams": [team_key(home_team), team_key(away_team)],
        "scores": [home_score, away_score],
        "score_available": home_score is not None and away_score is not None,
        "status": status,
        "raw_teams": [home_team, away_team],
    }


def extract_espn_update(event):
    comp = (event.get("competitions") or [{}])[0]
    competitors = comp.get("competitors") or []
    if len(competitors) != 2:
        return None

    teams, scores = [], []
    for competitor in competitors:
        team = competitor.get("team") or {}
        name = team.get("displayName") or team.get("shortDisplayName") or team.get("name") or ""
        teams.append(team_key(name))
        scores.append(str(competitor.get("score", "")).strip())

    status_type = (comp.get("status") or {}).get("type") or {}
    status_name = str(status_type.get("name") or status_type.get("state") or "").upper()
    completed = bool(status_type.get("completed"))

    if completed or status_name in {"STATUS_FINAL", "STATUS_FULL_TIME", "FINAL", "FULL_TIME", "POST"}:
        status = "Final"
    elif status_name in {"STATUS_IN_PROGRESS", "STATUS_HALFTIME", "STATUS_FIRST_HALF", "STATUS_SECOND_HALF", "IN", "LIVE"}:
        status = "En vivo"
    else:
        status = "Programado"

    raw_date = str(event.get("date") or "")
    date = raw_date[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", raw_date) else ""

    return {
        "source": "ESPN",
        "event_id": str(event.get("id") or ""),
        "date": date,
        "teams": teams,
        "scores": [to_int(scores[0]), to_int(scores[1])],
        "score_available": all(score.isdigit() for score in scores),
        "status": status,
        "raw_teams": teams,
    }


def game_indexes(games):
    by_id, by_date_pair, by_pair = {}, {}, {}
    for game in games:
        if game.get("id"):
            by_id[str(game.get("id"))] = game
        by_date_pair[date_pair_key(game.get("date"), game.get("team1"), game.get("team2"))] = game
        by_pair[pair_key(game.get("team1"), game.get("team2"))] = game
    return by_id, by_date_pair, by_pair


def find_matching_game(update, by_id, by_date_pair, by_pair):
    if update["event_id"] and update["event_id"] in by_id:
        return by_id[update["event_id"]]
    dated = by_date_pair.get((update["date"],) + tuple(sorted(update["teams"])))
    return dated or by_pair.get(tuple(sorted(update["teams"])))


def score_in_dashboard_order(game, update):
    if not update["score_available"]:
        return None
    if team_key(game.get("team1")) == update["teams"][0]:
        return f"{update['scores'][0]} - {update['scores'][1]}"
    return f"{update['scores'][1]} - {update['scores'][0]}"


def should_apply_update(game, new_score, new_status):
    old_score = game.get("score", "")
    old_status = game.get("status", "")

    if old_status == "Final" and new_status != "Final":
        return False
    if old_status == "Final" and old_score and new_score is None:
        return False
    if new_status == "Programado":
        return False

    return (new_score is not None and old_score != new_score) or (new_status and old_status != new_status)


def apply_update(game, update):
    new_score = score_in_dashboard_order(game, update)
    new_status = update["status"]

    if not should_apply_update(game, new_score, new_status):
        return False

    if new_score is not None:
        game["score"] = new_score
    if new_status:
        game["status"] = new_status

    source_note = f"{update['source']} automatic update"
    existing_notes = game.get("notes", "")
    if source_note not in existing_notes:
        game["notes"] = f"{existing_notes} · {source_note}" if existing_notes else source_note

    print(f"Applied {update['source']} update: {game.get('team1')} {game.get('score')} {game.get('team2')} [{game.get('status')}]")
    return True


def collect_fifa_updates():
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
    if not DATA_FILE.exists():
        print("worldcup_results.json not found")
        return 1

    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    games = payload["games"] if isinstance(payload, dict) else payload
    dates = [game.get("date") for game in games if game.get("date")]

    by_id, by_date_pair, by_pair = game_indexes(games)

    updates = collect_fifa_updates() + collect_espn_updates(dates)

    matched = 0
    changed = 0

    for update in updates:
        game = find_matching_game(update, by_id, by_date_pair, by_pair)
        if not game:
            continue

        matched += 1

        if apply_update(game, update):
            changed += 1

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
