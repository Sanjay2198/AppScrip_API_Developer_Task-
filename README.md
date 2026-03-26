# Trade Opportunities API

A simple FastAPI service that:

- accepts an Indian sector name
- fetches recent Google News RSS items
- asks Gemini for a Markdown trade report
- falls back to a basic Markdown summary if Gemini is unavailable

## Files

This project is intentionally simple and currently uses a single application file:

```text
main.py
requirements.txt
.env.example
README.md
```

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

3. Copy the env template and add your Gemini key.

```powershell
Copy-Item .env.example .env
```

4. Run the server.

```powershell
python -m uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes for Gemini output | Your Gemini API key |
| `GEMINI_MODEL` | No | Gemini model name. Default: `gemini-2.5-flash` |
| `API_KEYS` | No | Comma-separated API keys allowed to call the API |
| `RATE_LIMIT_REQUESTS` | No | Requests allowed in each rate window |
| `RATE_LIMIT_WINDOW` | No | Rate window in seconds |

## Endpoints

### `GET /`

Basic API info.

### `GET /health`

No authentication required. Returns service health and UTC timestamp.

### `GET /analyze/{sector}`

Requires `X-Api-Key`.

Example:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/analyze/pharmaceuticals" `
  -Headers @{ "X-Api-Key" = "guest-key-123" }
```

Successful responses return:

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

- The Swagger UI is available at `http://127.0.0.1:8000/docs`.
- Google News fetching is best-effort. If news cannot be fetched, the app still tries to produce a report.
- If Gemini fails because of key, network, quota, or model issues, the endpoint returns a fallback Markdown report instead of crashing.
