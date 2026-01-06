# AutoApply AI

A Python backend for automating job applications. Scrapes jobs from multiple platforms, uses **Google Gemini AI** (FREE) to tailor resumes, and tracks applications.

## Features

- **Job Scraping** - Naukri, LinkedIn, Instahire with anti-detection
- **JD Analysis** - Extract skills, requirements, and red flags
- **Resume Tailoring** - Three levels: conservative, moderate, aggressive
- **Cover Letters** - Personalized, non-generic generation
- **Match Scoring** - Detailed candidate-job fit analysis
- **Application Tracking** - Full pipeline from scraped to offer
- **Zero Cost** - Uses Gemini free tier (1,500 requests/day)

## Setup

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Configure
cp .env.example .env
# Add your GEMINI_API_KEY to .env

# Run
uvicorn api.main:app --reload --port 8000
```

### Get Gemini API Key (FREE)
1. Visit https://aistudio.google.com/app/apikey
2. Create a new API key
3. Add to `.env`: `GEMINI_API_KEY=your_key`

API docs: http://localhost:8000/docs

## Project Structure

```
├── api/          # FastAPI endpoints
├── ai/           # Gemini AI integrations
├── scrapers/     # Web scrapers
├── database/     # SQLAlchemy models
├── utils/        # Helpers
└── tests/        # Test suite
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/jobs/scrape` | Start background scraping |
| `GET /api/jobs` | List jobs with filters |
| `POST /api/ai/analyze-jd` | Analyze job description |
| `POST /api/ai/tailor-resume` | Tailor resume for job |
| `POST /api/ai/generate-cover-letter` | Generate cover letter |
| `GET /api/ai/usage-stats` | Check API usage |
| `GET /api/monitoring/health` | Service health check |

## Rate Limits

Gemini free tier:
- 1,500 requests/day
- 15 requests/minute
- Caching reduces actual API calls

## Configuration

Required in `.env`:
```
GEMINI_API_KEY=your_key_here
DATABASE_URL=sqlite:///./app.db
```

## License

MIT
