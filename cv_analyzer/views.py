# cv_analyzer/views.py
"""
CV Analyzer Views — Using Your Analyzer Modules
Simple, clean, direct integration with your analyzer.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
import json
import time
import logging

from .models import CVAnalysis, CVTemplate
from .forms import CVUploadForm, CVComparisonForm, CVFilterForm

logger = logging.getLogger(__name__)


# ============================================================================
# UPLOAD & ANALYZE CV
# ============================================================================

@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def upload_cv_analysis(request):
    """Upload and analyze CV using your analyzer modules."""

    # Import analyzer helpers lazily so a broken optional module does not
    # prevent the rest of the Django project from starting.
    from analyzer.parser import extract_text_from_bytes
    from analyzer.skills import get_skill_extractor
    from analyzer.scorer import calculate_score
    from analyzer.gap import detect_skill_gaps
    from analyzer.suggestions import generate_suggestions
    from analyzer.similarity import get_similarity_analyzer
    from analyzer.utilities import (
        check_section_completeness,
        extract_contact_info,
        calculate_experience_years,
    )
    
    if request.method == 'POST':
        form = CVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                start_time = time.time()
                
                # Create record
                cv_analysis = form.save(commit=False)
                cv_analysis.user = request.user
                cv_analysis.save()
                logger.info(f"Created CV analysis: {cv_analysis.id}")
                
                # ── FIX: seek to 0 before reading ──────────────────────────
                # Django's form validation may have already read the file,
                # leaving the cursor at the end. Seeking back ensures we
                # read the full file content.
                uploaded_file = request.FILES['cv_file']
                uploaded_file.seek(0)
                file_bytes = uploaded_file.read()
                filename = uploaded_file.name
                logger.info(f"File: '{filename}', size={len(file_bytes)} bytes")

                if len(file_bytes) == 0:
                    messages.error(request, 'Uploaded file is empty. Please upload a valid PDF or DOCX.')
                    cv_analysis.delete()
                    return redirect('upload_cv_analysis')
                # ────────────────────────────────────────────────────────────
                
                # ===== YOUR ANALYZER MODULES =====
                
                # 1. Extract text
                try:
                    text = extract_text_from_bytes(file_bytes, filename)
                    if not text or len(text.strip()) < 50:
                        messages.error(request, 'Could not extract text from file. Please ensure it is a text-based (not scanned) PDF.')
                        cv_analysis.delete()
                        return redirect('upload_cv_analysis')
                    logger.info(f"Extracted {len(text)} chars")
                except Exception as e:
                    logger.error(f"Extraction failed: {e}")
                    messages.error(request, f'Text extraction error: {e}')
                    cv_analysis.delete()
                    return redirect('upload_cv_analysis')
                
                # 2. Extract skills (your module)
                skills = {'technical': [], 'soft': []}
                try:
                    extractor = get_skill_extractor()
                    skills = extractor.extract(text)
                    logger.info(f"Skills: {len(skills['technical'])} technical, {len(skills['soft'])} soft")
                except Exception as e:
                    logger.warning(f"Skill extraction failed: {e}")
                
                # 3. Score CV (your module)
                try:
                    score_result = calculate_score(text, skills)
                    overall_score = score_result['score']
                    breakdown = score_result['breakdown']
                    logger.info(f"CV scored: {overall_score}/100")
                except Exception as e:
                    logger.error(f"Scoring failed: {e}")
                    messages.error(request, f'Scoring error: {e}')
                    cv_analysis.delete()
                    return redirect('upload_cv_analysis')
                
                # 4. Detect gaps (your module)
                gaps = {}
                try:
                    gaps = detect_skill_gaps(skills)
                except Exception as e:
                    logger.warning(f"Gap detection failed: {e}")
                
                # 5. Generate suggestions (your module)
                suggestions = []
                try:
                    suggestions = generate_suggestions(score_result, skills, gaps)
                    logger.info(f"Generated {len(suggestions)} suggestions")
                except Exception as e:
                    logger.warning(f"Suggestion generation failed: {e}")
                
                # 6. Job similarity (your module - optional)
                similarity = 0
                job_description = request.POST.get('job_description', '').strip()
                if job_description and len(job_description) >= 20:
                    try:
                        analyzer = get_similarity_analyzer()
                        similarity = analyzer.calculate_similarity(text, job_description)
                        logger.info(f"Similarity: {similarity}")
                    except Exception as e:
                        logger.warning(f"Similarity failed: {e}")
                
                # 7. Section completeness (your module)
                sections = {}
                try:
                    sections = check_section_completeness(text)
                except Exception as e:
                    logger.warning(f"Section check failed: {e}")
                
                # 8. Contact & experience (your module)
                contact_info = {}
                experience_years = 0
                try:
                    contact_info = extract_contact_info(text)
                    experience_years = calculate_experience_years(text)
                except Exception as e:
                    logger.warning(f"Contact extraction failed: {e}")
                
                # ===== STORE IN DATABASE =====
                
                cv_analysis.overall_score = int(overall_score)
                cv_analysis.format_score = int(breakdown.get('formatting_score', 0))
                cv_analysis.content_score = int(breakdown.get('completeness_score', 0))
                cv_analysis.keyword_score = int(breakdown.get('keywords_score', 0))
                cv_analysis.readability_score = int(breakdown.get('skill_density_score', 0))
                
                # Feedback messages
                cv_analysis.format_feedback = f"Format score: {cv_analysis.format_score}/100"
                cv_analysis.content_feedback = f"Content score: {cv_analysis.content_score}/100"
                cv_analysis.keyword_feedback = f"Keyword score: {cv_analysis.keyword_score}/100"
                cv_analysis.readability_feedback = f"Readability score: {cv_analysis.readability_score}/100"
                
                # Store extracted data
                cv_analysis.extracted_skills = json.dumps(skills)
                cv_analysis.extracted_education = json.dumps(sections)
                
                # Store all recommendations
                cv_analysis.recommendations = json.dumps({
                    'breakdown': breakdown,
                    'suggestions': suggestions,
                    'gaps': gaps,
                    'similarity': similarity,
                    'contact_info': contact_info,
                    'experience_years': experience_years,
                })
                
                # Overall message
                if overall_score >= 80:
                    overall_msg = "Excellent! Your CV is well-structured."
                elif overall_score >= 60:
                    overall_msg = "Good foundation! Check suggestions to improve."
                else:
                    overall_msg = "Room for improvement. Follow the suggestions."
                
                cv_analysis.overall_feedback = f"Score: {overall_score}/100. {overall_msg}"
                cv_analysis.is_analyzed = True
                cv_analysis.analysis_time_taken = time.time() - start_time
                cv_analysis.save()
                
                logger.info(f"Analysis complete in {cv_analysis.analysis_time_taken:.2f}s")
                messages.success(request, f'✅ CV analyzed! Score: {overall_score}/100')
                return redirect('cv_analysis_detail', pk=cv_analysis.pk)
                
            except Exception as e:
                logger.exception(f"Error: {e}")
                messages.error(request, f'Unexpected error: {e}')
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


# ============================================================================
# LIST ANALYSES
# ============================================================================

@login_required(login_url='login')
@require_http_methods(["GET"])
def cv_analysis_list(request):
    """List all CV analyses for user."""
    analyses = CVAnalysis.objects.filter(user=request.user).order_by('-created_at')
    
    form = CVFilterForm(request.GET)
    if form.is_valid():
        score_min = form.cleaned_data.get('score_min')
        score_max = form.cleaned_data.get('score_max')
        sort_by = form.cleaned_data.get('sort_by')
        
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
    
    return render(request, 'cv_analyzer/cv_analysis_list.html', {
        'analyses': analyses,
        'form': form,
        'total_analyses': analyses.count(),
    })


# ============================================================================
# DETAIL VIEW
# ============================================================================

@login_required(login_url='login')
@require_http_methods(["GET"])
def cv_analysis_detail(request, pk):
    """Display CV analysis results."""
    analysis = get_object_or_404(CVAnalysis, pk=pk, user=request.user)
    
    skills = {}
    suggestions = []
    gaps = {}
    contact_info = {}
    experience_years = 0
    sections = {}
    completeness = 0
    similarity = 0

    try:
        skills = json.loads(analysis.extracted_skills) if analysis.extracted_skills else {'technical': [], 'soft': []}
        recs = json.loads(analysis.recommendations) if analysis.recommendations else {}
        suggestions_list = recs.get('suggestions', [])
        gaps = recs.get('gaps', {})
        contact_info = recs.get('contact_info', {})
        experience_years = recs.get('experience_years', 0)
        similarity = recs.get('similarity', 0)

        # Group suggestions by priority
        suggestions = {'High': [], 'Medium': [], 'Low': []}
        for s in suggestions_list:
            priority = s.get('priority', 'Low')
            if priority in suggestions:
                suggestions[priority].append(s)

        # Section completeness
        sections_data = json.loads(analysis.extracted_education) if analysis.extracted_education else {}
        sections = sections_data.get('sections', {})
        completeness = sections_data.get('completeness_percentage', 0)
    except Exception as e:
        logger.warning(f"Detail view data parsing failed: {e}")
    
    return render(request, 'cv_analyzer/cv_analysis_detail.html', {
        'analysis': analysis,
        'skills': skills,
        'suggestions': suggestions,
        'gaps': gaps,
        'contact_info': contact_info,
        'experience_years': experience_years,
        'similarity': similarity,
        'sections': sections,
        'completeness': completeness,
    })


# ============================================================================
# COMPARISON
# ============================================================================

@login_required(login_url='login')
@require_http_methods(["GET"])
def cv_comparison(request):
    """Compare two CVs."""
    user_qs = CVAnalysis.objects.filter(user=request.user, is_analyzed=True)
    
    form = CVComparisonForm()
    form.fields['cv_analysis_1'].queryset = user_qs
    form.fields['cv_analysis_2'].queryset = user_qs
    
    comparison_data = None
    cv1_id = request.GET.get('cv_analysis_1') or request.GET.get('cv1')
    cv2_id = request.GET.get('cv_analysis_2') or request.GET.get('cv2')
    
    if cv1_id and cv2_id:
        try:
            cv1 = get_object_or_404(CVAnalysis, pk=cv1_id, user=request.user)
            cv2 = get_object_or_404(CVAnalysis, pk=cv2_id, user=request.user)
            
            comparison_data = {
                'cv1': cv1,
                'cv2': cv2,
                'overall_diff': cv1.overall_score - cv2.overall_score,
                'format_diff': cv1.format_score - cv2.format_score,
                'content_diff': cv1.content_score - cv2.content_score,
                'keyword_diff': cv1.keyword_score - cv2.keyword_score,
                'readability_diff': cv1.readability_score - cv2.readability_score,
                'better_cv': 'First CV' if cv1.overall_score > cv2.overall_score else 'Second CV' if cv2.overall_score > cv1.overall_score else 'Tied',
            }
        except Exception:
            messages.error(request, 'CVs not found.')
    
    return render(request, 'cv_analyzer/cv_comparison.html', {
        'form': form,
        'comparison_data': comparison_data,
    })


# ============================================================================
# DELETE
# ============================================================================

@login_required(login_url='login')
@require_http_methods(["POST"])
def delete_cv_analysis(request, pk):
    """Delete a CV analysis."""
    analysis = get_object_or_404(CVAnalysis, pk=pk, user=request.user)
    analysis.delete()
    messages.success(request, '✅ CV deleted successfully!')
    return redirect('cv_analysis_list')


# ============================================================================
# TEMPLATES
# ============================================================================

@login_required(login_url='login')
@require_http_methods(["GET"])
def cv_templates(request):
    """View CV templates."""
    templates = CVTemplate.objects.filter(is_active=True).order_by('category')
    return render(request, 'cv_analyzer/cv_templates.html', {
        'templates': templates,
        'total_templates': templates.count(),
    })