# CareerAI

CareerAI is a Django-based career assistant platform built to help students and job seekers manage the full job-search workflow in one place. It combines CV analysis, skill extraction, job discovery, AI-powered matching, interview practice, community discussion, and learning resources into a single web application.

## Overview

The platform is organized around a practical career workflow:

1. Register and log in.
2. Upload a CV and generate an analysis.
3. Search jobs through the scraper-backed job search page.
4. Compare opportunities against extracted CV skills.
5. Save, apply, or auto-apply to relevant roles.
6. Use the forum, chatbot, interview tools, and learning resources to improve career readiness.

The landing page is public. After login, users return to the home page and can navigate to the dashboard and tools from the shared layout.

## Features

### CV Analyzer
- Upload PDF or DOC/DOCX resumes.
- Extract skills and generate CV feedback.
- Compare resume quality and track progress over time.

### Jobs and matching
- Search jobs through the scraper-driven job search page.
- Switch between demo mode and live scraping.
- Rank jobs by CV match score when a CV has been analyzed.
- Save jobs, manage applications, and configure auto-apply options.
- Generate job alerts and browse company details.

### AI Interview
- Start mock interview sessions from available templates.
- Answer generated questions and review results.
- Track interview history.

### Chatbot
- Ask career questions and get conversational guidance.
- Browse FAQ content and quick tips.
- Review chat session history.

### Forum
- Browse community discussions and categories.
- Create posts, reply to threads, like content, and manage profiles.
- Use leaderboard, notifications, search, and mentorship-style interactions.

### Dashboard
- View a personalized summary of activity.
- Track applications, saved jobs, CV progress, goals, and auto-apply status.

### Resource Hub
- Explore curated learning resources and skill paths.
- Track learning progress and completed resources.

### Notifications
- Receive updates for platform activity.
- Mark notifications as read or archive them.

## Technology stack

- **Backend:** Python 3.10, Django 4.2.11
- **Frontend:** HTML, CSS, JavaScript, Tailwind CDN, GSAP animations
- **Database:** SQLite for local development
- **AI / NLP:** spaCy, Hugging Face Transformers, sentence-transformers, scikit-learn, torch
- **PDF and document parsing:** pdfplumber, PyPDF2, python-docx, pdfminer.six
- **Job scraping:** requests, BeautifulSoup, lxml

## Project structure

```text
fyp/
├── core/              # Django project settings, URLs, WSGI/ASGI
├── users/             # Authentication, profiles, password reset, CV upload
├── cv_analyzer/       # CV upload, analysis, comparison, templates
├── jobs/              # Job listings, scraper search, applications, auto-apply
├── chatbot/           # Career assistant chatbot and FAQ content
├── forum/             # Community forum, posts, replies, badges, notifications
├── dashboard/         # User dashboard, analytics, goals, activity tracking
├── resource_hub/      # Learning resources and skill paths
├── notifications/     # Notification center and preferences
├── ai_interview/      # Interview practice, questions, results, history
├── analyzer/          # CV skill extraction and similarity logic
├── scraper/           # Job scraping, caching, demo data, matching
├── templates/         # Shared and app-specific templates
├── static/            # CSS, JavaScript, and static assets
├── media/             # Uploaded CVs and user files
└── manage.py
```

## Main routes

| Route | Purpose |
|---|---|
| `/` | Public landing page |
| `/auth/` | Register, log in, profile, password reset |
| `/cv-analyzer/` | CV upload and analysis |
| `/jobs/search/` | Scraper-backed job search |
| `/jobs/` | Job listings and related job tools |
| `/interview/` | AI interview practice |
| `/chatbot/` | Career chatbot |
| `/forum/` | Community forum |
| `/dashboard/` | Personal dashboard |
| `/resources/` | Learning resources and skill paths |
| `/notifications/` | Notification center |
| `/admin/` | Django admin |

## Setup

### Prerequisites

- Python 3.10+
- pip

### Installation

1. Clone the repository.

   ```bash
   git clone <repository-url>
   cd fyp
   ```

2. Create and activate a virtual environment.

   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install the dependencies.

   ```bash
   pip install -r requirements.txt
   ```

4. Apply database migrations.

   ```bash
   py manage.py migrate
   ```

5. Start the development server.

   ```bash
   py manage.py runserver
   ```

6. Open the application.

   ```text
   http://127.0.0.1:8000/
   ```

## Runtime notes

- The app uses SQLite by default and ships with a local `db.sqlite3` file.
- Some AI and similarity features fall back gracefully when optional packages are unavailable.
- Job scraping can run in demo mode or live mode from the job search page.
- Logs are written to `logs/django.log`.
- Uploaded files are stored under `media/`.

## Optional dependencies and fallbacks

The project includes several optional packages that improve functionality but are not always required for the app to start:

- `sentence-transformers` and `scikit-learn` for semantic job matching.
- `transformers` and `torch` for NLP-based skill extraction.
- `pdfplumber` and `PyPDF2` for PDF parsing.
- `python-docx` for DOCX parsing.
- `beautifulsoup4`, `requests`, and `lxml` for scraping.

If some of these packages are unavailable, the application falls back to simpler behavior where possible.

## Development tips

- Use `py manage.py check` to validate the project configuration.
- Use `py manage.py makemigrations` and `py manage.py migrate` after changing models.
- Check `logs/django.log` when debugging scraper, analyzer, or forum issues.

## Contributing

1. Fork the repository.
2. Create a feature branch.
3. Commit changes with a clear message.
4. Push the branch and open a pull request.

## License

This project was developed as a Final Year Project (FYP) for academic use.
