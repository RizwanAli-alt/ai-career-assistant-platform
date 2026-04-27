"""
views.py — AI Career Chatbot (improved)

Key improvements over v1:
  - Context-aware bot: reads last N messages before responding
  - 14 intent categories (up from 7) with regex + weighted keyword scoring
  - Rich, multi-paragraph responses for every intent
  - AJAX chat endpoint — no full page reload needed
  - Auto-title sessions from first user message
  - Rate limiting (max 20 messages / minute per user)
  - Input sanitisation & max length enforcement
  - Atomic view-count increments (avoids race conditions)
  - Context-aware clarification for vague follow-ups
  - User analytics view
  - Proper logging throughout
"""

from __future__ import annotations

import html
import logging
import re
from datetime import timedelta
from typing import Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import ChatMessageForm, UserFeedbackForm
from .models import (
    FAQ, CareerTip, ChatMessage, ChatSession,
    FAQCategory, UserFeedback,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RATE_LIMIT_MESSAGES      = 20   # max user messages per window
RATE_LIMIT_WINDOW_MINUTES = 1   # rolling window length
MAX_CONTEXT_MESSAGES     = 10   # previous messages fed into context check
MAX_MESSAGE_LENGTH       = 2000 # character cap on incoming messages

STOP_WORDS = frozenset({
    'a','an','the','and','or','but','if','to','for','of','in','on','at',
    'is','are','am','i','you','my','me','can','how','what','when','where',
    'why','with','about','please','help','do','does','it','this','that',
    'have','has','been','will','would','could','should','its','be','was',
    'had','not','they','we','he','she','some','any','all','more','so',
    'get','use','need','want','know','just','also','very','really','little',
    'bit','think','going',
})

# ---------------------------------------------------------------------------
# Intent definitions
# ---------------------------------------------------------------------------

INTENTS: dict[str, dict] = {
    "greeting": {
        "patterns": [r"\b(hi+|hello+|hey+|howdy|greetings|good\s+(morning|afternoon|evening|day))\b"],
        "keywords": {"hi": 2, "hello": 2, "hey": 2},
        "confidence": 0.95,
    },
    "thanks": {
        "patterns": [r"\b(thank(s| you)|appreciate|great|awesome|helpful|perfect|cheers)\b"],
        "keywords": {"thank": 2, "thanks": 2, "appreciate": 2},
        "confidence": 0.90,
    },
    "faq_request": {
        "patterns": [r"\b(faq|frequently asked|what can you|show me|list|options)\b"],
        "keywords": {"faq": 3, "list": 1, "options": 1},
        "confidence": 0.90,
    },
    "resume": {
        "patterns": [r"\b(resum[e\xe9]|curriculum vitae|cv|cover letter|portfolio|references|ats)\b"],
        "keywords": {"resume": 3, "cv": 3, "ats": 2, "cover": 2, "letter": 1, "format": 1, "template": 1},
        "confidence": 0.88,
    },
    "interview": {
        "patterns": [r"\b(interview(ing|s)?|behavioral|technical interview|panel|mock|star method|hiring process)\b"],
        "keywords": {"interview": 3, "behavioral": 2, "star": 2, "mock": 2, "prepare": 2, "question": 1},
        "confidence": 0.88,
    },
    "salary": {
        "patterns": [r"\b(salary|compensation|pay(check|raise)?|wage|negotiat|offer|package|benefits|raise|bonus|equity|stock)\b"],
        "keywords": {"salary": 3, "negotiate": 3, "compensation": 2, "pay": 2, "raise": 2, "bonus": 2, "equity": 2},
        "confidence": 0.88,
    },
    "job_search": {
        "patterns": [r"\b(job(s| search| hunt|board)?|position|opening|vacancy|apply|application|linkedin|indeed|hiring|recruit)\b"],
        "keywords": {"job": 3, "apply": 2, "application": 2, "linkedin": 2, "hiring": 2, "vacancy": 2},
        "confidence": 0.85,
    },
    "skills": {
        "patterns": [r"\b(skill(s)?|learn(ing)?|course|certification|upskill|training|bootcamp|degree|study|udemy|coursera)\b"],
        "keywords": {"skill": 3, "learn": 2, "course": 2, "certification": 2, "training": 2, "bootcamp": 2},
        "confidence": 0.85,
    },
    "networking": {
        "patterns": [r"\b(network(ing)?|connection(s)?|referral|mentor(ship)?|community|cold (email|outreach))\b"],
        "keywords": {"network": 3, "connection": 2, "referral": 2, "mentor": 2, "outreach": 2},
        "confidence": 0.85,
    },
    "career_change": {
        "patterns": [r"\b(career (change|switch|transition|pivot)|switch(ing)? (career|field|industry)|new (field|industry|career))\b"],
        "keywords": {"change": 2, "switch": 2, "transition": 3, "pivot": 3, "career": 1, "field": 1},
        "confidence": 0.88,
    },
    "remote_work": {
        "patterns": [r"\b(remote|wfh|work from home|hybrid|distributed|telecommut)\b"],
        "keywords": {"remote": 3, "wfh": 3, "hybrid": 2, "home": 1},
        "confidence": 0.85,
    },
    "layoff_jobless": {
        "patterns": [r"\b(laid off|layoff|unemployed|lost (my )?job|fired|redundan|let go)\b"],
        "keywords": {"laid": 2, "layoff": 3, "unemployed": 3, "fired": 3, "redundant": 3},
        "confidence": 0.92,
    },
    "linkedin": {
        "patterns": [r"\b(linkedin( profile)?|optimize profile|linkedin (headline|summary|bio))\b"],
        "keywords": {"linkedin": 3, "profile": 2, "headline": 2, "summary": 1},
        "confidence": 0.88,
    },
    "cover_letter": {
        "patterns": [r"\b(cover letter|motivation letter|application letter|letter of interest)\b"],
        "keywords": {"cover": 2, "letter": 2, "motivation": 1},
        "confidence": 0.90,
    },
}

# ---------------------------------------------------------------------------
# Response templates (rich, multi-paragraph)
# ---------------------------------------------------------------------------

RESPONSES: dict[str, str] = {
    "greeting": (
        "Hello! \U0001f44b Great to have you here.\n\n"
        "I'm your AI Career Assistant. I can help with:\n\n"
        "\U0001f4c4 Resume & CV optimisation\n"
        "\U0001f3af Interview preparation\n"
        "\U0001f4b0 Salary negotiation\n"
        "\U0001f50d Job search strategy\n"
        "\U0001f4da Skills development\n"
        "\U0001f91d Networking & LinkedIn\n"
        "\U0001f504 Career transitions\n"
        "\U0001f4dd Cover letters\n"
        "\U0001f3e0 Remote work tips\n\n"
        "What would you like to work on today?"
    ),
    "thanks": (
        "You're very welcome! \U0001f60a\n\n"
        "Feel free to come back any time you need career guidance. "
        "Best of luck on your journey! \U0001f680"
    ),
    "faq_request": (
        "\U0001f4cb Here's everything I can help you with:\n\n"
        "- Resume & CV — format, ATS, action verbs, achievements\n"
        "- Cover Letter — structure, personalisation, tone\n"
        "- Interview Prep — STAR method, behavioural & technical questions\n"
        "- Salary Negotiation — research, scripts, total compensation\n"
        "- Job Search — strategy, LinkedIn, hidden job market\n"
        "- LinkedIn Profile — headline, summary, keywords\n"
        "- Skills Development — courses, certifications, gap analysis\n"
        "- Networking — outreach templates, cold email, informational interviews\n"
        "- Career Change — transferable skills, reframing, bridging gaps\n"
        "- Remote Work — finding remote jobs, productivity tips\n"
        "- After a Layoff — action plan and support\n\n"
        "Just type your question and I'll do my best to help!"
    ),
    "resume": (
        "\U0001f4c4 Resume & CV Optimisation\n\n"
        "Format & Structure\n"
        "- Use a clean, single-column ATS-friendly layout (no tables, columns, graphics)\n"
        "- Font: Calibri, Georgia, or Garamond at 10-12pt\n"
        "- Keep it to 1 page (under 5 years experience) or 2 pages max\n"
        "- Sections: Summary -> Experience -> Skills -> Education -> Certifications\n\n"
        "Writing High-Impact Bullets\n"
        "Use the formula: Action verb + Task + Measurable result\n"
        "Bad: 'Responsible for managing a team'\n"
        "Good: 'Led a cross-functional team of 8, shipping features 20% faster'\n\n"
        "ATS Optimisation\n"
        "- Mirror exact keywords from the job description\n"
        "- Spell out acronyms (e.g. 'Search Engine Optimisation (SEO)')\n"
        "- Avoid headers in text boxes — ATS can't read them\n\n"
        "Summary Section\n"
        "Write 2-3 sentences: who you are, your top 2 skills, and your career goal.\n\n"
        "Want help with a specific section — like your summary or work experience bullets?"
    ),
    "interview": (
        "\U0001f3af Interview Preparation Guide\n\n"
        "Before the Interview\n"
        "- Research: company mission, recent news, products, team structure\n"
        "- Re-read the job description and map your experience to each requirement\n"
        "- Prepare 5-8 STAR stories covering: leadership, failure, conflict, achievement\n\n"
        "The STAR Method\n"
        "- Situation: set the scene briefly\n"
        "- Task: what was your responsibility?\n"
        "- Action: what did YOU specifically do?\n"
        "- Result: quantify the outcome (%, money saved, time reduced)\n\n"
        "Question Types\n"
        "- Behavioural: 'Tell me about a time when...'\n"
        "- Situational: 'What would you do if...'\n"
        "- Technical: role-specific knowledge checks\n\n"
        "Questions to Ask Them\n"
        "- 'What does success look like in this role after 90 days?'\n"
        "- 'What are the biggest challenges the team faces right now?'\n"
        "- 'How do you support professional development?'\n\n"
        "After the Interview\n"
        "Send a thank-you email within 24 hours referencing something specific from the conversation.\n\n"
        "Would you like help crafting answers to specific questions?"
    ),
    "salary": (
        "\U0001f4b0 Salary Negotiation Strategy\n\n"
        "Step 1 — Research\n"
        "Use Glassdoor, LinkedIn Salary, Levels.fyi, and Payscale. Build a range, not a single number.\n\n"
        "Step 2 — Never go first\n"
        "When asked for expectations, deflect:\n"
        "'I'd love to understand the full scope of the role first. Could you share the budgeted range?'\n\n"
        "Step 3 — Anchor high\n"
        "When you give a number, aim 10-20% above your target — it gives you negotiation room.\n\n"
        "Step 4 — Negotiate the whole package\n"
        "- Signing bonus (often easier to flex than base)\n"
        "- Equity / stock options\n"
        "- Remote flexibility\n"
        "- Extra PTO\n"
        "- Learning & development budget\n\n"
        "Useful script:\n"
        "'I'm very excited about this offer. Based on my research and experience, "
        "I was expecting something closer to [X]. Is there flexibility there?'\n\n"
        "What stage of the salary discussion are you at? I can give more targeted advice."
    ),
    "job_search": (
        "\U0001f50d Job Search Strategy\n\n"
        "Build a Target Company List\n"
        "- Identify 20-30 companies you'd genuinely love to work at\n"
        "- Set up LinkedIn job alerts and follow their careers pages\n"
        "- Apply within 48 hours of a listing going live\n\n"
        "Optimise Your Materials\n"
        "- Tailor your resume and cover letter for each application\n"
        "- Mirror the exact job title and keywords from the listing\n"
        "- Track everything in a spreadsheet: company, role, date, status, contacts\n\n"
        "The Hidden Job Market\n"
        "Up to 70% of roles are never posted publicly. Networking is essential:\n"
        "- Reconnect with alumni, former colleagues, and managers\n"
        "- Book informational interviews (ask about their career path, not for a job)\n\n"
        "Daily Routine\n"
        "- 1 hour: apply to 2-3 tailored roles\n"
        "- 30 mins: network (LinkedIn, emails, calls)\n"
        "- 30 mins: skill development or portfolio work\n\n"
        "What type of role or industry are you targeting?"
    ),
    "skills": (
        "\U0001f4da Skills Development Roadmap\n\n"
        "Identify Your Gaps\n"
        "- Pull 10 job descriptions for your target role\n"
        "- Highlight skills that appear in 7+ of them — those are priorities\n"
        "- Compare honestly against your current skills\n\n"
        "Best Learning Platforms\n"
        "- Technical: Coursera, edX, Udemy, Pluralsight, freeCodeCamp, Codecademy\n"
        "- Business/Soft skills: LinkedIn Learning, MasterClass, Harvard Online\n"
        "- Certifications: Google, AWS, Microsoft, HubSpot, Meta (many free or low-cost)\n\n"
        "Learning Tips\n"
        "- Build projects as you learn — don't just watch videos\n"
        "- Set a weekly learning goal (e.g. 5 hours)\n"
        "- Join study communities on Discord, Reddit, or Slack\n\n"
        "Show Your Skills\n"
        "- Add certifications to LinkedIn and your resume immediately\n"
        "- Write about what you're learning (LinkedIn posts, blog)\n"
        "- Contribute to open source or volunteer for projects\n\n"
        "What skill area are you focused on?"
    ),
    "networking": (
        "\U0001f91d Networking That Actually Works\n\n"
        "Start Warm\n"
        "- Begin with people you already know: ex-colleagues, classmates, professors\n"
        "- Let them know you're open to opportunities or exploring a new area\n\n"
        "LinkedIn Outreach Formula\n"
        "1. Engage with their content first (like, comment thoughtfully)\n"
        "2. Send a personalised connection request (mention their work or a shared interest)\n"
        "3. After connecting, ask for a 15-minute informational chat — not a job\n\n"
        "Outreach Template:\n"
        "'Hi [Name], I came across your post about [topic] and found it really insightful. "
        "I'm currently [your situation] and would love to learn more about your experience in [their field]. "
        "Would you be open to a quick 15-minute chat? No worries if you're busy — I appreciate your time.'\n\n"
        "Give Before You Take\n"
        "- Share useful articles, make introductions, offer to help\n"
        "- Follow up after conversations with a thank-you and something useful\n\n"
        "Would you like help crafting an outreach message for a specific situation?"
    ),
    "career_change": (
        "\U0001f504 Navigating a Career Change\n\n"
        "Step 1 — Diagnose the Problem\n"
        "Is it the role, the industry, the company, or the type of work? "
        "Getting specific helps you make the right change, not just any change.\n\n"
        "Step 2 — Map Transferable Skills\n"
        "Leadership, communication, data analysis, project management — these cross every industry. "
        "List yours and frame them in your target field's language.\n\n"
        "Step 3 — Bridge the Gap\n"
        "- Take courses or earn certifications in the new field\n"
        "- Do freelance, volunteer, or side projects to build a portfolio\n"
        "- Find adjacent roles that blend your current and target skills\n\n"
        "Step 4 — Rewrite Your Story\n"
        "Your resume and LinkedIn should tell a forward story. Lead with your target, not your past.\n"
        "Example headline: 'Marketing Manager transitioning to UX Design | 6 years storytelling experience'\n\n"
        "Step 5 — Informational Interviews\n"
        "Talk to 10+ people in your target field before applying. "
        "It builds your network and gives you insider language.\n\n"
        "What field are you moving from, and where are you hoping to go?"
    ),
    "remote_work": (
        "\U0001f3e0 Remote Work Tips\n\n"
        "Finding Remote Jobs\n"
        "- Remote-first job boards: Remote.co, We Work Remotely, FlexJobs, Remote OK\n"
        "- Filter LinkedIn and Indeed by 'Remote'\n"
        "- Target companies known to be remote-friendly (GitLab, Automattic, Basecamp, etc.)\n\n"
        "Standing Out in Remote Applications\n"
        "- Highlight async communication skills and self-management\n"
        "- Mention any previous remote or distributed team experience\n"
        "- Show familiarity with remote tools: Slack, Notion, Jira, Zoom, Loom\n\n"
        "Remote Work Productivity\n"
        "- Designate a dedicated workspace separate from where you relax\n"
        "- Use time-blocking to structure your day\n"
        "- Over-communicate asynchronously — document decisions in writing\n"
        "- Set hard stop times to protect work-life boundaries\n\n"
        "Are you looking for remote work in a specific field?"
    ),
    "layoff_jobless": (
        "\U0001f499 Getting Back on Your Feet After a Layoff\n\n"
        "First — it's okay to take a breath. Layoffs are stressful and often have nothing to do "
        "with your performance. You're not alone, and this is recoverable.\n\n"
        "Immediate Steps (Week 1)\n"
        "- File for unemployment benefits if eligible — do this right away\n"
        "- Update your LinkedIn to 'Open to Work' (recruiter-only option is available)\n"
        "- Reach out to your network — let people know you're looking\n"
        "- Update your resume while everything is fresh\n\n"
        "Job Search Strategy\n"
        "- Treat the search like a job: set daily goals and hours\n"
        "- Prioritise warm leads (referrals) over cold applications\n"
        "- If asked why you left: 'My role was eliminated in a company-wide restructuring'\n\n"
        "Stay Positive\n"
        "- Keep a routine: wake up at the same time, exercise, socialise\n"
        "- Celebrate small wins: a response, an interview, a new connection\n"
        "- Use this time to level up skills or explore what you really want next\n\n"
        "What's your field, and how long have you been searching? I can give more specific help."
    ),
    "linkedin": (
        "\U0001f517 LinkedIn Profile Optimisation\n\n"
        "Headline (most important field)\n"
        "Don't just write your job title. Write value:\n"
        "Good: 'Senior Software Engineer | Python & AWS | Building scalable fintech systems'\n\n"
        "About Section\n"
        "- First 3 lines show before 'see more' — make them count\n"
        "- Write in first person, conversationally\n"
        "- Include: who you are, what you do, what makes you different, call to action\n\n"
        "Experience Section\n"
        "- Use bullet points with the same STAR-style format as your resume\n"
        "- Quantify everything you can\n\n"
        "Skills & Endorsements\n"
        "- Add 5-10 skills that match your target job titles\n"
        "- Ask colleagues for endorsements — they often reciprocate when asked\n\n"
        "Settings\n"
        "- Turn on 'Open to Work' (recruiter-only or public)\n"
        "- Add your profile to relevant LinkedIn newsletters and groups\n\n"
        "Would you like help writing your headline or About section?"
    ),
    "cover_letter": (
        "\U0001f4dd Writing a Standout Cover Letter\n\n"
        "Structure (3-4 paragraphs, under 400 words)\n\n"
        "Paragraph 1 — The Hook\n"
        "Open with something specific — why this company, this role.\n"
        "Avoid: 'I am writing to apply for...'\n"
        "Better: 'When I saw [Company]'s recent push into [area], I knew this role was exactly where I want to be.'\n\n"
        "Paragraph 2 — Your Value\n"
        "Pick 1-2 achievements most relevant to the role. Show, don't tell.\n\n"
        "Paragraph 3 — Why Them\n"
        "Demonstrate research. Mention their product, values, or recent news. "
        "This shows genuine interest and separates you from generic applicants.\n\n"
        "Paragraph 4 — The Close\n"
        "Express enthusiasm, invite a conversation, and thank them.\n\n"
        "Key Rules\n"
        "- Address it to a specific person where possible\n"
        "- Never copy-paste the same letter — tailor it every time\n"
        "- Match the tone of the company (formal vs casual)\n\n"
        "Would you like help drafting a cover letter for a specific role?"
    ),
    "general": (
        "I'm here to support your career journey! \U0001f3af\n\n"
        "I can help with:\n\n"
        "Resume & CV | Cover Letters | Interview Prep\n"
        "Salary Negotiation | Job Search | LinkedIn\n"
        "Skills Development | Networking\n"
        "Career Change | Remote Work | After a Layoff\n\n"
        "Try asking something like:\n"
        "- 'How do I improve my resume?'\n"
        "- 'What should I say in a salary negotiation?'\n"
        "- 'Help me prepare for a behavioural interview'\n"
        "- 'I was just laid off — what do I do first?'"
    ),
    "clarification": (
        "I want to make sure I give you the most useful advice.\n\n"
        "Could you tell me a bit more? For example:\n"
        "- What's your current role or industry?\n"
        "- What specific challenge are you facing?\n"
        "- What outcome are you hoping for?\n\n"
        "The more detail you share, the better I can help!"
    ),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitise(text: str) -> str:
    return html.unescape(text[:MAX_MESSAGE_LENGTH]).strip()


def _extract_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z]{2,}", text.lower())
    return [t for t in tokens if t not in STOP_WORDS]


def _detect_intent(text: str) -> tuple[str, float]:
    text_lower = text.lower()
    keywords   = _extract_keywords(text_lower)

    # 1. Regex first
    for intent, cfg in INTENTS.items():
        for pattern in cfg["patterns"]:
            if re.search(pattern, text_lower):
                return intent, cfg["confidence"]

    # 2. Keyword weighted scoring
    best_intent, best_score = "general", 0
    for intent, cfg in INTENTS.items():
        score = sum(cfg["keywords"].get(kw, 0) for kw in keywords)
        if score > best_score:
            best_score  = score
            best_intent = intent

    if best_score >= 2:
        return best_intent, min(0.5 + best_score * 0.05, 0.85)

    return "general", 0.40


def _is_follow_up(session: ChatSession, new_intent: str) -> bool:
    last_bot = (
        session.messages.filter(message_type='bot').order_by('-timestamp').first()
    )
    return bool(last_bot and last_bot.intent == new_intent)


def _rate_limit_exceeded(user) -> bool:
    window_start = timezone.now() - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
    count = (
        ChatMessage.objects
                   .filter(session__user=user, message_type='user', timestamp__gte=window_start)
                   .count()
    )
    return count >= RATE_LIMIT_MESSAGES


def _auto_title(message: str) -> str:
    title = message[:60]
    if len(message) > 60:
        cut = title.rfind(' ')
        title = (title[:cut] if cut > 20 else title) + '\u2026'
    return title


def _find_matching_faq(user_message: str) -> Optional[FAQ]:
    user_lower = user_message.lower()
    keywords   = _extract_keywords(user_message)
    if not keywords:
        return None

    q_filter = Q()
    for kw in keywords:
        q_filter |= Q(keywords__icontains=kw) | Q(question__icontains=kw)

    faqs      = FAQ.objects.filter(is_active=True).filter(q_filter)
    best, high = None, 0

    for faq in faqs:
        faq_kws       = faq.get_keywords_list()
        keyword_hits  = sum(1 for kw in faq_kws if kw in user_lower)
        question_hits = sum(1 for kw in keywords if kw in faq.question.lower())
        score         = (keyword_hits * 3) + question_hits
        if score > high:
            high, best = score, faq

    return best if high > 0 else None


# ---------------------------------------------------------------------------
# Bot engine
# ---------------------------------------------------------------------------

def generate_bot_response(
    user_message: str,
    session: ChatSession,
    user,
) -> tuple[str, str, float]:
    """
    Returns (response_text, intent, confidence).
    Priority: FAQ DB match > intent response > clarification > fallback.
    """
    # 1. FAQ match — highest specificity
    faq = _find_matching_faq(user_message)
    if faq:
        FAQ.objects.filter(pk=faq.pk).update(views_count=faq.views_count + 1)
        return faq.answer, 'faq', 0.95

    # 2. Intent detection
    intent, confidence = _detect_intent(user_message)

    # 3. If still general and user is repeating vague messages, ask to clarify
    if intent == 'general' and _is_follow_up(session, 'general'):
        return RESPONSES['clarification'], 'clarification', 0.60

    return RESPONSES.get(intent, RESPONSES['general']), intent, confidence


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required(login_url='login')
def chat(request, session_id=None):
    """Main chat. Supports regular POST and AJAX POST."""

    if session_id:
        session = get_object_or_404(ChatSession, pk=session_id, user=request.user)
    else:
        session = ChatSession.objects.create(user=request.user)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'redirect': f'/chat/{session.pk}/'})
        return redirect('chat_detail', session_id=session.pk)

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        # Rate limit
        if _rate_limit_exceeded(request.user):
            err = 'You are sending messages too quickly. Please wait a moment.'
            if is_ajax:
                return JsonResponse({'success': False, 'error': err}, status=429)
            messages.error(request, err)
            return redirect('chat_detail', session_id=session.pk)

        # Validate
        user_message = _sanitise(request.POST.get('content', ''))
        if not user_message:
            err = 'Please enter a message before sending.'
            if is_ajax:
                return JsonResponse({'success': False, 'error': err}, status=400)
            messages.error(request, err)
            return redirect('chat_detail', session_id=session.pk)

        # Auto-title on first message
        if session.title == 'New Chat':
            session.title = _auto_title(user_message)
            session.save(update_fields=['title'])

        # Persist user message
        user_msg_obj = ChatMessage.objects.create(
            session=session,
            message_type='user',
            content=user_message,
        )

        # Generate response
        try:
            bot_text, intent, confidence = generate_bot_response(
                user_message, session, request.user
            )
        except Exception:
            logger.exception("Bot response error for session %s", session.pk)
            bot_text, intent, confidence = (
                "I ran into an issue. Please try again in a moment.",
                'error', 0.0,
            )

        bot_msg_obj = ChatMessage.objects.create(
            session=session,
            message_type='bot',
            content=bot_text,
            intent=intent,
            confidence_score=confidence,
        )

        session.updated_at = timezone.now()
        session.save(update_fields=['updated_at'])

        if is_ajax:
            return JsonResponse({
                'success': True,
                'user_message': {
                    'id': user_msg_obj.pk,
                    'content': user_message,
                    'timestamp': user_msg_obj.timestamp.strftime('%I:%M %p'),
                },
                'bot_message': {
                    'id': bot_msg_obj.pk,
                    'content': bot_text,
                    'intent': intent,
                    'confidence': round(confidence, 2),
                    'timestamp': bot_msg_obj.timestamp.strftime('%I:%M %p'),
                },
                'session_title': session.title,
            })

        return redirect('chat_detail', session_id=session.pk)

    # GET
    form            = ChatMessageForm()
    messages_list   = session.messages.all()
    recent_sessions = (
        ChatSession.objects
                   .filter(user=request.user)
                   .only('id', 'title', 'updated_at')[:10]
    )
    return render(request, 'chatbot/chat.html', {
        'session': session,
        'messages': messages_list,
        'form': form,
        'recent_sessions': recent_sessions,
        'current_session_id': session.id,
    })


@login_required(login_url='login')
@require_http_methods(["GET"])
def chat_list(request):
    sessions = (
        ChatSession.objects
                   .filter(user=request.user)
                   .annotate(message_count=Count('messages'))
    )
    return render(request, 'chatbot/chat_list.html', {'sessions': sessions})


@login_required(login_url='login')
@require_http_methods(["POST"])
def delete_chat_session(request, session_id):
    session = get_object_or_404(ChatSession, pk=session_id, user=request.user)
    session.delete()
    messages.success(request, 'Chat session deleted.')
    return redirect('chat_list')


@login_required(login_url='login')
@require_http_methods(["POST"])
def rename_chat_session(request, session_id):
    session = get_object_or_404(ChatSession, pk=session_id, user=request.user)
    title   = (request.POST.get('title') or '').strip()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if title:
        session.title = title[:200]
        session.save(update_fields=['title'])
        if is_ajax:
            return JsonResponse({'success': True, 'title': session.title})
        messages.success(request, 'Session renamed.')
    else:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Title cannot be empty.'}, status=400)
        messages.error(request, 'Title cannot be empty.')

    return redirect('chat_detail', session_id=session.pk)


@require_http_methods(["GET"])
def faq(request):
    search = request.GET.get('search', '').strip()
    if search:
        faqs = (
            FAQ.objects
               .filter(
                   Q(question__icontains=search) |
                   Q(answer__icontains=search) |
                   Q(keywords__icontains=search),
                   is_active=True,
               )
               .order_by('-views_count')
        )
        return render(request, 'chatbot/faq_search.html', {
            'faqs': faqs, 'search_query': search,
        })

    categories = FAQCategory.objects.prefetch_related(
        Prefetch('faqs', queryset=FAQ.objects.filter(is_active=True).order_by('-views_count'))
    )
    return render(request, 'chatbot/faq.html', {'categories': categories})


@require_http_methods(["GET"])
def faq_detail(request, pk):
    faq_obj = get_object_or_404(FAQ, pk=pk, is_active=True)
    FAQ.objects.filter(pk=pk).update(views_count=faq_obj.views_count + 1)
    related = (
        FAQ.objects.filter(category=faq_obj.category, is_active=True)
                   .exclude(pk=pk).order_by('-views_count')[:5]
    )
    return render(request, 'chatbot/faq_detail.html', {'faq': faq_obj, 'related_faqs': related})


@require_http_methods(["GET"])
def career_tips(request):
    tips     = CareerTip.objects.all()
    category = request.GET.get('category', '').strip()
    if category:
        tips = tips.filter(category=category)
    return render(request, 'chatbot/career_tips.html', {
        'tips': tips,
        'featured_tips': tips.filter(featured=True)[:3],
        'category_filter': category,
        'categories': CareerTip.CATEGORY_CHOICES,
    })


@require_http_methods(["GET"])
def career_tip_detail(request, pk):
    tip = get_object_or_404(CareerTip, pk=pk)
    CareerTip.objects.filter(pk=pk).update(views_count=tip.views_count + 1)
    related = CareerTip.objects.filter(category=tip.category).exclude(pk=pk).order_by('-views_count')[:4]
    return render(request, 'chatbot/career_tip_detail.html', {'tip': tip, 'related_tips': related})


@login_required(login_url='login')
@require_http_methods(["POST"])
def submit_feedback(request, message_id):
    msg_obj = get_object_or_404(
        ChatMessage.objects.select_related('session'),
        pk=message_id, message_type='bot', session__user=request.user,
    )
    form = UserFeedbackForm(request.POST)
    if form.is_valid():
        UserFeedback.objects.update_or_create(
            user=request.user, message=msg_obj,
            defaults={
                'rating':  form.cleaned_data['rating'],
                'comment': form.cleaned_data.get('comment') or '',
            },
        )
        return JsonResponse({'success': True, 'message': 'Thank you for your feedback!'})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


# ---------------------------------------------------------------------------
# Analytics dashboard
# ---------------------------------------------------------------------------

@login_required(login_url='login')
@require_http_methods(["GET"])
def user_analytics(request):
    """Personal analytics page for the current user."""
    user = request.user

    total_sessions = ChatSession.objects.filter(user=user).count()
    total_messages = ChatMessage.objects.filter(session__user=user, message_type='user').count()

    bot_messages   = ChatMessage.objects.filter(session__user=user, message_type='bot')
    avg_confidence = bot_messages.aggregate(avg=Avg('confidence_score'))['avg'] or 0

    intent_breakdown = (
        bot_messages.exclude(intent__isnull=True).exclude(intent='')
                    .values('intent').annotate(count=Count('id')).order_by('-count')[:8]
    )

    feedback    = UserFeedback.objects.filter(user=user)
    avg_rating  = feedback.aggregate(avg=Avg('rating'))['avg'] or 0

    return render(request, 'chatbot/analytics.html', {
        'total_sessions':   total_sessions,
        'total_messages':   total_messages,
        'avg_confidence':   round(avg_confidence * 100, 1),
        'intent_breakdown': intent_breakdown,
        'avg_rating':       round(avg_rating, 1),
        'total_feedback':   feedback.count(),
    })