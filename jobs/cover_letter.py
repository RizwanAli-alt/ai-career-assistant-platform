"""
Cover-letter generator for the Auto-Apply Agent.

No external API is required – letters are built from the user's profile
skills and the job's details.
"""


def generate_cover_letter(user, job):
    """Return a personalised cover-letter string for *user* applying to *job*."""
    profile = getattr(user, 'profile', None)
    full_name = f"{user.first_name} {user.last_name}".strip() or user.username

    # Collect user skills
    user_skills = []
    if profile and profile.skills:
        user_skills = [s.strip() for s in profile.skills.split(',') if s.strip()]

    # Collect job skills (required + preferred)
    job_skills_raw = list(job.get_required_skills_list())
    if job.preferred_skills:
        job_skills_raw += job.get_preferred_skills_list()
    job_skills_lower = [s.lower() for s in job_skills_raw]

    # Find overlapping skills (case-insensitive substring match)
    matching_skills = [
        s for s in user_skills
        if any(s.lower() in js or js in s.lower() for js in job_skills_lower)
    ]
    if not matching_skills:
        matching_skills = user_skills[:3]

    company_name = job.company.name
    job_title = job.title
    domain = job.company.industry or "your industry"
    skills_text = ", ".join(matching_skills[:5]) if matching_skills else "relevant technical skills"

    cover_letter = (
        f"Dear Hiring Team at {company_name},\n\n"
        f"I am writing to express my strong interest in the {job_title} position at {company_name}. "
        f"As a motivated professional with hands-on experience in {skills_text}, I am confident "
        f"in my ability to make a meaningful contribution to your team.\n\n"
        f"My relevant skills include {skills_text}, which align well with the requirements "
        f"outlined in your job posting. I have developed these competencies through practical "
        f"projects and continuous learning, and I am eager to apply them in a real-world setting "
        f"at {company_name}.\n\n"
        f"I am excited about {company_name} because of your work in {domain}. I believe that "
        f"joining your team would provide me with the opportunity to grow professionally while "
        f"contributing to impactful projects.\n\n"
        f"Thank you for considering my application. I look forward to the opportunity to discuss "
        f"how my skills and enthusiasm can benefit {company_name}.\n\n"
        f"Warm regards,\n{full_name}"
    )
    return cover_letter
