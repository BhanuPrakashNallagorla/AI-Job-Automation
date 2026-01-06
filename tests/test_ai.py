"""
Tests for AI module components.
Uses mocked responses to avoid API costs.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_jd_analyzer_caching(sample_jd):
    """Test that JD analysis is cached."""
    from ai.jd_analyzer import JDAnalyzer
    
    # Mock the Anthropic client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"required_skills": {"technical": ["Python"]}, "experience": {"years_min": 5}}')]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    
    with patch.object(JDAnalyzer, '__init__', lambda x, api_key=None: None):
        analyzer = JDAnalyzer()
        analyzer.client = MagicMock()
        analyzer.client.messages.create = MagicMock(return_value=mock_response)
        analyzer.model = "claude-sonnet-4-20250514"
        analyzer.logger = MagicMock()
        
        # First call
        result1 = await analyzer.analyze(sample_jd, use_cache=True)
        assert "required_skills" in result1
        
        # Second call should use cache
        result2 = await analyzer.analyze(sample_jd, use_cache=True)
        assert result1 == result2


def test_match_scorer_quick_score():
    """Test quick scoring without API call."""
    from ai.match_scorer import MatchScorer
    
    scorer = MatchScorer()
    
    candidate_skills = {"python", "django", "postgresql", "docker"}
    
    job_analysis = {
        "required_skills": {
            "technical": ["Python", "Django"],
            "tools": ["PostgreSQL", "Redis"],
        },
        "preferred_skills": {
            "technical": ["Machine Learning"],
            "tools": ["Kubernetes"],
        }
    }
    
    score = scorer.quick_score(candidate_skills, job_analysis)
    
    assert 0 <= score <= 100
    # Should score relatively high since candidate has most required skills
    assert score >= 50


def test_match_scorer_levels():
    """Test match level classification."""
    from ai.match_scorer import MatchScorer
    
    scorer = MatchScorer()
    
    assert scorer.get_match_level(90) == "excellent"
    assert scorer.get_match_level(75) == "good"
    assert scorer.get_match_level(60) == "moderate"
    assert scorer.get_match_level(45) == "weak"
    assert scorer.get_match_level(30) == "poor"


def test_match_scorer_recommendation():
    """Test recommendation based on score."""
    from ai.match_scorer import MatchScorer
    
    scorer = MatchScorer()
    
    assert scorer.get_recommendation(85) == "hire"
    assert scorer.get_recommendation(70) == "interview"
    assert scorer.get_recommendation(55) == "maybe"
    assert scorer.get_recommendation(40) == "pass"


def test_tailoring_levels():
    """Test that tailoring levels are defined correctly."""
    from ai.resume_tailor import TailoringLevel, ResumeTailor
    
    assert TailoringLevel.CONSERVATIVE == "conservative"
    assert TailoringLevel.MODERATE == "moderate"
    assert TailoringLevel.AGGRESSIVE == "aggressive"
    
    # Check prompts exist for all levels
    tailor = ResumeTailor.__new__(ResumeTailor)
    assert TailoringLevel.CONSERVATIVE in tailor.TAILORING_PROMPTS
    assert TailoringLevel.MODERATE in tailor.TAILORING_PROMPTS
    assert TailoringLevel.AGGRESSIVE in tailor.TAILORING_PROMPTS


def test_cover_letter_tones():
    """Test cover letter tone options."""
    from ai.cover_letter_generator import ToneStyle, CoverLetterGenerator
    
    assert ToneStyle.PROFESSIONAL == "professional"
    assert ToneStyle.CONVERSATIONAL == "conversational"
    assert ToneStyle.ENTHUSIASTIC == "enthusiastic"
    
    # Check tone guidelines exist
    generator = CoverLetterGenerator.__new__(CoverLetterGenerator)
    assert ToneStyle.PROFESSIONAL in generator.TONE_GUIDELINES
    assert ToneStyle.CONVERSATIONAL in generator.TONE_GUIDELINES
    assert ToneStyle.ENTHUSIASTIC in generator.TONE_GUIDELINES
