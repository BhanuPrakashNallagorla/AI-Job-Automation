<div align="center">

# 🤖 AutoApply AI

### Intelligent Job Application Automation Platform

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)](https://fastapi.tiangolo.com)
[![Claude AI](https://img.shields.io/badge/Claude-Sonnet%20%7C%20Opus-ff6b35.svg)](https://anthropic.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*Scrape jobs. Tailor resumes with AI. Land interviews faster.*

[Features](#-features) • [Quick Start](#-quick-start) • [API Docs](#-api-endpoints) • [Architecture](#-architecture)

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🕷️ Multi-Platform Scraping
- **Naukri** - Full support with anti-detection
- **LinkedIn** - Session-based authentication
- **Instahire** - Platform-specific parsing
- Automatic retry & rate limiting

</td>
<td width="50%">

### 🧠 AI-Powered Analysis
- **JD Analysis** - Extract skills, requirements, red flags
- **Match Scoring** - Detailed compatibility breakdown
- **Smart Caching** - Avoid redundant API calls

</td>
</tr>
<tr>
<td width="50%">

### 📝 Resume Tailoring
Three tailoring levels:
| Level | Description |
|-------|-------------|
| 🟢 Conservative | Subtle reordering & tweaks |
| 🟡 Moderate | Keyword optimization |
| 🔴 Aggressive | Full restructuring |

*100% truthful - Never fabricates experience*

</td>
<td width="50%">

### 💌 Cover Letter Generation
- **Non-generic** opening hooks
- **Company-specific** personalization
- Multiple tones: Professional, Conversational, Enthusiastic
- Auto follow-up email generation

</td>
</tr>
</table>

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL (or SQLite for dev)
- [Anthropic API Key](https://console.anthropic.com)

### Installation

```bash
# Clone the repository
git clone https://github.com/BhanuPrakashNallagorla/AI-Job-Automation.git
cd AI-Job-Automation/autoapply-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Run the Server

```bash
uvicorn api.main:app --reload --port 8000
```

🎉 **API Docs available at:** http://localhost:8000/docs

---

## 📡 API Endpoints

### Jobs
| Method | Endpoint | Description |
|:------:|----------|-------------|
| `POST` | `/api/jobs/scrape` | Start background scraping |
| `GET` | `/api/jobs` | List jobs with filters |
| `GET` | `/api/jobs/{id}` | Get job details |
| `PUT` | `/api/jobs/{id}/status` | Update review status |

### AI Operations
| Method | Endpoint | Description |
|:------:|----------|-------------|
| `POST` | `/api/ai/analyze-jd` | Analyze job description |
| `POST` | `/api/ai/tailor-resume` | Generate tailored resume |
| `POST` | `/api/ai/generate-cover-letter` | Create personalized letter |
| `POST` | `/api/ai/match-score` | Calculate compatibility |

### Applications
| Method | Endpoint | Description |
|:------:|----------|-------------|
| `POST` | `/api/applications` | Track new application |
| `GET` | `/api/applications/stats` | Dashboard statistics |
| `POST` | `/api/applications/{id}/follow-up` | Set reminder |

---

## 🏗️ Architecture

```
autoapply-ai/
├── 🌐 api/                # FastAPI endpoints
│   ├── main.py           # App entry + middleware
│   └── routes/           # jobs, applications, ai, scraper
├── 🕷️ scrapers/           # Web scraping engines
│   ├── base_scraper.py   # Anti-detection base class
│   ├── naukri_scraper.py
│   ├── linkedin_scraper.py
│   └── instahire_scraper.py
├── 🤖 ai/                 # AI modules
│   ├── jd_analyzer.py    # Claude Sonnet
│   ├── resume_tailor.py  # Claude Opus
│   ├── cover_letter_generator.py
│   └── match_scorer.py
├── 🗄️ database/           # SQLAlchemy ORM
├── 🛠️ utils/              # Helpers
└── 🧪 tests/              # Pytest suite
```

---

## 💰 Cost Estimates

| Operation | Model | Avg Cost |
|-----------|:-----:|:--------:|
| JD Analysis | Sonnet | ~$0.005 |
| Resume Tailor | Opus | ~$0.05 |
| Cover Letter | Opus | ~$0.03 |
| Match Score | Sonnet | ~$0.005 |

**Monthly estimate for 100 applications: ~$10-15**

Built-in budget alerts to prevent overspending.

---

## 🔧 Configuration

Key environment variables in `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-...     # Required
DATABASE_URL=sqlite:///./app.db  # Or PostgreSQL
DAILY_BUDGET_USD=20.0            # Cost limit
MAX_SCRAPING_PAGES=10            # Per search
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage report
pytest tests/ --cov=. --cov-report=html
```

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

<div align="center">

**Made with ❤️ for job seekers everywhere**

⭐ Star this repo if it helps your job search!

</div>
