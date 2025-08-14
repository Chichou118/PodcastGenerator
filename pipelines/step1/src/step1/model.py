"""Data models for RCT articles and trials."""
from typing import List, Optional
from pydantic import BaseModel


class Article(BaseModel):
    """Unified article model for RCT metadata."""
    
    # Basic metadata
    title: str
    abstract: str
    authors: List[str]
    journal: str
    year: int
    pub_date: str
    pmid: str
    doi: Optional[str] = None
    url: str
    language: str
    
    # Additional metadata
    mesh_terms: List[str]
    trial_design: str
    sample_size: Optional[int] = None
    multicenter: Optional[bool] = None
    
    # Study details
    intervention: str
    comparator: str
    primary_outcome: str
    effect_summary: Optional[str] = None
    
    # Scoring and selection
    score: Optional[float] = None
    rationale: Optional[str] = None


class ArticleList(BaseModel):
    """Container for a list of articles."""
    articles: List[Article]