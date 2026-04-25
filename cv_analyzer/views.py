# cv_analyzer/views.py
"""
CV Analyzer Views — merged with v2.1 Analyzer Modules.

FIXES applied in this merge:
  FIX-A  analyzer.suggestions  — was 'suggerstions' (typo). Rename the file.
  FIX-B  analyzer.utilities    — was 'utilites' (typo). Rename the file.
  FIX-C  cv_comparison view    — form POSTs 'cv_analysis_1'/'cv_analysis_2'
                                  but old code read GET params 'cv1'/'cv2'.
                                  Now supports both GET params AND form fields.
  FIX-D  cv_analysis_detail    — detail template uses analysis.content_feedback,
                                  .keyword_feedback, .readability_feedback as
                                  plain text. views.py now populates these with
                                  human-readable strings (not raw JSON).
  FIX-E  format_feedback field — was overwritten with full JSON breakdown dict.
                                  breakdown JSON is now stored in a dedicated
                                  helper field so format_feedback stays readable.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
import time
import logging

from .models import CVAnalysis, CVFeedback, CVTemplate, KeywordDatabase
from .forms import CVUploadForm, CVComparisonForm, CVFilterForm

# ── Analyzer modules (v2.1) ──────────────────────────────────────────────────
from analyzer.parser import extract_text_from_bytes, extract_sections
from analyzer.skills import get_skill_extractor
from analyzer.scorer import calculate_score
from analyzer.gap import detect_skill_gaps
from analyzer.suggestions import generate_suggestions          # FIX-A (renamed file)
from analyzer.similarity import get_similarity_analyzer
from analyzer.utilities import (                               # FIX-B (renamed file)
    validate_file,
    get_file_size_mb,
    check_section_completeness,
    extract_contact_info,
    calculate_experience_years,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_format_feedback(breakdown: dict) -> str:
    """
    Convert the scorer breakdown dict into a human-readable string
    for the format_feedback field (displayed by the detail template).
    """
    fmt = breakdown.get("formatting_score", 0)
    if fmt >= 75:
        return (
            f"Good formatting ({fmt}/100). Your CV has clear structure, "
            "bullet points, and contact details are present."
        )
    elif fmt >= 50:
        return (
            f"Moderate formatting ({fmt}/100). Consider adding bullet points "
            "and ensuring your contact details are prominent."
        )
    else:
        return (
            f"Formatting needs work ({fmt}/100). Add clear section headers, "
            "bullet points, and make sure email / phone appear at the top."
        )


def _build_content_feedback(breakdown: dict) -> str:
    """Human-readable content/completeness feedback."""
    score = breakdown.get("completeness_score", 0)
    if score >= 75:
        return (
            f"Strong content completeness ({score}/100). All major CV sections "
            "are present and well-populated."
        )
    elif score >= 50:
        return (
            f"Decent content ({score}/100). A few sections could be expanded — "
            "add more detail to experience and education."
        )
    else:
        return (
            f"Content is thin ({score}/100). Make sure you have dedicated sections "
            "for Summary, Experience, Education, Skills, and Projects."
        )


def _build_keyword_feedback(breakdown: dict) -> str:
    """Human-readable keyword feedback."""
    score = breakdown.get("keywords_score", 0)
    if score >= 75:
        return (
            f"Excellent keyword coverage ({score}/100). Strong use of action verbs "
            "and industry-specific terms."
        )
    elif score >= 50:
        return (
            f"Average keyword density ({score}/100). Add more action verbs like "
            "'led', 'built', 'optimized' and quantify your achievements."
        )
    else:
        return (
            f"Low keyword density ({score}/100). Use industry-specific terms, "
            "action verbs, and include quantified results (e.g. 'increased sales by 30%')."
        )


def _build_readability_feedback(breakdown: dict) -> str:
    """Human-readable skill-density / readability feedback."""
    score = breakdown.get("skill_density_score", 0)
    if score >= 75:
        return (
            f"Great skill density ({score}/100). Your CV showcases a broad, "
            "relevant skill set."
        )
    elif score >= 50:
        return (
            f"Moderate skill density ({score}/100). Consider listing more technical "
            "and soft skills explicitly."
        )
    else:
        return (
            f"Skill density is low ({score}/100). Add a dedicated Skills section "
            "listing both technical tools and soft skills."
        )


# ─────────────────────────────────────────────────────────────────────────────
# UPLOAD & ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def upload_cv_analysis(request):
    """
    Upload and analyze CV using integrated analyzer modules (v2.1).

    WORKFLOW:
      1  Validate & save uploaded file
      2  Extract text (Windows-safe temp-dir approach)
      3  Extract skills (keyword + spaCy + HF BERT sliding-window)
      4  Score CV (4 SRS-compliant weighted dimensions)
      5  Detect skill gaps
      6  Generate suggestions
      7  Optional job-description similarity
      8  Section completeness check
      9  Extract contact info & experience years
      10 Persist all results → redirect to detail view
    """
    if request.method == 'POST':
        form = CVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                start_time = time.time()

                # ── 1. Save record ────────────────────────────────────────────
                cv_analysis = form.save(commit=False)
                cv_analysis.user = request.user
                cv_analysis.save()
                logger.info(f"Created CV analysis record: {cv_analysis.id}")

                # ── 2. Extract text ───────────────────────────────────────────
                try:
                    file_bytes = request.FILES['cv_file'].read()
                    text = extract_text_from_bytes(
                        file_bytes,
                        request.FILES['cv_file'].name
                    )
                    logger.info(f"Extracted {len(text)} chars from CV")
                except Exception as e:
                    logger.error(f"Text extraction failed: {e}", exc_info=True)
                    messages.error(request, f'Could not extract text from file: {e}')
                    cv_analysis.delete()
                    return redirect('upload_cv_analysis')

                if not text or len(text.strip()) < 50:
                    messages.error(
                        request,
                        'Could not extract meaningful text. '
                        'Please ensure your CV is not corrupted or image-only.'
                    )
                    cv_analysis.delete()
                    return redirect('upload_cv_analysis')

                # ── 3. Skill extraction ───────────────────────────────────────
                skills = {'technical': [], 'soft': []}
                try:
                    skill_extractor = get_skill_extractor()
                    skills = skill_extractor.extract(text)
                    logger.info(
                        f"Skills: {len(skills['technical'])} technical, "
                        f"{len(skills['soft'])} soft"
                    )
                except Exception as e:
                    logger.warning(f"Skill extraction failed (non-fatal): {e}")

                # ── 4. Scoring ────────────────────────────────────────────────
                try:
                    score_result = calculate_score(text, skills)
                    overall_score = score_result['score']
                    breakdown = score_result['breakdown']
                    logger.info(f"CV scored: {overall_score}/100")
                except Exception as e:
                    logger.error(f"Scoring failed: {e}", exc_info=True)
                    messages.error(request, f'Scoring error: {e}')
                    cv_analysis.delete()
                    return redirect('upload_cv_analysis')

                # ── 5. Gap analysis ───────────────────────────────────────────
                gaps = {
                    'missing_skills': [],
                    'high_priority_skills': [],
                    'emerging_missing_skills': [],
                    'user_has_high_demand_count': 0,
                    'total_high_demand': 0,
                    'coverage_percentage': 0.0,
                }
                try:
                    gaps = detect_skill_gaps(skills)
                except Exception as e:
                    logger.warning(f"Gap detection failed (non-fatal): {e}")

                # ── 6. Suggestions ────────────────────────────────────────────
                suggestions = []
                try:
                    suggestions = generate_suggestions(score_result, skills, gaps)
                    logger.info(f"Generated {len(suggestions)} suggestions")
                except Exception as e:
                    logger.warning(f"Suggestion generation failed (non-fatal): {e}")

                # ── 7. Similarity (optional) ──────────────────────────────────
                similarity = 0
                job_description = request.POST.get('job_description', '').strip()
                if job_description and len(job_description) >= 20:
                    try:
                        analyzer = get_similarity_analyzer()
                        similarity = analyzer.calculate_similarity(text, job_description)
                        logger.info(f"Similarity: {similarity}")
                    except Exception as e:
                        logger.warning(f"Similarity failed (non-fatal): {e}")

                # ── 8. Section completeness ───────────────────────────────────
                sections = {
                    'sections': {},
                    'completeness_percentage': 0,
                    'completed_count': 0,
                    'total_expected': 0,
                }
                try:
                    sections = check_section_completeness(text)
                except Exception as e:
                    logger.warning(f"Section check failed (non-fatal): {e}")

                # ── 9. Contact & experience ───────────────────────────────────
                contact_info = {}
                experience_years = 0
                try:
                    contact_info = extract_contact_info(text)
                    experience_years = calculate_experience_years(text)
                except Exception as e:
                    logger.warning(f"Contact/experience extraction failed: {e}")

                # ── 10. Persist ───────────────────────────────────────────────
                cv_analysis.overall_score    = int(overall_score)
                cv_analysis.format_score     = int(breakdown.get('formatting_score',    0))
                cv_analysis.content_score    = int(breakdown.get('completeness_score',  0))
                cv_analysis.keyword_score    = int(breakdown.get('keywords_score',      0))
                cv_analysis.readability_score = int(breakdown.get('skill_density_score', 0))

                # FIX-D: populate the four *_feedback text fields with human-readable strings
                cv_analysis.format_feedback      = _build_format_feedback(breakdown)
                cv_analysis.content_feedback     = _build_content_feedback(breakdown)
                cv_analysis.keyword_feedback     = _build_keyword_feedback(breakdown)
                cv_analysis.readability_feedback = _build_readability_feedback(breakdown)

                # Store extracted data
                cv_analysis.extracted_skills    = json.dumps(skills)
                cv_analysis.extracted_education = json.dumps({
                    'sections_found':  sections.get('sections', {}),
                    'completeness':    sections.get('completeness_percentage', 0),
                })

                # Store the full breakdown + everything else in recommendations
                cv_analysis.recommendations = json.dumps({
                    'breakdown':        breakdown,        # full scorer breakdown (FIX-E)
                    'suggestions':      suggestions,
                    'gaps':             gaps,
                    'similarity':       similarity,
                    'sections':         sections,
                    'contact_info':     contact_info,
                    'experience_years': experience_years,
                })

                # Overall feedback message
                if overall_score >= 80:
                    overall_msg = (
                        "Excellent! Your CV is well-structured and professional. "
                        "You're in great shape for applications."
                    )
                elif overall_score >= 60:
                    overall_msg = (
                        "Good foundation! Your CV has solid elements. "
                        "Review the suggestions below to push it to the next level."
                    )
                else:
                    overall_msg = (
                        "Room for improvement. Follow the actionable suggestions "
                        "to enhance your CV and improve your chances."
                    )

                cv_analysis.overall_feedback    = f"Your CV scored {overall_score}/100. {overall_msg}"
                cv_analysis.is_analyzed         = True
                cv_analysis.analysis_time_taken = time.time() - start_time
                cv_analysis.save()

                logger.info(f"Analysis done in {cv_analysis.analysis_time_taken:.2f}s")
                messages.success(request, f'✅ CV analyzed! Score: {overall_score}/100')
                return redirect('cv_analysis_detail', pk=cv_analysis.pk)

            except Exception as e:
                logger.exception(f"Unexpected error in upload_cv_analysis: {e}")
                messages.error(request, f'Unexpected error: {e}. Please try again.')
                if 'cv_analysis' in locals():
                    cv_analysis.delete()
                return redirect('upload_cv_analysis')
    else:
        form = CVUploadForm()

    return render(request, 'cv_analyzer/upload_cv_analysis.html', {
        'form': form,
        'max_file_size': '5 MB',
        'supported_formats': 'PDF, DOCX',
    })


# ─────────────────────────────────────────────────────────────────────────────
# LIST
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url='login')
@require_http_methods(["GET"])
def cv_analysis_list(request):
    """List all CV analyses for the current user with optional filters."""
    analyses = CVAnalysis.objects.filter(user=request.user).order_by('-created_at')

    form = CVFilterForm(request.GET)
    if form.is_valid():
        score_min = form.cleaned_data.get('score_min')
        score_max = form.cleaned_data.get('score_max')
        sort_by   = form.cleaned_data.get('sort_by')

        if score_min is not None:
            analyses = analyses.filter(overall_score__gte=score_min)
        if score_max is not None:
            analyses = analyses.filter(overall_score__lte=score_max)

        if sort_by == 'highest_score':
            analyses = analyses.order_by('-overall_score')
        elif sort_by == 'lowest_score':
            analyses = analyses.order_by('overall_score')
        elif sort_by == 'oldest':
            analyses = analyses.order_by('created_at')

    for analysis in analyses:
        analysis.score_rating = analysis.get_score_rating()

    return render(request, 'cv_analyzer/cv_analysis_list.html', {
        'analyses':        analyses,
        'form':            form,
        'total_analyses':  analyses.count(),
    })


# ─────────────────────────────────────────────────────────────────────────────
# DETAIL
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url='login')
@require_http_methods(["GET"])
def cv_analysis_detail(request, pk):
    """
    Display detailed CV analysis with all insights, scores, and suggestions.

    FIX-D: The four *_feedback fields now hold human-readable strings
    (set in upload_cv_analysis), so the template renders them directly.
    The full breakdown dict is read from recommendations['breakdown'].
    """
    analysis = get_object_or_404(CVAnalysis, pk=pk, user=request.user)

    recommendations = {}
    suggestions      = []
    gaps             = {}
    similarity       = 0
    sections         = {}
    contact_info     = {}
    experience_years = 0
    breakdown        = {}

    try:
        recommendations  = json.loads(analysis.recommendations) if analysis.recommendations else {}
        suggestions      = recommendations.get('suggestions', [])
        gaps             = recommendations.get('gaps', {})
        similarity       = recommendations.get('similarity', 0)
        sections         = recommendations.get('sections', {})
        contact_info     = recommendations.get('contact_info', {})
        experience_years = recommendations.get('experience_years', 0)
        breakdown        = recommendations.get('breakdown', {})   # FIX-E: stored here now
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"Failed to parse recommendations for analysis {pk}")

    try:
        skills = (
            json.loads(analysis.extracted_skills)
            if analysis.extracted_skills
            else {'technical': [], 'soft': []}
        )
    except (json.JSONDecodeError, TypeError):
        skills = {'technical': [], 'soft': []}

    suggestions_grouped = {
        'High':   [s for s in suggestions if s.get('priority') == 'High'],
        'Medium': [s for s in suggestions if s.get('priority') == 'Medium'],
        'Low':    [s for s in suggestions if s.get('priority') == 'Low'],
    }

    return render(request, 'cv_analyzer/cv_analysis_detail.html', {
        'analysis':        analysis,
        'score_percentage': analysis.overall_score,
        'breakdown':        breakdown,
        'skills':           skills,
        'suggestions':      suggestions_grouped,
        'gaps':             gaps,
        'similarity':       int(similarity) if similarity else 0,
        'sections':         sections.get('sections', {}),
        'completeness':     sections.get('completeness_percentage', 0),
        'score_rating':     analysis.get_score_rating(),
        'contact_info':     contact_info,
        'experience_years': experience_years,
    })


# ─────────────────────────────────────────────────────────────────────────────
# COMPARISON  (FIX-C)
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url='login')
@require_http_methods(["GET"])
def cv_comparison(request):
    """
    Compare two CVs side-by-side.

    FIX-C: The comparison form (CVComparisonForm) uses field names
    'cv_analysis_1' and 'cv_analysis_2', but the old code read GET
    params 'cv1' and 'cv2'.  This view now tries BOTH so that:
      - The select form works ('cv_analysis_1' / 'cv_analysis_2')
      - Deep-links from the detail page still work ('cv1' only, for pre-selection)
    """
    user_qs = CVAnalysis.objects.filter(user=request.user, is_analyzed=True)

    form = CVComparisonForm()
    form.fields['cv_analysis_1'].queryset = user_qs
    form.fields['cv_analysis_2'].queryset = user_qs

    comparison_data = None

    # Resolve IDs from either naming convention
    cv1_id = request.GET.get('cv_analysis_1') or request.GET.get('cv1')
    cv2_id = request.GET.get('cv_analysis_2') or request.GET.get('cv2')

    if cv1_id and cv2_id:
        try:
            cv1 = get_object_or_404(CVAnalysis, pk=cv1_id, user=request.user)
            cv2 = get_object_or_404(CVAnalysis, pk=cv2_id, user=request.user)

            try:
                skills1 = json.loads(cv1.extracted_skills) if cv1.extracted_skills else {'technical': [], 'soft': []}
                skills2 = json.loads(cv2.extracted_skills) if cv2.extracted_skills else {'technical': [], 'soft': []}
            except (json.JSONDecodeError, TypeError):
                skills1 = skills2 = {'technical': [], 'soft': []}

            comparison_data = {
                'cv1':              cv1,
                'cv2':              cv2,
                'overall_diff':     cv1.overall_score    - cv2.overall_score,
                'format_diff':      cv1.format_score     - cv2.format_score,
                'content_diff':     cv1.content_score    - cv2.content_score,
                'keyword_diff':     cv1.keyword_score    - cv2.keyword_score,
                'readability_diff': cv1.readability_score - cv2.readability_score,
                'tech_skills_diff': (
                    len(skills1.get('technical', [])) -
                    len(skills2.get('technical', []))
                ),
                'soft_skills_diff': (
                    len(skills1.get('soft', [])) -
                    len(skills2.get('soft', []))
                ),
                'better_cv': (
                    'First CV'  if cv1.overall_score > cv2.overall_score else
                    'Second CV' if cv2.overall_score > cv1.overall_score else
                    'Tied'
                ),
            }
        except Exception:
            messages.error(request, 'One or both CVs not found.')

    return render(request, 'cv_analyzer/cv_comparison.html', {
        'form':            form,
        'comparison_data': comparison_data,
    })


# ─────────────────────────────────────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url='login')
@require_http_methods(["POST"])
def delete_cv_analysis(request, pk):
    """Delete a CV analysis owned by the current user."""
    analysis = get_object_or_404(CVAnalysis, pk=pk, user=request.user)
    analysis.delete()
    logger.info(f"User {request.user.username} deleted CV analysis {pk}")
    messages.success(request, '✅ CV analysis deleted successfully!')
    return redirect('cv_analysis_list')


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATES
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url='login')
@require_http_methods(["GET"])
def cv_templates(request):
    """View available CV templates for download."""
    templates = CVTemplate.objects.filter(is_active=True).order_by('category')
    return render(request, 'cv_analyzer/cv_templates.html', {
        'templates':        templates,
        'total_templates':  templates.count(),
    })


# ─────────────────────────────────────────────────────────────────────────────
# INSIGHTS DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url='login')
@require_http_methods(["GET"])
def cv_insights_dashboard(request):
    """Dashboard showing CV insights, trends, and statistics."""
    analyses = CVAnalysis.objects.filter(
        user=request.user, is_analyzed=True
    ).order_by('-created_at')

    if not analyses.exists():
        return redirect('upload_cv_analysis')

    latest_analysis = analyses.first()
    total_analyses  = analyses.count()
    avg_score       = round(sum(a.overall_score for a in analyses) / total_analyses, 1)
    highest_score   = max(a.overall_score for a in analyses)
    lowest_score    = min(a.overall_score for a in analyses)

    top_suggestions = []
    gaps = {}
    try:
        recs            = json.loads(latest_analysis.recommendations) if latest_analysis.recommendations else {}
        top_suggestions = recs.get('suggestions', [])[:3]
        gaps            = recs.get('gaps', {})
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse latest recommendations for dashboard")

    return render(request, 'cv_analyzer/cv_insights_dashboard.html', {
        'latest_analysis':  latest_analysis,
        'total_analyses':   total_analyses,
        'avg_score':        avg_score,
        'highest_score':    highest_score,
        'lowest_score':     lowest_score,
        'score_improvement': highest_score - lowest_score if total_analyses > 1 else 0,
        'top_suggestions':  top_suggestions,
        'gaps':             gaps,
    })
