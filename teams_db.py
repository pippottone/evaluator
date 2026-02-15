"""
Local teams database — maps team names / aliases to API-Football team IDs.
Loaded from the user's league JSON files + common aliases for bookmaker variations.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
#  Embedded team data (from api_ids league files)
# ═══════════════════════════════════════════════════════════════════════════════

_EMBEDDED_TEAMS: list[dict] = [
    # ── Serie A ──────────────────────────────────────────
    {"id": 489, "name": "AC Milan", "code": "MIL", "country": "Italy"},
    {"id": 497, "name": "AS Roma", "code": "ROM", "country": "Italy"},
    {"id": 499, "name": "Atalanta", "code": "ATA", "country": "Italy"},
    {"id": 500, "name": "Bologna", "code": "BOL", "country": "Italy"},
    {"id": 490, "name": "Cagliari", "code": "CAG", "country": "Italy"},
    {"id": 895, "name": "Como", "code": "COM", "country": "Italy"},
    {"id": 520, "name": "Cremonese", "code": "CRE", "country": "Italy"},
    {"id": 502, "name": "Fiorentina", "code": "FIO", "country": "Italy"},
    {"id": 495, "name": "Genoa", "code": "GEN", "country": "Italy"},
    {"id": 505, "name": "Inter", "code": "INT", "country": "Italy"},
    {"id": 496, "name": "Juventus", "code": "JUV", "country": "Italy"},
    {"id": 487, "name": "Lazio", "code": "LAZ", "country": "Italy"},
    {"id": 867, "name": "Lecce", "code": "LEC", "country": "Italy"},
    {"id": 492, "name": "Napoli", "code": "NAP", "country": "Italy"},
    {"id": 523, "name": "Parma", "code": "PAR", "country": "Italy"},
    {"id": 801, "name": "Pisa", "code": "PIS", "country": "Italy"},
    {"id": 488, "name": "Sassuolo", "code": "SAS", "country": "Italy"},
    {"id": 503, "name": "Torino", "code": "TOR", "country": "Italy"},
    {"id": 494, "name": "Udinese", "code": "UDI", "country": "Italy"},
    {"id": 504, "name": "Verona", "code": "VER", "country": "Italy"},
    # Historical / relegated Serie A teams
    {"id": 511, "name": "Empoli", "code": "EMP", "country": "Italy"},
    {"id": 498, "name": "Sampdoria", "code": "SAM", "country": "Italy"},
    {"id": 501, "name": "Spezia", "code": "SPE", "country": "Italy"},
    {"id": 514, "name": "SPAL", "code": "SPA", "country": "Italy"},
    {"id": 515, "name": "Benevento", "code": "BEN", "country": "Italy"},
    {"id": 867, "name": "Lecce", "code": "LEC", "country": "Italy"},
    {"id": 519, "name": "Frosinone", "code": "FRO", "country": "Italy"},
    {"id": 512, "name": "Salernitana", "code": "SAL", "country": "Italy"},
    {"id": 522, "name": "Monza", "code": "MON", "country": "Italy"},

    # ── Premier League ───────────────────────────────────
    {"id": 42, "name": "Arsenal", "code": "ARS", "country": "England"},
    {"id": 66, "name": "Aston Villa", "code": "AST", "country": "England"},
    {"id": 35, "name": "Bournemouth", "code": "BOU", "country": "England"},
    {"id": 55, "name": "Brentford", "code": "BRE", "country": "England"},
    {"id": 51, "name": "Brighton", "code": "BRI", "country": "England"},
    {"id": 44, "name": "Burnley", "code": "BUR", "country": "England"},
    {"id": 49, "name": "Chelsea", "code": "CHE", "country": "England"},
    {"id": 52, "name": "Crystal Palace", "code": "CRY", "country": "England"},
    {"id": 45, "name": "Everton", "code": "EVE", "country": "England"},
    {"id": 36, "name": "Fulham", "code": "FUL", "country": "England"},
    {"id": 63, "name": "Leeds", "code": "LEE", "country": "England"},
    {"id": 40, "name": "Liverpool", "code": "LIV", "country": "England"},
    {"id": 50, "name": "Manchester City", "code": "MCI", "country": "England"},
    {"id": 33, "name": "Manchester United", "code": "MUN", "country": "England"},
    {"id": 34, "name": "Newcastle", "code": "NEW", "country": "England"},
    {"id": 65, "name": "Nottingham Forest", "code": "NOT", "country": "England"},
    {"id": 746, "name": "Sunderland", "code": "SUN", "country": "England"},
    {"id": 47, "name": "Tottenham", "code": "TOT", "country": "England"},
    {"id": 48, "name": "West Ham", "code": "WES", "country": "England"},
    {"id": 39, "name": "Wolves", "code": "WOL", "country": "England"},
    # Historical / relegated PL teams
    {"id": 46, "name": "Leicester", "code": "LEI", "country": "England"},
    {"id": 41, "name": "Southampton", "code": "SOU", "country": "England"},
    {"id": 38, "name": "Watford", "code": "WAT", "country": "England"},
    {"id": 37, "name": "Norwich", "code": "NOR", "country": "England"},
    {"id": 62, "name": "Sheffield Utd", "code": "SHU", "country": "England"},
    {"id": 43, "name": "Cardiff", "code": "CAR", "country": "England"},
    {"id": 60, "name": "Luton", "code": "LUT", "country": "England"},
    {"id": 57, "name": "Ipswich", "code": "IPS", "country": "England"},

    # ── La Liga ──────────────────────────────────────────
    {"id": 542, "name": "Alaves", "code": "ALA", "country": "Spain"},
    {"id": 531, "name": "Athletic Club", "code": "BIL", "country": "Spain"},
    {"id": 530, "name": "Atletico Madrid", "code": "MAD", "country": "Spain"},
    {"id": 529, "name": "Barcelona", "code": "BAR", "country": "Spain"},
    {"id": 538, "name": "Celta Vigo", "code": "CEL", "country": "Spain"},
    {"id": 797, "name": "Elche", "code": "ELC", "country": "Spain"},
    {"id": 540, "name": "Espanyol", "code": "ESP", "country": "Spain"},
    {"id": 546, "name": "Getafe", "code": "GET", "country": "Spain"},
    {"id": 547, "name": "Girona", "code": "GIR", "country": "Spain"},
    {"id": 539, "name": "Levante", "code": "LEV", "country": "Spain"},
    {"id": 798, "name": "Mallorca", "code": "MAL", "country": "Spain"},
    {"id": 727, "name": "Osasuna", "code": "OSA", "country": "Spain"},
    {"id": 718, "name": "Oviedo", "code": "OVI", "country": "Spain"},
    {"id": 728, "name": "Rayo Vallecano", "code": "RAY", "country": "Spain"},
    {"id": 543, "name": "Real Betis", "code": "BET", "country": "Spain"},
    {"id": 541, "name": "Real Madrid", "code": "REA", "country": "Spain"},
    {"id": 548, "name": "Real Sociedad", "code": "RSO", "country": "Spain"},
    {"id": 536, "name": "Sevilla", "code": "SEV", "country": "Spain"},
    {"id": 532, "name": "Valencia", "code": "VAL", "country": "Spain"},
    {"id": 533, "name": "Villarreal", "code": "VIL", "country": "Spain"},
    # Historical La Liga
    {"id": 534, "name": "Las Palmas", "code": "LPA", "country": "Spain"},
    {"id": 537, "name": "Leganes", "code": "LEG", "country": "Spain"},
    {"id": 535, "name": "Real Valladolid", "code": "VAD", "country": "Spain"},
    {"id": 545, "name": "Cadiz", "code": "CAD", "country": "Spain"},
    {"id": 544, "name": "Granada CF", "code": "GRA", "country": "Spain"},

    # ── Ligue 1 ──────────────────────────────────────────
    {"id": 77, "name": "Angers", "code": "ANG", "country": "France"},
    {"id": 108, "name": "Auxerre", "code": "AUX", "country": "France"},
    {"id": 111, "name": "Le Havre", "code": "HAV", "country": "France"},
    {"id": 116, "name": "Lens", "code": "LEN", "country": "France"},
    {"id": 79, "name": "Lille", "code": "LIL", "country": "France"},
    {"id": 97, "name": "Lorient", "code": "LOR", "country": "France"},
    {"id": 80, "name": "Lyon", "code": "LYO", "country": "France"},
    {"id": 81, "name": "Marseille", "code": "MAR", "country": "France"},
    {"id": 112, "name": "Metz", "code": "MET", "country": "France"},
    {"id": 91, "name": "Monaco", "code": "MON", "country": "France"},
    {"id": 83, "name": "Nantes", "code": "NAN", "country": "France"},
    {"id": 84, "name": "Nice", "code": "NIC", "country": "France"},
    {"id": 114, "name": "Paris FC", "code": "PAR", "country": "France"},
    {"id": 85, "name": "Paris Saint Germain", "code": "PSG", "country": "France"},
    {"id": 94, "name": "Rennes", "code": "REN", "country": "France"},
    {"id": 106, "name": "Stade Brestois 29", "code": "BRE", "country": "France"},
    {"id": 95, "name": "Strasbourg", "code": "STR", "country": "France"},
    {"id": 96, "name": "Toulouse", "code": "TOU", "country": "France"},
    # Historical Ligue 1
    {"id": 93, "name": "Reims", "code": "REI", "country": "France"},
    {"id": 82, "name": "Montpellier", "code": "MTP", "country": "France"},
    {"id": 78, "name": "Bordeaux", "code": "BOR", "country": "France"},
    {"id": 99, "name": "Clermont Foot", "code": "CLE", "country": "France"},
    {"id": 110, "name": "Saint-Etienne", "code": "STE", "country": "France"},

    # ── Bundesliga ───────────────────────────────────────
    {"id": 180, "name": "1. FC Heidenheim", "code": "HEI", "country": "Germany"},
    {"id": 192, "name": "1. FC Köln", "code": "KOL", "country": "Germany"},
    {"id": 167, "name": "1899 Hoffenheim", "code": "HOF", "country": "Germany"},
    {"id": 168, "name": "Bayer Leverkusen", "code": "BAY", "country": "Germany"},
    {"id": 157, "name": "Bayern München", "code": "BMU", "country": "Germany"},
    {"id": 165, "name": "Borussia Dortmund", "code": "DOR", "country": "Germany"},
    {"id": 163, "name": "Borussia Mönchengladbach", "code": "MOE", "country": "Germany"},
    {"id": 169, "name": "Eintracht Frankfurt", "code": "EIN", "country": "Germany"},
    {"id": 170, "name": "FC Augsburg", "code": "AUG", "country": "Germany"},
    {"id": 186, "name": "FC St. Pauli", "code": "PAU", "country": "Germany"},
    {"id": 164, "name": "FSV Mainz 05", "code": "MAI", "country": "Germany"},
    {"id": 175, "name": "Hamburger SV", "code": "HAM", "country": "Germany"},
    {"id": 173, "name": "RB Leipzig", "code": "LEI", "country": "Germany"},
    {"id": 160, "name": "SC Freiburg", "code": "FRE", "country": "Germany"},
    {"id": 182, "name": "Union Berlin", "code": "UNI", "country": "Germany"},
    {"id": 172, "name": "VfB Stuttgart", "code": "STU", "country": "Germany"},
    {"id": 161, "name": "VfL Wolfsburg", "code": "WOL", "country": "Germany"},
    {"id": 162, "name": "Werder Bremen", "code": "WER", "country": "Germany"},
    # Historical Bundesliga
    {"id": 159, "name": "Hertha Berlin", "code": "HER", "country": "Germany"},
    {"id": 176, "name": "VfL Bochum", "code": "BOC", "country": "Germany"},
    {"id": 179, "name": "Arminia Bielefeld", "code": "BIE", "country": "Germany"},
    {"id": 174, "name": "Greuther Fürth", "code": "FUR", "country": "Germany"},
    {"id": 178, "name": "Darmstadt 98", "code": "DAR", "country": "Germany"},
    {"id": 181, "name": "SV Holstein Kiel", "code": "KIE", "country": "Germany"},
]


# ═══════════════════════════════════════════════════════════════════════════════
#  Bookmaker alias map — common variations → canonical name (case-insensitive)
# ═══════════════════════════════════════════════════════════════════════════════

_BOOKMAKER_ALIASES: dict[str, str] = {
    # Italy
    "fc empoli": "empoli",
    "empoli fc": "empoli",
    "spezia calcio": "spezia",
    "us salernitana": "salernitana",
    "us salernitana 1919": "salernitana",
    "hellas verona": "verona",
    "inter milan": "inter",
    "internazionale": "inter",
    "inter milano": "inter",
    "ac monza": "monza",
    "us cremonese": "cremonese",
    "ssc napoli": "napoli",
    "ss lazio": "lazio",
    "ac fiorentina": "fiorentina",
    "us lecce": "lecce",
    "udinese calcio": "udinese",
    "genoa cfc": "genoa",
    "uc sampdoria": "sampdoria",
    "torino fc": "torino",
    "bologna fc": "bologna",
    "cagliari calcio": "cagliari",
    "como 1907": "como",
    "parma calcio": "parma",
    "acf fiorentina": "fiorentina",
    "as roma": "as roma",  # keep full name since it's canonical
    "roma": "as roma",
    "ac milan": "ac milan",
    "milan": "ac milan",

    # England
    "man city": "manchester city",
    "man utd": "manchester united",
    "man united": "manchester united",
    "newcastle utd": "newcastle",
    "newcastle united": "newcastle",
    "spurs": "tottenham",
    "tottenham hotspur": "tottenham",
    "brighton hove albion": "brighton",
    "brighton & hove albion": "brighton",
    "west ham united": "west ham",
    "wolverhampton": "wolves",
    "wolverhampton wanderers": "wolves",
    "nottingham": "nottingham forest",
    "notts forest": "nottingham forest",
    "nott'm forest": "nottingham forest",
    "afc bournemouth": "bournemouth",
    "crystal palace fc": "crystal palace",
    "leeds united": "leeds",
    "leicester city": "leicester",
    "southampton fc": "southampton",
    "ipswich town": "ipswich",
    "luton town": "luton",
    "sheffield united": "sheffield utd",
    "sheffield utd": "sheffield utd",
    "burnley fc": "burnley",

    # Spain
    "at. madrid": "atletico madrid",
    "atl. madrid": "atletico madrid",
    "atletico de madrid": "atletico madrid",
    "atlético madrid": "atletico madrid",
    "fc barcelona": "barcelona",
    "barça": "barcelona",
    "barca": "barcelona",
    "athletic bilbao": "athletic club",
    "athletico bilbao": "athletic club",
    "real sociedad san sebastian": "real sociedad",
    "ud las palmas": "las palmas",
    "cd leganes": "leganes",
    "cd leganés": "leganes",
    "rcd espanyol": "espanyol",
    "rcd mallorca": "mallorca",
    "rc celta": "celta vigo",
    "celta": "celta vigo",
    "real betis balompie": "real betis",
    "sevilla fc": "sevilla",
    "valencia cf": "valencia",

    # France
    "psg": "paris saint germain",
    "paris sg": "paris saint germain",
    "paris saint-germain": "paris saint germain",
    "olympique lyonnais": "lyon",
    "ol": "lyon",
    "olympique marseille": "marseille",
    "olympique de marseille": "marseille",
    "om": "marseille",
    "losc lille": "lille",
    "losc": "lille",
    "as monaco": "monaco",
    "rc lens": "lens",
    "stade rennais": "rennes",
    "stade brestois": "stade brestois 29",
    "brest": "stade brestois 29",
    "ogc nice": "nice",
    "fc nantes": "nantes",
    "rc strasbourg": "strasbourg",
    "as saint-etienne": "saint-etienne",
    "asse": "saint-etienne",
    "clermont": "clermont foot",

    # Germany
    "bayern munich": "bayern münchen",
    "bayern munchen": "bayern münchen",
    "bayern": "bayern münchen",
    "fc bayern": "bayern münchen",
    "dortmund": "borussia dortmund",
    "bvb": "borussia dortmund",
    "gladbach": "borussia mönchengladbach",
    "monchengladbach": "borussia mönchengladbach",
    "mgladbach": "borussia mönchengladbach",
    "leverkusen": "bayer leverkusen",
    "frankfurt": "eintracht frankfurt",
    "e. frankfurt": "eintracht frankfurt",
    "hoffenheim": "1899 hoffenheim",
    "tsg hoffenheim": "1899 hoffenheim",
    "rb leipzig": "rb leipzig",
    "rasenballsport leipzig": "rb leipzig",
    "leipzig": "rb leipzig",
    "freiburg": "sc freiburg",
    "wolfsburg": "vfl wolfsburg",
    "stuttgar": "vfb stuttgart",
    "stuttgart": "vfb stuttgart",
    "koln": "1. fc köln",
    "köln": "1. fc köln",
    "cologne": "1. fc köln",
    "mainz": "fsv mainz 05",
    "mainz 05": "fsv mainz 05",
    "heidenheim": "1. fc heidenheim",
    "bremen": "werder bremen",
    "augsburg": "fc augsburg",
    "st. pauli": "fc st. pauli",
    "st pauli": "fc st. pauli",
    "hamburg": "hamburger sv",
    "hsv": "hamburger sv",
    "bochum": "vfl bochum",
    "hertha": "hertha berlin",
    "hertha bsc": "hertha berlin",
    "holstein kiel": "sv holstein kiel",
    "kiel": "sv holstein kiel",
    "darmstadt": "darmstadt 98",

    # Italy extras for "Udinese - - Atalanta" style
    "udinese -": "udinese",
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Build lookup index
# ═══════════════════════════════════════════════════════════════════════════════

def _normalise(s: str) -> str:
    """Lowercase, strip common prefixes/suffixes, remove dots/punctuation."""
    s = s.strip().lower()
    s = s.replace(".", "").replace("'", "").replace("'", "")
    return s


def _build_index() -> tuple[dict[str, int], dict[str, int]]:
    """Build name→id and code→id lookup dicts."""
    name_to_id: dict[str, int] = {}
    code_to_id: dict[str, int] = {}

    for team in _EMBEDDED_TEAMS:
        tid = team["id"]
        name = _normalise(team["name"])
        code = team.get("code", "").strip().upper()

        name_to_id[name] = tid
        if code and code not in code_to_id:
            code_to_id[code] = tid

    # Add bookmaker aliases
    for alias, canonical in _BOOKMAKER_ALIASES.items():
        canon_norm = _normalise(canonical)
        if canon_norm in name_to_id:
            name_to_id[_normalise(alias)] = name_to_id[canon_norm]

    return name_to_id, code_to_id


_NAME_TO_ID, _CODE_TO_ID = _build_index()

# Reverse map for display
_ID_TO_NAME: dict[int, str] = {}
for _t in _EMBEDDED_TEAMS:
    _ID_TO_NAME.setdefault(_t["id"], _t["name"])


# ═══════════════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════════════

def lookup_team_id(name: str) -> Optional[int]:
    """
    Try to resolve a team name to an API-Football team ID.
    Tries exact match, alias match, then partial/fuzzy match.
    Returns None if no match found.
    """
    norm = _normalise(name)

    # 1. Exact match
    if norm in _NAME_TO_ID:
        return _NAME_TO_ID[norm]

    # 2. Try stripping common prefixes/suffixes
    stripped = _strip_decorators(norm)
    if stripped in _NAME_TO_ID:
        return _NAME_TO_ID[stripped]

    # 3. Try code match (3-letter)
    upper = name.strip().upper()
    if len(upper) <= 4 and upper in _CODE_TO_ID:
        return _CODE_TO_ID[upper]

    # 4. Partial match — check if input contains a known team name or vice versa
    for known_name, tid in _NAME_TO_ID.items():
        if len(known_name) >= 4:  # avoid matching very short strings
            if known_name in norm or norm in known_name:
                return tid

    return None


def get_team_name(team_id: int) -> Optional[str]:
    """Get canonical team name by ID."""
    return _ID_TO_NAME.get(team_id)


def _strip_decorators(name: str) -> str:
    """Remove common prefixes/suffixes that bookmakers add."""
    # Strip common prefixes
    prefixes = ["fc ", "ac ", "as ", "afc ", "ssc ", "ss ", "us ", "uc ",
                "rcd ", "cd ", "rc ", "ud ", "cf ", "sc ", "vfl ", "vfb ",
                "fsv ", "sv ", "tsv ", "tsg ", "1 "]
    # Strip common suffixes
    suffixes = [" fc", " cf", " calcio", " 1907", " 1919", " 1904",
                " united", " city"]

    s = name
    for p in prefixes:
        if s.startswith(p):
            s = s[len(p):]
            break
    for sf in suffixes:
        if s.endswith(sf):
            s = s[:-len(sf)]
            break
    return s.strip()


def load_external_teams(directory: str) -> int:
    """Load additional team JSON files from a directory. Returns count of teams added."""
    path = Path(directory)
    if not path.is_dir():
        return 0

    count = 0
    for f in path.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for team in data:
                    tid = team.get("id")
                    tname = team.get("name", "")
                    if tid and tname:
                        norm = _normalise(tname)
                        if norm not in _NAME_TO_ID:
                            _NAME_TO_ID[norm] = tid
                            _ID_TO_NAME.setdefault(tid, tname)
                            count += 1
        except Exception:
            continue
    return count
