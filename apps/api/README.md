# JobFlow

An AI-powered job search assistant I built to help myself find jobs, prep for interviews, and stay organized.

---

## What This Actually Does

### 1. Job Search + Coach
The core of it. Upload your resume, and the AI helps you:
- Find relevant job postings
- Review and tailor your resume for specific roles
- Prepare for interviews with company research and practice questions
- Track your job pipeline (saved → applied → interview → offer)

### 2. Signals (Timeline)
A discussion feed where AI agents share different perspectives on your job search. Post a thought or question, and get varied viewpoints - some supportive, some critical, some with unexpected angles. Helps me think through decisions.

### 3. Councils (Group Chats)
When you need deeper collaboration, spin up a council - a group of agents working together on a specific task. Good for brainstorming or working through complex problems.

---

## Quick Start

```bash
# Clone
git clone https://github.com/your-org/jobflow.git
cd jobflow/ai-service

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure (minimum: OpenAI key + database)
cp .env.example .env
# Edit .env with your OPENAI_API_KEY and DATABASE_URL

# Database (Docker)
docker run -d --name jobflow-db \
  -e POSTGRES_USER=jobflow \
  -e POSTGRES_PASSWORD=jobflow \
  -e POSTGRES_DB=jobflow \
  -p 5432:5432 postgres:15

# Run
uvicorn app.main:app --reload --port 8000
```

Check `http://localhost:8000/health` - you're good.

---

## Configuration

**Required:**
- `OPENAI_API_KEY` - Powers the AI
- `DATABASE_URL` - PostgreSQL connection

**Optional:**
- `RAPIDAPI_KEY` - For job search API
- `TAVILY_API_KEY` - For web research
- Notification webhooks (Slack, Telegram, Discord)

See `.env.example` for all options.

---

## Tech Stack

- Python / FastAPI
- LangGraph for agent orchestration
- PostgreSQL
- OpenAI GPT-4o (configurable)

---

## License

MIT - do whatever you want with it.

---

*Built this for myself. Maybe it helps you too.*
