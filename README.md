# Trade Opportunities API

A FastAPI service for sector-based India trade analysis. It collects recent market/news signals, sends them to Gemini, and returns a structured Markdown report.

## Architecture

The project is split into simple layers to match the task requirements:

```text
main.py            FastAPI routes and error handling
config.py          Environment configuration
auth.py            API key authentication
rate_limiter.py    In-memory rate limiting
session_store.py   In-memory session tracking
data_collector.py  Async Google News RSS collection
ai_analyzer.py     Async Gemini analysis and fallback report generation
schemas.py         Response models
utils.py           Shared helpers
requirements.txt
.env.example
README.md
```

## Features

- `GET /analyze/{sector}` returns a Markdown market analysis report
- API key authentication with `X-Api-Key`
- In-memory session tracking
- In-memory rate limiting per API key
- Async external calls with `httpx.AsyncClient`
- Swagger docs at `/docs`
- Graceful fallback report if Gemini is unavailable

## Setup

1. Create and activate a virtual environment.

```powershell
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Create your local environment file.

```powershell
Copy-Item .env.example .env
```

4. Add your Gemini API key to `.env`.

5. Start the API.

```powershell
python -m uvicorn main:app --reload
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes for Gemini output | Your Gemini API key |
| `GEMINI_MODEL` | No | Gemini model name. Default: `gemini-2.5-flash` |
| `API_KEYS` | No | Comma-separated API keys allowed to call the API |
| `RATE_LIMIT_REQUESTS` | No | Requests allowed in each rate window |
| `RATE_LIMIT_WINDOW` | No | Rate window in seconds |

## API Endpoints

### `GET /`

Returns service metadata.

### `GET /health`

Returns health status and a UTC timestamp.

### `GET /analyze/{sector}`

Requires `X-Api-Key`.

Example:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/analyze/pharmaceuticals" `
  -Headers @{ "X-Api-Key" = "guest-key-123" }
```

Response shape:

```json
{
  "session_id": "abc-123",
  "sector": "pharmaceuticals",
  "generated_at": "2025-03-26T15:00:00+00:00",
  "requests_remaining": 9,
  "report": "# Trade Opportunities Report: Pharmaceuticals Sector in India\n..."
}
```

### `GET /sessions`

Requires `X-Api-Key`.

Returns only the sessions created with that API key during the current server run.

## Notes

- Storage is in-memory only. Restarting the server clears sessions and rate limit counters.
- Data collection uses Google News RSS as a lightweight current-events source.
- If Gemini fails because of model, key, quota, or network issues, the API still returns a Markdown fallback report.
