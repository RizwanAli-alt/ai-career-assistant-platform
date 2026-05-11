# CareerAI

A Django-based career assistant platform for students and job seekers. CareerAI combines CV analysis, job matching, interview practice, community features, and learning resources in one application.

## How it works

1. Create an account and log in.
2. Upload a CV and generate an AI-assisted analysis with ATS scoring.
3. Search jobs through scraper-backed sources in live or demo mode.
4. Compare your CV against job requirements and market skill gaps.
5. Save jobs, manage applications, and configure auto-apply tools.
6. Improve readiness via the chatbot, forum, interview practice, and resource hub.

## Features

**CV Analyzer** — Upload PDF, DOC, or DOCX. Extract text, skills, sections, and contact details. Generate ATS-style scores for format, content, keywords, and readability. Compare CVs and review historical analyses.

**Job Matching** — Scraper-backed job search ranked by CV match score. Save jobs, set alerts, manage applications, and enable auto-apply. Supports live and demo modes.

**AI Interview** — Start mock sessions from templates, answer generated questions, and review results. Full session history and progress tracking.

**Chatbot** — Conversational career guidance with persistent session history.

**Forum** — Community threads with replies and likes. Manage profile activity and follow relevant discussions.

**Dashboard** — Personal overview of CV status, saved jobs, applications, and recent activity.

**Resource Hub** — Curated learning materials and skill paths with progress tracking.

**Notifications** — Realtime platform updates via Django Channels. Mark as read or archive.

## Tech stack

| Layer | Technologies |
|---|---|
| Backend | Python 3.10, Django 4.2.9, Channels 4.1.0 |
| AI / NLP | sentence-transformers, transformers, torch, scikit-learn, spaCy, NLTK |
| Documents | pdfplumber, pypdf, pdfminer.six, python-docx |
| Scraping | requests, beautifulsoup4, lxml |
| Background jobs | Celery, Redis, django-celery-results |
| Frontend | HTML, CSS, JavaScript, Bootstrap, django-crispy-forms |
| Database | SQLite (development) |

## Project structure

```
fyp/
├── core/              # Settings, URLs, ASGI/WSGI
├── users/             # Authentication and user profile
├── cv_analyzer/       # CV upload, extraction, scoring, comparison
├── jobs/              # Job search, applications, auto-apply, alerts
├── chatbot/           # Career chatbot and chat history
├── forum/             # Community posts, replies, profiles
├── dashboard/         # User dashboard and summary views
├── resource_hub/      # Learning resources and skill paths
├── notifications/     # Notification center and realtime hooks
├── ai_interview/      # Interview practice and results
├── analyzer/          # CV parsing, scoring, gaps, suggestions
├── scraper/           # Job scraping, caching, matching
├── templates/         # Shared and app-specific templates
├── static/            # CSS, JavaScript, and assets
├── media/             # Uploaded CVs and profile files
├── logs/              # Application logs
├── models/            # Skill and market data (JSON)
├── scripts/           # Development utility scripts
├── temp/              # Temporary processing files
└── manage.py
```

## Routes

| Route | Purpose |
|---|---|
| `/` | Public landing page |
| `/auth/` | Authentication and profile |
| `/cv-analyzer/` | CV upload and analysis |
| `/jobs/` | Jobs, alerts, applications, auto-apply |
| `/chatbot/` | Career chatbot |
| `/forum/` | Community forum |
| `/dashboard/` | Personal dashboard |
| `/resources/` | Learning resources |
| `/notifications/` | Notification center |
| `/interview/` | Interview practice |
| `/admin/` | Django admin |

## Setup

**Prerequisites:** Python 3.10+, pip

```bash
# 1. Clone and enter the project
git clone <repository-url>
cd fyp

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply migrations
python manage.py migrate

# 5. Start the development server
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

## Runtime notes

- SQLite is used by default (`db.sqlite3`).
- Uploaded files are stored in `media/`; logs go to `logs/django.log`.
- CV analysis degrades gracefully when some AI packages are unavailable, but PDF extraction requires `pdfplumber` or `pypdf`.
- Job scraping supports demo mode and live mode.
- Realtime notifications require an ASGI server (Channels).
- Run `python manage.py check` to validate your configuration.
- After model changes: `python manage.py makemigrations && python manage.py migrate`.

## Contributing

1. Fork the repository.
2. Create a feature branch.
3. Commit with a clear, descriptive message.
4. Push the branch and open a pull request.

## License

Developed as a Final Year Project (FYP) for academic use.