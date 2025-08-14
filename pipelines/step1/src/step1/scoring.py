"""Scoring logic for ranking RCT articles by interestingness."""
import re
from typing import List, Tuple
from .model import Article


# High-quality journals in anesthesiology/perioperative medicine
HIGH_QUALITY_JOURNALS = [
    "Anesthesiology",
    "British Journal of Anaesthesia",
    "Anesthesia and Analgesia",
    "Anaesthesiology",
    "European Journal of Anaesthesiology",
    "Journal of Clinical Anesthesia",
    "Anesthesia & Analgesia",
    "Anaesthesia",
    "Acta Anaesthesiologica Scandinavica",
    "Canadian Journal of Anesthesia",
    "Regional Anesthesia and Pain Medicine",
    "Pain Medicine",
    "Journal of Anesthesia",
    "Anaesthesia, Pain & Intensive Care",
    "Middle East Journal of Anesthesiology",
    "Korean Journal of Anesthesiology",
    "Saudi Journal of Anaesthesia",
    "Indian Journal of Anaesthesia",
    "Journal of Anaesthesiology Clinical Pharmacology",
    "A & A Case Reports"
]


# Patient-centered outcomes
PATIENT_CENTERED_OUTCOMES = [
    "pain", "mortality", "morbidity", "complications", "recovery", 
    "discharge", "quality of life", "functional outcome", "patient satisfaction",
    "length of stay", "readmission", "adverse events", "safety"
]


# Clinically actionable interventions
CLINICALLY_ACTIONABLE_INTERVENTIONS = [
    "airway", "intubation", "ventilation", "regional", "block", 
    "analgesia", "anesthetic", "sedation", "hemodynamic", "fluid",
    "blood pressure", "hypotension", "hypertension", "cardiac output"
]


def score_article(article: Article) -> Tuple[float, str]:
    """Score an article based on various heuristics.
    
    Args:
        article: Article to score
        
    Returns:
        Tuple of (score, rationale)
    """
    score = 0.0
    rationale_parts = []
    
    # Sample size scoring
    if article.sample_size:
        if article.sample_size >= 500:
            score += 3.0
            rationale_parts.append("large sample size (>500)")
        elif article.sample_size >= 100:
            score += 1.5
            rationale_parts.append("moderate sample size (>100)")
    
    # Multicenter study
    if article.multicenter:
        score += 1.0
        rationale_parts.append("multicenter study")
    
    # Patient-centered primary outcome
    primary_outcome_lower = article.primary_outcome.lower()
    if any(outcome in primary_outcome_lower for outcome in PATIENT_CENTERED_OUTCOMES):
        score += 1.5
        rationale_parts.append("patient-centered outcome")
    
    # Clinically actionable intervention
    intervention_lower = article.intervention.lower()
    if any(intervention in intervention_lower for intervention in CLINICALLY_ACTIONABLE_INTERVENTIONS):
        score += 1.5
        rationale_parts.append("clinically actionable intervention")
    
    # High-quality venue
    if article.journal in HIGH_QUALITY_JOURNALS:
        score += 2.0
        rationale_parts.append("high-quality journal")
    
    # Clear effect direction
    if article.effect_summary and len(article.effect_summary.strip()) > 0:
        # Check if effect summary contains numerical values or clear direction
        if re.search(r'\d+\.?\d*%', article.effect_summary) or \
           re.search(r'\d+\.?\d*\s*(increase|decrease|higher|lower|better|worse)', 
                    article.effect_summary, re.IGNORECASE):
            score += 1.0
            rationale_parts.append("quantified effect")
    
    # Combine rationale
    rationale = "; ".join(rationale_parts) if rationale_parts else "no standout features"
    
    return score, rationale


def score_articles(articles: List[Article]) -> List[Article]:
    """Score a list of articles and add scores to them.
    
    Args:
        articles: List of articles to score
        
    Returns:
        List of articles with scores added
    """
    scored_articles = []
    
    for article in articles:
        score, rationale = score_article(article)
        article.score = score
        article.rationale = rationale
        scored_articles.append(article)
    
    return scored_articles


def sort_articles_by_score(articles: List[Article]) -> List[Article]:
    """Sort articles by score in descending order.
    
    Args:
        articles: List of articles to sort
        
    Returns:
        List of articles sorted by score (highest first)
    """
    return sorted(articles, key=lambda x: x.score or 0.0, reverse=True)