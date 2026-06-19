#!/usr/bin/env python3
"""Fully automated World Cup dashboard results updater.

Sources:
1. FIFA official calendar matches API as primary source.
2. ESPN public scoreboard as fallback source.

No manual overrides.
No scraping of news articles.
No manual_results.json.
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
    "mexico": "México",
    "méxico": "México",
    "south africa": "Sudáfrica",
    "korea republic": "Corea del Sur",
    "south korea": "Corea del Sur",
    "republic of korea": "Corea del Sur",
    "czechia": "Chequia",
    "czech republic": "Chequia",
    "canada": "Canadá",
    "bosnia and herz.": "Bosnia y Herzegovina",
    "bosnia and herzegovina": "Bosnia y Herzegovina",
    "qatar": "Qatar",
    "switzerland": "Suiza",
    "suisse": "Suiza",
    "united states": "Estados Unidos",
    "usa": "Estados Unidos",
    "us": "Estados Unidos",
    "paraguay": "Paraguay",
    "australia": "Australia",
    "turkey": "Turquía",
    "türkiye": "Turquía",
    "brazil": "Brasil",
    "morocco": "Marruecos",
    "haiti": "Haití",
    "scotland": "Escocia",
    "germany": "Alemania",
    "curacao": "Curazao",
    "curaçao": "Curazao",
    "ivory coast": "Costa de Marfil",
    "cote d ivoire": "Costa de Marfil",
    "côte d’ivoire": "Costa de Marfil",
    "côte d'ivoire": "Costa de Marfil",
    "ecuador": "Ecuador",
    "netherlands": "Países Bajos",
    "japan": "Japón",
    "sweden": "Suecia",
    "tunisia": "Túnez",
    "belgium": "Bélgica",
    "egypt": "Egipto",
    "iran": "Irán",
    "new zealand": "Nueva Zelanda",
    "spain": "España",
    "cape verde": "Cabo Verde",
    "saudi arabia": "Arabia Saudita",
    "uruguay": "Uruguay",
    "france": "Francia",
    "senegal": "Senegal",
    "iraq": "Irak",
    "norway": "Noruega",
    "argentina": "Argentina",
    "algeria": "Argelia",
    "austria": "Austria",
    "jordan": "Jordania",
    "portugal": "Portugal",
    "dr congo": "RD Congo",
    "congo dr": "RD Congo",
    "uzbekistan": "Uzbekistán",
    "colombia": "Colombia",
    "england": "Inglaterra",
    "croatia": "Croacia",
    "ghana": "Ghana",
    "panama": "Panamá",
}


def load_json_url(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=35) as response:
        return json.loads(response.read().decode("utf-8"))


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")


def normalize_text(value):
    value = str(value or "").strip().lower()
    value = value.replace("’", "'")
    value = re.sub(r"[^a-z0-9áéíóúüñç' ]+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def ascii_fold(value):
    return (
        value.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
        .replace("ñ", "n")
    )


def team_key(value):
    cleaned = normalize_text(value)
    folded = ascii_fold(cleaned)
    return ALIASES.get(cleaned) or ALIASES.get(folded) or value


def pair_key(team1, team2):
    return tuple(sorted([team_key(team1), team_key(team2)]))


def date_pair_key(date, team1, team2):
    return (str(date or ""),) + pair_key(team1, team2)


def date_to_espn(date_value):
    return str(date_value or "").replace("-", "")[:8]


def first_value(obj, keys):
    if not isinstance(obj, dict):
        return None
    for key in keys:
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
    return None


def text_from_localized(value):
    """Extract readable text from FIFA localized objects/lists."""
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                locale = str(item.get("Locale") or item.get("locale") or item.get("Language") or "").lower()
                if locale in {"en", "en-us", "en-gb"}:
                    text = first_value(item, ["Description", "description", "Name", "name", "Text", "text"])
                    if text:
                        return str(text)
        for item in value:
            text = text_from_localized(item)
            if text:
                return text
        return ""

    if isinstance(value, dict):
        text = first_value(
            value,
            [
                "Description",
                "description",
                "Name",
                "name",
                "DisplayName",
                "displayName",
                "ShortName",
                "shortName",
                "Abbreviation",
                "abbreviation",
                "Text",
                "text",
            ],
        )
        if text:
            return text_from_localized(text)

    return ""


def extract_team_name(team_obj):
    if team_obj is None:
        return ""

    if isinstance(team_obj, str):
        return team_obj

    if isinstance(team_obj, dict):
        for key in [
            "Name",
            "name",
            "TeamName",
            "teamName",
            "DisplayName",
            "displayName",
            "ShortName",
            "shortName",
            "CountryName",
            "countryName",
            "Abbreviation",
            "abbreviation",
        ]:
            if key in team_obj:
                text = text_from_localized(team_obj[key])
                if text:
                    return text

    return text_from_localized(team_obj)


def to_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        match = re.search(r"\d+", str(value))
        return int(match.group(0)) if match else None


def normalize_fifa_status(raw_status, match_obj):
    status_text = normalize_text(raw_status)

    # FIFA visual page uses FT; API may use several names depending on entity.
    if status_text in {
        "ft",
        "full time",
        "fulltime",
        "finished",
        "final",
        "played",
        "completed",
        "result",
        "post match",
        "postmatch",
    }:
        return "Final"

    if status_text in {
        "live",
        "in progress",
        "first half",
        "second half",
        "half time",
        "halftime",
        "ht",
    }:
        return "En vivo"

    # Some FIFA records expose boolean or numeric finished flags.
    finished_flag = first_value(
        match_obj,
        ["Finished", "finished", "IsFinished", "isFinished", "Completed", "completed"],
    )
    if str(finished_flag).lower() in {"true", "1", "yes"}:
        return "Final"

    return "Programado"


def find_matches_list(payload):
    """Find the main match list in FIFA payload."""
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    for key in ["Results", "results", "Matches", "matches", "Items", "items", "Data", "data"]:
        value = payload.get(key)
        if isinstance(value, list):
            return value

    # Fallback: recursively find a list containing match-like objects.
    candidates = []

    def walk(value):
        if isinstance(value, list):
            score = 0
            for item in value[:5]:
                if isinstance(item, dict):
                    keys = set(item.keys())
                    if keys & {"IdMatch", "idMatch", "MatchId", "IdCompetition", "HomeTeam", "AwayTeam"}:
                        score += 1
            if score:
                candidates.append((score, value))
        elif isinstance(value, dict):
            for child in value.values():
                walk(child)

    walk(payload)

    if not candidates:
        return []

    return sorted(candidates, key=lambda x: x[0], reverse=True)[0][1]


def extract_fifa_update(match):
    if not isinstance(match, dict):
        return None

    match_id = first_value(match, ["IdMatch", "idMatch", "MatchId", "matchId", "Id", "id"])
    date_raw = first_value(
        match,
        [
            "Date",
            "date",
            "MatchDate",
            "matchDate",
            "MatchDateTime",
            "matchDateTime",
            "LocalDate",
            "localDate",
            "DateLocal",
            "dateLocal",
        ],
    )
    date = str(date_raw or "")[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", str(date_raw or "")) else ""

    home_team_obj = first_value(match, ["HomeTeam", "homeTeam", "Home", "home"])
    away_team_obj = first_value(match, ["AwayTeam", "awayTeam", "Away", "away"])
    home_team = extract_team_name(home_team_obj)
    away_team = extract_team_name(away_team_obj)

    if not home_team or not away_team:
        return None

    home_score = first_value(
        match,
        [
            "HomeTeamScore",
            "homeTeamScore",
            "HomeScore",
            "homeScore",
            "ScoreHome",
            "scoreHome",
            "HomeTeamGoals",
            "homeTeamGoals",
        ],
    )
    away_score = first_value(
        match,
        [
            "AwayTeamScore",
            "awayTeamScore",
            "AwayScore",
            "awayScore",
            "ScoreAway",
            "scoreAway",
            "AwayTeamGoals",
            "awayTeamGoals",
        ],
    )

    # Some FIFA entities store score inside a nested Result/Score object.
    result_obj = first_value(match, ["Result", "result", "Score", "score"])
    if isinstance(result_obj, dict):
        home_score = home_score if home_score not in (None, "") else first_value(
            result_obj,
            ["HomeTeamScore", "homeTeamScore", "HomeScore", "homeScore", "ScoreHome", "scoreHome"],
        )
        away_score = away_score if away_score not in (None, "") else first_value(
            result_obj,
            ["AwayTeamScore", "awayTeamScore", "AwayScore", "awayScore", "ScoreAway", "scoreAway"],
        )

    home_score = to_int(home_score)
    away_score = to_int(away_score)

    status_raw = first_value(
        match,
        [
            "MatchStatus",
            "matchStatus",
            "Status",
            "status",
            "MatchStatusName",
            "matchStatusName",
            "Period",
            "period",
        ],
    )
    if isinstance(status_raw, dict) or isinstance(status_raw, list):
        status_raw = text_from_localized(status_raw)

    status = normalize_fifa_status(status_raw, match)

    return {
        "source": "FIFA",
        "event_id": str(match_id or ""),
        "date": date,
        "teams": [team_key(home_team), team_key(away_team)],
        "scores": [home_score, away_score],
        "score_available": home_score is not None and away_score is not None,
        "status": status,
    }


def extract_espn_update(event):
    comp = (event.get("competitions") or [{}])[0]
    competitors = comp.get("competitors") or []

    if len(competitors) != 2:
        return None

    teams = []
    scores = []

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
    }


def game_indexes(games):
    by_id = {}
    by_date_pair = {}
    by_pair = {}

    for game in games:
        if game.get("id"):
            by_id[str(game.get("id"))] = game
        by_date_pair[date_pair_key(game.get("date"), game.get("team1"), game.get("team2"))] = game
        by_pair[pair_key(game.get("team1"), game.get("team2"))] = game

    return by_id, by_date_pair, by_pair


def find_matching_game(update, by_id, by_date_pair, by_pair):
    # ID match works for ESPN. FIFA ids may differ from the dashboard ids, so pair matching is also needed.
    if update["event_id"] and update["event_id"] in by_id:
        return by_id[update["event_id"]]

    dated = by_date_pair.get((update["date"],) + tuple(sorted(update["teams"])))
    if dated:
        return dated

    return by_pair.get(tuple(sorted(update["teams"])))


def score_in_dashboard_order(game, update):
    if not update["score_available"]:
        return None

    if team_key(game.get("team1")) == update["teams"][0]:
        return f"{update['scores'][0]} - {update['scores'][1]}"

    return f"{update['scores'][1]} - {update['scores'][0]}"


def should_apply_update(game, new_score, new_status):
    old_score = game.get("score", "")
    old_status = game.get("status", "")

    # Do not downgrade final matches.
    if old_status == "Final" and new_status != "Final":
        return False

    # Do not overwrite final scores with missing score data.
    if old_status == "Final" and old_score and new_score is None:
        return False

    if new_status == "Programado":
        return False

    if new_score is not None and old_score != new_score:
        return True

    if new_status and old_status != new_status:
        return True

    return False


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

    return True


def collect_fifa_updates():
    try:
        payload = load_json_url(FIFA_URL)
    except Exception as exc:
        print(f"Unable to load FIFA feed: {exc}")
        return []

    matches = find_matches_list(payload)
    updates = []

    for match in matches:
        update = extract_fifa_update(match)
        if update:
            updates.append(update)

    print(f"Fetched FIFA matches: {len(updates)} updates")
    return updates


def collect_espn_updates(dates):
    events_by_id = {}

    for date in sorted(set(dates)):
        espn_date = date_to_espn(date)
        if not espn_date:
            continue

        url = ESPN_URL_TEMPLATE.format(date=espn_date)

        try:
            feed = load_json_url(url)
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

    updates = []
    for event in events_by_id.values():
        update = extract_espn_update(event)
        if update:
            updates.append(update)

    return updates


def main():
    if not DATA_FILE.exists():
        print("worldcup_results.json not found")
        return 1

    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    games = payload["games"] if isinstance(payload, dict) else payload
    dates = [game.get("date") for game in games if game.get("date")]

    by_id, by_date_pair, by_pair = game_indexes(games)

    # FIFA first. ESPN second as fallback.
    updates = collect_fifa_updates() + collect_espn_updates(dates)

    changed = 0

    for update in updates:
        game = find_matching_game(update, by_id, by_date_pair, by_pair)
        if not game:
            continue

        if apply_update(game, update):
            changed += 1

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
        print("No match updates found")

    return 0


if __name__ == "__main__":
    sys.exit(main())
