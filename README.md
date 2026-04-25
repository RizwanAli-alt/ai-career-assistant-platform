# CareerAI — AI-Powered Career Platform

CareerAI is a Django-based web platform designed to help Pakistani graduates build the career they actually want. It combines AI-driven tools for CV analysis, skill gap detection, smart job matching, interview preparation, and community features — all in one place.

---

## Features

| Module | Description |
|---|---|
| **CV Analyzer** | Upload your CV and get AI-powered feedback, skill extraction, and improvement suggestions |
| **Job Matching** | Smart job recommendations, auto-apply support, and AI-generated cover letters |
| **AI Interview** | Practice mock interviews with AI-generated questions and instant feedback |
| **Chatbot** | Conversational AI assistant for career guidance |
| **Forum** | Community discussion board for peer support and knowledge sharing |
| **Dashboard** | Personalised overview of activity, progress, and recommendations |
| **Resource Hub** | Curated learning resources for upskilling |
| **Notifications** | Real-time alerts for job matches, forum replies, and platform updates |

---

## Tech Stack

- **Backend:** Python 3 / Django 5.2
- **Frontend:** HTML, CSS (custom design system with CSS variables), JavaScript, GSAP animations
- **Database:** SQLite (default, swappable via `settings.py`)
- **AI Integration:** OpenAI / custom AI services (configured per module)
- **Media Storage:** Local file system (`/media/`)

---

## Project Structure

```
FYP-TEAM000-AI/
├── core/               # Django project settings, URLs, WSGI/ASGI
├── users/              # Authentication & user profiles
├── cv_analyzer/        # CV upload and AI analysis
├── jobs/               # Job listings, matching, auto-apply, cover letters
├── ai_interview/       # Mock interview generation and evaluation
├── chatbot/            # Conversational career assistant
├── forum/              # Community forum
├── dashboard/          # User dashboard
├── resource_hub/       # Learning resources
├── notifications/      # Notification system
├── templates/          # HTML templates (extends base.html)
├── static/             # CSS, JS, images
├── media/              # User-uploaded files
└── manage.py
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- pip

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/fa22-bse-058-droid/FYP-TEAM000-AI.git
   cd FYP-TEAM000-AI
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate      # macOS/Linux
   venv\Scripts\activate         # Windows
   ```

3. **Install dependencies**

   ```bash
   pip install django
   # Install any additional packages required by the project
   ```

4. **Apply database migrations**

   ```bash
   python manage.py migrate
   ```

5. **Run the development server**

   ```bash
   python manage.py runserver
   ```

6. Open your browser and navigate to `http://127.0.0.1:8000/`

---

## URL Routes

| URL | Module |
|---|---|
| `/` | Home / Landing page |
| `/auth/` | User registration & login |
| `/cv-analyzer/` | CV Analyzer |
| `/jobs/` | Job board & matching |
| `/interview/` | AI Interview practice |
| `/chatbot/` | AI Chatbot |
| `/forum/` | Community forum |
| `/dashboard/` | User dashboard |
| `/resources/` | Resource hub |
| `/notifications/` | Notifications |
| `/admin/` | Django admin panel |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "feat: add your feature"`
4. Push the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## Team

**FYP Team 000 — AI Track**  
BS Software Engineering, 2022 cohort

---

## License

This project is developed as a Final Year Project (FYP) for academic purposes.
