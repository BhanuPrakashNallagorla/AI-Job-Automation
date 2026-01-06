# AutoApply AI

A Python backend for automating job applications. Scrapes jobs from multiple platforms, uses Claude AI to tailor resumes, and tracks applications.

## Features

- **Job Scraping** - Naukri, LinkedIn, Instahire with anti-detection
- **JD Analysis** - Extract skills, requirements, and red flags using Claude Sonnet
- **Resume Tailoring** - Three levels: conservative, moderate, aggressive (Claude Opus)
- **Cover Letters** - Personalized, non-generic generation
- **Match Scoring** - Detailed candidate-job fit analysis
- **Application Tracking** - Full pipeline from scraped to offer

## Setup

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Configure
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# Run
uvicorn api.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Project Structure

```
├── api/          # FastAPI endpoints
├── ai/           # Claude AI integrations
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
| `GET /api/applications/stats` | Application statistics |

## Configuration

Required in `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=sqlite:///./app.db
```

## License

MIT
