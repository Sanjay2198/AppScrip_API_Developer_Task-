# Trade Opportunities API

A FastAPI service that searches for current market data and uses **Google Gemini** to generate structured trade opportunity reports for Indian industry sectors.

---

## Features

- `GET /analyze/{sector}` — Returns a full Markdown market analysis report
- API key authentication via `X-Api-Key` header
- In-memory rate limiting (10 requests/hour per key)
- Session tracking (in-memory)
- DuckDuckGo web search for live market data (no API key needed)
- Auto-generated Swagger docs at `/docs`

---

## Project Structure

```
├── main.py            # FastAPI app and routes
├── auth.py            # API key authentication
├── rate_limiter.py    # In-memory rate limiter
├── data_collector.py  # DuckDuckGo web search
├── ai_analyzer.py     # Google Gemini integration
├── config.py          # Environment variable settings
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup

### 1. Clone and enter the project

```bash
git clone <repo-url>
cd AppScrip_API_Developer_Task-
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Get a free Gemini API key

1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click **Create API Key**
4. Copy the key

### 5. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set your Gemini key:

```
GEMINI_API_KEY=your_actual_key_here
```

### 6. Run the server

```bash
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`

---

## API Usage

### Authentication

All requests (except `/health`) require the `X-Api-Key` header.

Default demo keys (from `.env.example`): `guest-key-123` or `demo-key-456`

---

### Endpoints

#### `GET /analyze/{sector}`

Generates a trade opportunities report for the given sector.

**Example — curl:**

```bash
curl -X GET "http://127.0.0.1:8000/analyze/pharmaceuticals" \
     -H "X-Api-Key: guest-key-123"
```

**Example — PowerShell:**

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/analyze/technology" `
  -Headers @{ "X-Api-Key" = "guest-key-123" }
```

**Sample Response:**

```json
{
  "session_id": "abc123-...",
  "sector": "pharmaceuticals",
  "generated_at": "2025-01-01T10:00:00",
  "requests_remaining": 9,
  "report": "# Trade Opportunities Report: Pharmaceuticals Sector in India\n\n## Executive Summary\n..."
}
```

The `report` field contains a full **Markdown** document you can save as a `.md` file:

```bash
curl -s "http://127.0.0.1:8000/analyze/agriculture" \
     -H "X-Api-Key: guest-key-123" \
  | python -c "import sys,json; print(json.load(sys.stdin)['report'])" \
  > agriculture_report.md
```

---

#### `GET /sessions`

List all analysis sessions for your API key.

```bash
curl "http://127.0.0.1:8000/sessions" -H "X-Api-Key: guest-key-123"
```

---

#### `GET /health`

No auth required. Simple uptime check.

```bash
curl http://127.0.0.1:8000/health
```

---

#### Interactive Docs

Open `http://127.0.0.1:8000/docs` in your browser for the full Swagger UI where you can test all endpoints.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Your Google Gemini API key |
| `API_KEYS` | `guest-key-123,demo-key-456` | Comma-separated valid API keys |
| `RATE_LIMIT_REQUESTS` | `10` | Max requests per window per key |
| `RATE_LIMIT_WINDOW` | `3600` | Window size in seconds (1 hour) |

---

## Supported Sectors (examples)

Any sector name works. Some examples:

- `pharmaceuticals`
- `technology`
- `agriculture`
- `textiles`
- `automobiles`
- `renewable-energy`
- `steel`
- `chemicals`

---

## Error Responses

| Code | Meaning |
|---|---|
| `400` | Invalid sector name |
| `401` | Missing or invalid API key |
| `429` | Rate limit exceeded |
| `500` | Server error (check Gemini key or network) |
