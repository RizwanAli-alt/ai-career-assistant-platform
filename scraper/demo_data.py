# scraper/demo_data.py
"""
Realistic demo job listings for LinkedIn, Indeed, and Rozee.pk.
Used when demo_mode=True so the UI works without live scraping.
"""

import random
from typing import List
from .models import JobListing

# ─── Skill pool ──────────────────────────────────────────────────────────────
_TECH_SKILLS = [
    "Python", "Django", "Flask", "FastAPI", "JavaScript", "TypeScript",
    "React", "Vue.js", "Angular", "Node.js", "Express", "PostgreSQL",
    "MySQL", "MongoDB", "Redis", "Docker", "Kubernetes", "AWS", "GCP",
    "Azure", "Git", "REST API", "GraphQL", "CI/CD", "Linux", "Nginx",
    "Celery", "Machine Learning", "TensorFlow", "PyTorch", "Pandas",
    "NumPy", "Scikit-learn", "NLP", "Computer Vision", "SQL", "NoSQL",
    "Java", "Spring Boot", "Kotlin", "Swift", "Flutter", "Laravel",
    "PHP", "Ruby on Rails", "Go", "Rust", "C++", "C#", ".NET",
]

_MODALITIES = ["Remote", "Hybrid", "On-site", "Remote", "Remote"]  # bias remote

_LINKEDIN_COMPANIES = [
    "Google", "Meta", "Microsoft", "Amazon", "Stripe", "Shopify",
    "Grab", "Careem", "Systems Limited", "10Pearls", "Arbisoft",
    "Netsol Technologies", "TRG", "Devsinc", "Tkxel",
]

_INDEED_COMPANIES = [
    "IBM", "Accenture", "Deloitte", "PwC", "Capgemini", "Infosys",
    "Tata Consultancy", "HBL", "UBL", "Telenor", "Jazz", "PTCL",
    "K-Electric", "NetSuite", "SAP Pakistan",
]

_ROZEE_COMPANIES = [
    "Contour Software", "VentureDive", "Ingenio", "Programmers Force",
    "Folio3", "Creative Chaos", "Corvit Networks", "Techlogix",
    "Ovex Technologies", "Nextbridge", "Softech Solutions",
    "Emumba", "i2c Inc.", "PayFast", "Data Annotation",
]

_LOCATIONS_PK = [
    "Lahore, Pakistan", "Karachi, Pakistan", "Islamabad, Pakistan",
    "Rawalpindi, Pakistan", "Multan, Pakistan", "Faisalabad, Pakistan",
]

_LOCATIONS_INTL = [
    "Remote", "Dubai, UAE", "London, UK", "Singapore",
    "Toronto, Canada", "Berlin, Germany",
]

_SALARY_RANGES = [
    "PKR 80,000 – 120,000/mo", "PKR 120,000 – 180,000/mo",
    "PKR 180,000 – 250,000/mo", "USD 2,000 – 3,500/mo",
    "USD 3,500 – 6,000/mo", "Competitive",
]

_DESCRIPTIONS = [
    "We are looking for a passionate engineer to join our growing team. "
    "You will work on cutting-edge projects and collaborate with a talented group of developers.",

    "Join our dynamic team and help us build scalable, high-performance systems. "
    "You will own features end-to-end from design to deployment.",

    "We need an experienced developer who can hit the ground running. "
    "Our tech stack is modern and our team is fully remote-friendly.",

    "Be part of a fast-growing startup with a strong engineering culture. "
    "We value clean code, great documentation, and continuous improvement.",

    "Work on mission-critical systems that impact millions of users. "
    "We offer competitive pay, flexible hours, and a great benefits package.",
]

# ─── Title templates ─────────────────────────────────────────────────────────
_TITLE_TEMPLATES = {
    "python":       ["Python Developer", "Python Backend Engineer", "Senior Python Developer",
                     "Python/Django Developer", "Python Full Stack Engineer"],
    "react":        ["React Developer", "Frontend Engineer (React)", "Senior React Developer",
                     "React/Next.js Developer", "UI Engineer – React"],
    "django":       ["Django Developer", "Django Backend Engineer", "Python/Django Engineer",
                     "Full Stack Developer (Django/React)", "Django REST API Developer"],
    "javascript":   ["JavaScript Developer", "Full Stack JS Engineer", "Node.js Developer",
                     "JavaScript/TypeScript Engineer", "Frontend JavaScript Developer"],
    "machine learning": ["ML Engineer", "Machine Learning Engineer", "AI/ML Developer",
                         "Data Scientist", "NLP Engineer"],
    "devops":       ["DevOps Engineer", "Site Reliability Engineer", "Cloud Engineer",
                     "AWS DevOps Engineer", "Infrastructure Engineer"],
    "flutter":      ["Flutter Developer", "Mobile Developer (Flutter)", "Cross-Platform Mobile Engineer",
                     "Flutter/Dart Developer", "Mobile App Developer"],
    "data":         ["Data Engineer", "Data Analyst", "Business Intelligence Developer",
                     "Data Pipeline Engineer", "Analytics Engineer"],
    "default":      ["Software Engineer", "Full Stack Developer", "Backend Developer",
                     "Web Developer", "Senior Software Engineer", "Tech Lead"],
}


def _pick_title(query: str) -> str:
    q = query.lower()
    for key, titles in _TITLE_TEMPLATES.items():
        if key in q:
            return random.choice(titles)
    return random.choice(_TITLE_TEMPLATES["default"])


def _pick_skills(query: str, n: int = 6) -> List[str]:
    """Return a mix of query-relevant + random skills."""
    q = query.lower()
    relevant = [s for s in _TECH_SKILLS if s.lower() in q or q in s.lower()]
    others = [s for s in _TECH_SKILLS if s not in relevant]
    pool = relevant + random.sample(others, min(len(others), 20))
    return random.sample(pool, min(n, len(pool)))


def _pick_location(portal: str) -> str:
    if portal == "Rozee.pk":
        return random.choice(_LOCATIONS_PK)
    if portal == "LinkedIn":
        return random.choice(_LOCATIONS_PK + _LOCATIONS_INTL)
    return random.choice(_LOCATIONS_PK + _LOCATIONS_INTL)


def generate_demo_jobs(query: str, location: str = "", max_per_portal: int = 10) -> List[JobListing]:
    """Generate realistic demo jobs for all three portals."""
    jobs: List[JobListing] = []

    portals_cfg = [
        ("LinkedIn",  _LINKEDIN_COMPANIES, "https://linkedin.com/jobs/view/"),
        ("Indeed",    _INDEED_COMPANIES,   "https://indeed.com/viewjob?jk="),
        ("Rozee.pk",  _ROZEE_COMPANIES,    "https://rozee.pk/job/"),
    ]

    for portal, companies, base_url in portals_cfg:
        for i in range(max_per_portal):
            title = _pick_title(query)
            company = random.choice(companies)
            loc = location.strip() or _pick_location(portal)
            skills = _pick_skills(query)
            job_id = random.randint(100000, 999999)

            jobs.append(JobListing(
                title=title,
                company=company,
                location=loc,
                portal=portal,
                url=f"{base_url}{job_id}",
                description=random.choice(_DESCRIPTIONS),
                skills_mentioned=skills,
                modality=random.choice(_MODALITIES),
                salary=random.choice(_SALARY_RANGES),
                posted_date=f"{random.randint(1, 7)} days ago",
                job_type=random.choice(["Full-time", "Contract", "Part-time"]),
            ))

    random.shuffle(jobs)
    return jobs