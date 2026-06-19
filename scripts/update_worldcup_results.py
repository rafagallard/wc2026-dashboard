#!/usr/bin/env python3
"""Update worldcup_results.json from ESPN's public scoreboard endpoint.
This script is intended for GitHub Actions. It keeps the dashboard file stable and only updates the JSON data.
"""
import json, os, re, sys, urllib.request, datetime
from pathlib import Path

DATA_FILE = Path('worldcup_results.json')
ESPN_URL = os.getenv('ESPN_SCOREBOARD_URL', 'https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?limit=200&dates=20260611-20260719')
ALIASES = {
    'mexico':'México','south africa':'Sudáfrica','korea republic':'Corea del Sur','south korea':'Corea del Sur','czechia':'Chequia','czech republic':'Chequia',
    'canada':'Canadá','bosnia and herz.':'Bosnia y Herzegovina','bosnia and herzegovina':'Bosnia y Herzegovina','qatar':'Qatar','switzerland':'Suiza',
    'united states':'Estados Unidos','usa':'Estados Unidos','paraguay':'Paraguay','australia':'Australia','turkey':'Turquía','türkiye':'Turquía',
    'brazil':'Brasil','morocco':'Marruecos','haiti':'Haití','scotland':'Escocia','germany':'Alemania','curacao':'Curazao','curaçao':'Curazao',
    'ivory coast':'Costa de Marfil','cote d ivoire':'Costa de Marfil','côte d’ivoire':'Costa de Marfil','ecuador':'Ecuador','netherlands':'Países Bajos',
    'japan':'Japón','sweden':'Suecia','tunisia':'Túnez','belgium':'Bélgica','egypt':'Egipto','iran':'Irán','new zealand':'Nueva Zelanda',
    'spain':'España','cape verde':'Cabo Verde','saudi arabia':'Arabia Saudita','uruguay':'Uruguay','france':'Francia','senegal':'Senegal','iraq':'Irak',
    'norway':'Noruega','argentina':'Argentina','algeria':'Argelia','austria':'Austria','jordan':'Jordania','portugal':'Portugal','dr congo':'RD Congo',
    'congo dr':'RD Congo','uzbekistan':'Uzbekistán','colombia':'Colombia','england':'Inglaterra','croatia':'Croacia','ghana':'Ghana','panama':'Panamá'
}

def key(s):
    s = re.sub(r'[^a-z0-9 ]+', '', (s or '').lower()).strip()
    return ALIASES.get(s, s)

def load_json_url(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))

def main():
    payload = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    games = payload['games'] if isinstance(payload, dict) else payload
    by_pair = {}
    for g in games:
        by_pair[tuple(sorted([key(g['team1']), key(g['team2'])]))] = g
    try:
        feed = load_json_url(ESPN_URL)
    except Exception as exc:
        print(f'Unable to load ESPN feed: {exc}')
        return 0
    changed = 0
    for ev in feed.get('events', []):
        comp = (ev.get('competitions') or [{}])[0]
        competitors = comp.get('competitors') or []
        if len(competitors) != 2:
            continue
        teams = []
        scores = []
        for c in competitors:
            teams.append(key(((c.get('team') or {}).get('displayName') or (c.get('team') or {}).get('shortDisplayName') or '')))
            scores.append(c.get('score'))
        g = by_pair.get(tuple(sorted(teams)))
        if not g:
            continue
        status = ((comp.get('status') or {}).get('type') or {})
        completed = bool(status.get('completed')) or status.get('name') in ('STATUS_FINAL','STATUS_FULL_TIME')
        if completed and all(str(x).isdigit() for x in scores):
            # preserve original home/away order from dashboard
            if key(g['team1']) == teams[0]:
                new_score = f"{scores[0]} - {scores[1]}"
            else:
                new_score = f"{scores[1]} - {scores[0]}"
            if g.get('score') != new_score or g.get('status') != 'Final':
                g['score'] = new_score
                g['status'] = 'Final'
                changed += 1
    if changed:
        now = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec='seconds')
        out = {
            'updatedAt': now,
            'timezone': payload.get('timezone','America/Mexico_City') if isinstance(payload,dict) else 'America/Mexico_City',
            'refreshHours': 1,
            'sourceLabel': 'ESPN public scoreboard',
            'games': games
        }
        DATA_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Updated {changed} matches')
    else:
        print('No match updates found')
    return 0
if __name__ == '__main__':
    sys.exit(main())
