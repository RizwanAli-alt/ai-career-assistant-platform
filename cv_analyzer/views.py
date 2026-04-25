# cv_analyzer/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils import timezone
import json
import time
import logging

from .models import CVAnalysis, CVFeedback, CVTemplate, KeywordDatabase
from .forms import CVUploadForm, CVComparisonForm, CVFilterForm

# Import Streamlit analyzer modules
from analyzer.parser import extract_text_from_bytes
from analyzer.skills import get_skill_extractor
from analyzer.scorer import calculate_score
from analyzer.gap import detect_skill_gaps
from analyzer.suggestions import generate_suggestions
from analyzer.similarity import get_similarity_analyzer
from analyzer.utilities import validate_file, get_file_size_mb, check_section_completeness

logger = logging.getLogger(__name__)


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def upload_cv_analysis(request):
    """
    Upload and analyze CV using Streamlit analyzer modules
    
    NEW FEATURES (v2.1 Integration):
    - Uses analyzer.parser for text extraction (PDF, DOCX)
    - Uses analyzer.skills with caching for skill extraction
    - Uses analyzer.scorer for SRS-compliant scoring
    - Uses analyzer.gap for skill gap detection
    - Uses analyzer.suggestions for actionable improvements
    - Uses analyzer.similarity for job description matching
    """
    if request.method == 'POST':
        form = CVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                start_time = time.time()
                
                # Create CV analysis record
                cv_analysis = form.save(commit=False)
                cv_analysis.user = request.user
                cv_analysis.save()
                
                # Extract text using Streamlit parser (FIX #6: Windows-safe)
                try:
                    file_bytes = request.FILES['cv_file'].read()
                    text = extract_text_from_bytes(
                        file_bytes, 
                        request.FILES['cv_file'].name
                    )
                except Exception as e:
                    logger.error(f"Text extraction failed: {e}")
                    messages.error(request, f'Could not extract text: {str(e)}')
                    cv_analysis.delete()
                    return redirect('upload_cv_analysis')
                
                if not text or len(text.strip()) < 50:
                    messages.error(request, 'Could not extract meaningful text from CV')
                    cv_analysis.delete()
                    return redirect('upload_cv_analysis')
                
                # ── SKILL EXTRACTION (FIX #2: uses cached singleton) ──────────────
                try:
                    skill_extractor = get_skill_extractor()
                    skills = skill_extractor.extract(text)
                    logger.info(f"Extracted {len(skills['technical'])} technical, {len(skills['soft'])} soft skills")
                except Exception as e:
                    logger.error(f"Skill extraction failed: {e}")
                    skills = {'technical': [], 'soft': []}
                
                # ── CV SCORING (SRS CV-FR-02: 4-dimensional weighted score) ─────────
                try:
                    score_result = calculate_score(text, skills)
                    overall_score = score_result['score']
                    breakdown = score_result['breakdown']
                except Exception as e:
                    logger.error(f"CV scoring failed: {e}")
                    messages.error(request, f'Scoring error: {str(e)}')
                    cv_analysis.delete()
                    return redirect('upload_cv_analysis')
                
                # ── SKILL GAP ANALYSIS (detect high-demand + emerging skills) ────────
                try:
                    gaps = detect_skill_gaps(skills)
                except Exception as e:
                    logger.error(f"Gap detection failed: {e}")
                    gaps = {
                        'missing_skills': [],
                        'high_priority_skills': [],
                        'emerging_missing_skills': [],
                        'coverage_percentage': 0
                    }
                
                # ── SUGGESTIONS (actionable, prioritized improvements) ────────────────
                try:
                    suggestions = generate_suggestions(score_result, skills, gaps)
                except Exception as e:
                    logger.error(f"Suggestion generation failed: {e}")
                    suggestions = []
                
                # ── CV-JOB SIMILARITY (optional: if user provided job description) ────
                similarity = 0
                job_description = request.POST.get('job_description', '')
                if job_description and job_description.strip():
                    try:
                        analyzer = get_similarity_analyzer()
                        similarity = analyzer.calculate_similarity(text, job_description)
                    except Exception as e:
                        logger.warning(f"Similarity calculation failed: {e}")
                
                # ── SECTION COMPLETENESS ───────────────────────────────────────────
                try:
                    sections = check_section_completeness(text)
                except Exception as e:
                    logger.warning(f"Section check failed: {e}")
                    sections = {'sections': {}, 'completeness_percentage': 0}
                
                # ── STORE IN DATABASE ──────────────────────────────────────────────
                cv_analysis.overall_score = int(overall_score)
                cv_analysis.format_score = int(breakdown.get('formatting_score', 0))
                cv_analysis.content_score = int(breakdown.get('completeness_score', 0))
                cv_analysis.keyword_score = int(breakdown.get('keywords_score', 0))
                cv_analysis.readability_score = int(breakdown.get('skill_density_score', 0))
                
                # Store JSON data
                cv_analysis.format_feedback = json.dumps(breakdown)
                cv_analysis.extracted_skills = json.dumps(skills)
                cv_analysis.recommendations = json.dumps({
                    'suggestions': suggestions,
                    'gaps': gaps,
                    'similarity': similarity,
                    'sections': sections
                })
                
                # Generate overall feedback message
                if overall_score >= 80:
                    overall_msg = "Excellent! Your CV is well-structured and professional."
                elif overall_score >= 60:
                    overall_msg = "Good foundation! Review suggestions below to improve further."
                else:
                    overall_msg = "Room for improvement. Follow the actionable suggestions to enhance your CV."
                
                cv_analysis.overall_feedback = f"Your CV scored {overall_score}/100. {overall_msg}"
                
                cv_analysis.is_analyzed = True
                cv_analysis.analysis_time_taken = time.time() - start_time
                cv_analysis.save()
                
                messages.success(
                    request, 
                    f'✅ CV analyzed successfully! Score: {overall_score}/100'
                )
                return redirect('cv_analysis_detail', pk=cv_analysis.pk)
                
            except Exception as e:
                logger.exception(f"Upload CV analysis error: {e}")
                messages.error(request, f'Unexpected error: {str(e)}')
                if 'cv_analysis' in locals():
                    cv_analysis.delete()
                return redirect('upload_cv_analysis')
    else:
        form = CVUploadForm()
    
    context = {
        'form': form,
        'max_file_size': '5 MB',
        'supported_formats': 'PDF, DOC, DOCX'
    }
    return render(request, 'cv_analyzer/upload_cv_analysis.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def cv_analysis_list(request):
    """List all CV analyses with filtering and sorting"""
    analyses = CVAnalysis.objects.filter(user=request.user)
    
    form = CVFilterForm(request.GET)
    if form.is_valid():
        if form.cleaned_data.get('score_min'):
            analyses = analyses.filter(overall_score__gte=form.cleaned_data['score_min'])
        if form.cleaned_data.get('score_max'):
            analyses = analyses.filter(overall_score__lte=form.cleaned_data['score_max'])
        
        sort_by = form.cleaned_data.get('sort_by')
        if sort_by == 'highest_score':
            analyses = analyses.order_by('-overall_score')
        elif sort_by == 'lowest_score':
            analyses = analyses.order_by('overall_score')
    
    # Add score rating for template display
    for analysis in analyses:
        analysis.score_rating = analysis.get_score_rating()
    
    context = {
        'analyses': analyses,
        'form': form,
        'total_analyses': analyses.count(),
    }
    return render(request, 'cv_analyzer/cv_analysis_list.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def cv_analysis_detail(request, pk):
    """Display detailed CV analysis with all insights"""
    analysis = get_object_or_404(CVAnalysis, pk=pk, user=request.user)
    
    # Parse stored JSON recommendations
    try:
        recommendations = json.loads(analysis.recommendations) if analysis.recommendations else {}
        suggestions = recommendations.get('suggestions', [])
        gaps = recommendations.get('gaps', {})
        similarity = recommendations.get('similarity', 0)
        sections = recommendations.get('sections', {})
    except json.JSONDecodeError:
        suggestions = []
        gaps = {}
        similarity = 0
        sections = {}
    
    try:
        breakdown = json.loads(analysis.format_feedback) if analysis.format_feedback else {}
        skills = json.loads(analysis.extracted_skills) if analysis.extracted_skills else {'technical': [], 'soft': []}
    except json.JSONDecodeError:
        breakdown = {}
        skills = {'technical': [], 'soft': []}
    
    # Group suggestions by priority
    suggestions_grouped = {
        'High': [s for s in suggestions if s.get('priority') == 'High'],
        'Medium': [s for s in suggestions if s.get('priority') == 'Medium'],
        'Low': [s for s in suggestions if s.get('priority') == 'Low'],
    }
    
    context = {
        'analysis': analysis,
        'score_percentage': analysis.overall_score,
        'breakdown': breakdown,
        'skills': skills,
        'suggestions': suggestions_grouped,
        'gaps': gaps,
        'similarity': similarity,
        'sections': sections.get('sections', {}),
        'completeness': sections.get('completeness_percentage', 0),
        'score_rating': analysis.get_score_rating(),
    }
    return render(request, 'cv_analyzer/cv_analysis_detail.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def cv_comparison(request):
    """Compare two CVs side-by-side"""
    form = CVComparisonForm()
    form.fields['cv_analysis_1'].queryset = CVAnalysis.objects.filter(user=request.user)
    form.fields['cv_analysis_2'].queryset = CVAnalysis.objects.filter(user=request.user)
    
    comparison_data = None
    
    if 'cv1' in request.GET and 'cv2' in request.GET:
        cv1_id = request.GET.get('cv1')
        cv2_id = request.GET.get('cv2')
        
        try:
            cv1 = CVAnalysis.objects.get(pk=cv1_id, user=request.user)
            cv2 = CVAnalysis.objects.get(pk=cv2_id, user=request.user)
            
            # Parse skills
            skills1 = json.loads(cv1.extracted_skills) if cv1.extracted_skills else {'technical': [], 'soft': []}
            skills2 = json.loads(cv2.extracted_skills) if cv2.extracted_skills else {'technical': [], 'soft': []}
            
            comparison_data = {
                'cv1': cv1,
                'cv2': cv2,
                'format_diff': cv1.format_score - cv2.format_score,
                'content_diff': cv1.content_score - cv2.content_score,
                'keyword_diff': cv1.keyword_score - cv2.keyword_score,
                'readability_diff': cv1.readability_score - cv2.readability_score,
                'overall_diff': cv1.overall_score - cv2.overall_score,
                'tech_skills_diff': len(skills1.get('technical', [])) - len(skills2.get('technical', [])),
                'soft_skills_diff': len(skills1.get('soft', [])) - len(skills2.get('soft', [])),
                'better_cv': 'First CV' if cv1.overall_score > cv2.overall_score else ('Second CV' if cv2.overall_score > cv1.overall_score else 'Tied'),
            }
        except CVAnalysis.DoesNotExist:
            messages.error(request, 'One or both CVs not found')
    
    context = {
        'form': form,
        'comparison_data': comparison_data,
    }
    return render(request, 'cv_analyzer/cv_comparison.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def delete_cv_analysis(request, pk):
    """Delete a CV analysis"""
    analysis = get_object_or_404(CVAnalysis, pk=pk, user=request.user)
    filename = analysis.cv_file.name
    analysis.delete()
    messages.success(request, f'CV analysis deleted successfully!')
    return redirect('cv_analysis_list')


@login_required(login_url='login')
@require_http_methods(["GET"])
def cv_templates(request):
    """View available CV templates"""
    templates = CVTemplate.objects.filter(is_active=True)
    
    context = {
        'templates': templates,
        'total_templates': templates.count(),
    }
    return render(request, 'cv_analyzer/cv_templates.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def cv_insights_dashboard(request):
    """Dashboard showing CV insights and trends"""
    analyses = CVAnalysis.objects.filter(user=request.user, is_analyzed=True).order_by('-created_at')
    
    if not analyses.exists():
        return redirect('upload_cv_analysis')
    
    latest_analysis = analyses.first()
    
    # Calculate statistics
    total_analyses = analyses.count()
    avg_score = sum(a.overall_score for a in analyses) / total_analyses if analyses else 0
    highest_score = max((a.overall_score for a in analyses), default=0)
    lowest_score = min((a.overall_score for a in analyses), default=0)
    
    # Parse latest recommendations
    try:
        recommendations = json.loads(latest_analysis.recommendations) if latest_analysis.recommendations else {}
        top_suggestions = recommendations.get('suggestions', [])[:3]
        gaps = recommendations.get('gaps', {})
    except:
        top_suggestions = []
        gaps = {}
    
    context = {
        'latest_analysis': latest_analysis,
        'total_analyses': total_analyses,
        'avg_score': round(avg_score, 1),
        'highest_score': highest_score,
        'lowest_score': lowest_score,
        'score_improvement': highest_score - lowest_score if total_analyses > 1 else 0,
        'top_suggestions': top_suggestions,
        'gaps': gaps,
    }
    return render(request, 'cv_analyzer/cv_insights_dashboard.html', context)