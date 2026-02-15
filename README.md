# Betslip Historical Validator (API-SPORTS)

This tool validates a parsed betslip against historical match data and returns:
- `won`
- `lost`
- `pending`
- `push`
- `refund`
- `void`
- `cancelled`

It is designed for the workflow you described:
1. screenshot -> OCR text
2. selection names matched to your DB
3. this tool checks real match outcomes via API and settles the betslip

## Supported markets
- `MATCH_WINNER` (`HOME`, `DRAW`, `AWAY`)
- `DOUBLE_CHANCE` (`1X`, `X2`, `12`)
- `OVER_UNDER` (pick `OVER` / `UNDER` + `line`, e.g. 2.5)
- `BTTS` (Both Teams To Score: `YES` / `NO`)
- `DRAW_NO_BET` (`HOME`, `AWAY`) -> returns `push` if match ends draw
- `TEAM_OVER_UNDER` (`OVER` / `UNDER` + `line` + `team=HOME|AWAY`)
- `CORRECT_SCORE` (pick like `2:1`)
- `HT_MATCH_WINNER` (1st-half winner: `HOME`, `DRAW`, `AWAY`)
- `SECOND_HALF_MATCH_WINNER` (2nd-half only winner: `HOME`, `DRAW`, `AWAY`)
- `HT_OVER_UNDER` (1st-half total goals)
- `SECOND_HALF_OVER_UNDER` (2nd-half only total goals)
- `HT_FT` (combo in format `HOME/AWAY` or `1/X`)
- `CORNERS_OVER_UNDER` (total corners over/under line)
- `TEAM_CORNERS_OVER_UNDER` (home/away corners over/under line)
- `CARDS_OVER_UNDER` (total cards = yellow+red over/under line)
- `TEAM_CARDS_OVER_UNDER` (home/away cards = yellow+red over/under line)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Set environment variable:

```powershell
$env:API_SPORTS_KEY="your_api_key"
```

## Input JSON example

```json
{
  "sport": "football",
  "base_url": "https://v3.football.api-sports.io",
  "selections": [
    {"fixture_id": 1208821, "market": "MATCH_WINNER", "pick": "HOME"},
    {"fixture_id": 1208822, "market": "OVER_UNDER", "pick": "OVER", "line": 2.5},
    {"fixture_id": 1208823, "market": "BTTS", "pick": "YES"}
  ]
}
```

Save as `slip.json`.

## Run

```bash
python main.py --input slip.json
```

## Run as HTTP service (recommended for external app integration)

```bash
uvicorn service:app --host 0.0.0.0 --port 8000
```

Open docs:
- `http://127.0.0.1:8000/docs`

### Request example

`POST /validate-betslip`

```json
{
  "base_url": "https://v3.football.api-sports.io",
  "selections": [
    {"fixture_id": 1208821, "market": "MATCH_WINNER", "pick": "HOME"},
    {"fixture_id": 1208822, "market": "OVER_UNDER", "pick": "OVER", "line": 2.5},
    {"fixture_id": 1208823, "market": "BTTS", "pick": "YES"}
  ]
}
```

You can also pass `api_key` in the JSON body, otherwise `API_SPORTS_KEY` env var is used.

### Table adapter request (best for your OCR+DB table flow)

`POST /validate-betslip/table`

This endpoint accepts table-like rows from your app and normalizes aliases automatically.

```json
{
  "base_url": "https://v3.football.api-sports.io",
  "rows": [
    {"fixture_id": 1208821, "market": "1X2", "pick": "1"},
    {"fixture_id": 1208822, "market": "OU", "pick": "OVER", "line": 2.5},
    {"fixture_id": 1208823, "market": "GGNG", "pick": "GG"}
  ]
}
```

Supported aliases:
- market: `MATCH_WINNER`, `1X2`, `MONEYLINE`, `DOUBLE_CHANCE`, `DC`, `OVER_UNDER`, `OU`, `BTTS`, `GGNG`
- picks are normalized per market (example: `1` -> `HOME`, `GG` -> `YES`, `O` -> `OVER`)

Additional aliases:
- market: `DNB` -> `DRAW_NO_BET`
- market: `TEAM_TOTAL_GOALS` -> `TEAM_OVER_UNDER`
- market: `CS` -> `CORRECT_SCORE`
- market: `HT_1X2`, `1H_1X2` -> `HT_MATCH_WINNER`
- market: `2H_1X2` -> `SECOND_HALF_MATCH_WINNER`
- market: `HT_OU` -> `HT_OVER_UNDER`
- market: `2H_OU` -> `SECOND_HALF_OVER_UNDER`
- market: `HTFT` -> `HT_FT`
- market: `CORNERS_OU` -> `CORNERS_OVER_UNDER`
- market: `TEAM_CORNERS_OU` -> `TEAM_CORNERS_OVER_UNDER`
- market: `CARDS_OU` -> `CARDS_OVER_UNDER`
- market: `TEAM_CARDS_OU` -> `TEAM_CARDS_OVER_UNDER`

If `base_url` is omitted in this endpoint, set `API_BASE_URL` in environment.

## Run with Docker (separate tool deployment)

```bash
docker build -t betslip-validator .
docker run --rm -p 8000:8000 --env-file .env.example betslip-validator
```

For production, create your own `.env` from `.env.example` and set real keys.

## Run with Docker Compose (recommended for Docker Desktop)

1. Create `.env` from the template and set your real key:

```bash
cp .env.example .env
```

2. Build image and start service:

```bash
docker build -t betslip-validator .
docker compose up -d
```

3. Manage lifecycle:

```bash
docker compose stop
docker compose start
docker compose down
```

The compose service is defined in `docker-compose.yml` with container name `betslip-validator-svc` and restart policy `unless-stopped`.

## Output shape

```json
{
  "status": "pending",
  "checked_at": "2026-02-15T10:30:00+00:00",
  "results": [
    {
      "fixture_id": 1208821,
      "market": "MATCH_WINNER",
      "pick": "HOME",
      "status": "won",
      "reason": "Home team won 2-1"
    }
  ]
}
```

## Notes
- If a fixture is not finalized yet, that selection returns `pending`.
- Slip status logic:
  - any `lost` -> slip `lost`
  - any `pending` or `not_supported` -> slip `pending`
  - all `won` -> slip `won`
  - all non-loss settled as `push/refund/void/cancelled` -> slip `refund`
- If one fixture cannot be fetched (API/network/invalid id), that selection is marked `pending` and the tool continues processing the rest.
- Period rules:
  - HT markets use halftime score.
  - 2H markets use `fulltime - halftime` goals for each team.
  - HT/FT uses halftime result + fulltime result categories.

## Run tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```
