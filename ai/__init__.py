"""
AI module initialization.
"""
from ai.jd_analyzer import JDAnalyzer, analyze_job_description
from ai.resume_tailor import ResumeTailor, tailor_resume
from ai.cover_letter_generator import CoverLetterGenerator, generate_cover_letter
from ai.match_scorer import MatchScorer, calculate_match_score

__all__ = [
    "JDAnalyzer",
    "analyze_job_description",
    "ResumeTailor",
    "tailor_resume",
    "CoverLetterGenerator",
    "generate_cover_letter",
    "MatchScorer",
    "calculate_match_score",
]
