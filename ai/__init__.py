"""
AI module initialization.
"""
from ai.gemini_client import GeminiClient, get_gemini_client
from ai.jd_analyzer import JDAnalyzer, analyze_job_description
from ai.resume_tailor import ResumeTailor, tailor_resume, TailoringLevel
from ai.cover_letter_generator import CoverLetterGenerator, generate_cover_letter, ToneStyle
from ai.match_scorer import MatchScorer, calculate_match_score

__all__ = [
    # Gemini Client
    "GeminiClient",
    "get_gemini_client",
    # JD Analyzer
    "JDAnalyzer",
    "analyze_job_description",
    # Resume Tailor
    "ResumeTailor",
    "tailor_resume",
    "TailoringLevel",
    # Cover Letter
    "CoverLetterGenerator",
    "generate_cover_letter",
    "ToneStyle",
    # Match Scorer
    "MatchScorer",
    "calculate_match_score",
]
