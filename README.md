# Trade Opportunities API

A simple FastAPI API that takes a sector name and returns a Markdown trade report for India.

## Run

powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn main:app --reload

Open: `http://127.0.0.1:8000/docs`

## `.env`

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
API_KEYS=guest-key-123,demo-key-456,my-secret-key
RATE_LIMIT_REQUESTS=10
RATE_LIMIT_WINDOW=3600
```

## Main Endpoint

`GET /analyze/{sector}`

Example:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/analyze/pharmaceuticals" `
  -Headers @{ "X-Api-Key" = "guest-key-123" }
```

Example response:

```json
{
  "session_id": "abc-123",
  "sector": "pharmaceuticals",
  "generated_at": "2025-03-26T15:00:00+00:00",
  "requests_remaining": 9,
  "report": "# Trade Opportunities Report: Pharmaceuticals Sector in India\n..."
}
```

## Other Endpoints

- `GET /` for basic API info
- `GET /health` for health check
- `GET /sessions` to see your current in-memory sessions
