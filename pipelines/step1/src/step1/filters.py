"""Filtering logic for RCT articles."""
import re
from typing import List
from .model import Article
from .config import settings


def is_rct_article(article: Article) -> bool:
    """Check if an article is a randomized controlled trial.
    
    Args:
        article: Article to check
        
    Returns:
        True if article is an RCT, False otherwise
    """
    # Check if it's explicitly labeled as a randomized controlled trial
    if any(term.lower() in article.title.lower() for term in 
           ["randomized", "randomised", "randomized controlled trial", "rct"]):
        return True
    
    # Check abstract for RCT keywords
    abstract_lower = article.abstract.lower()
    rct_keywords = [
        "randomized", "randomised", "randomly assigned", 
        "controlled trial", "clinical trial", "double blind",
        "placebo", "allocation", "intervention group"
    ]
    
    rct_count = sum(1 for keyword in rct_keywords if keyword in abstract_lower)
    return rct_count >= 2


def is_human_study(article: Article) -> bool:
    """Check if an article is a human study.
    
    Args:
        article: Article to check
        
    Returns:
        True if article is a human study, False otherwise
    """
    # Check if explicitly marked as human/clinical study
    human_keywords = ["human", "clinical", "patient", "volunteer", "randomized controlled trial"]
    mesh_human = any(term.lower() in " ".join(article.mesh_terms).lower() 
                     for term in human_keywords)
    
    # Check if animal study
    animal_keywords = ["mouse", "rat", "animal", "mice", "rodent"]
    mesh_animal = any(term.lower() in " ".join(article.mesh_terms).lower() 
                      for term in animal_keywords)
    
    # If animal study terms are present but no human terms, likely not human study
    if mesh_animal and not mesh_human:
        return False
        
    # Check title and abstract for human-related terms
    text = (article.title + " " + article.abstract).lower()
    has_human_terms = any(term in text for term in human_keywords)
    has_animal_terms = any(term in text for term in animal_keywords)
    
    # If animal terms but no human terms, likely not human study
    if has_animal_terms and not has_human_terms:
        return False
        
    # If we have human terms or no animal terms, assume it's human
    # This is more inclusive since many clinical trials don't explicitly mention "human"
    return has_human_terms or not has_animal_terms


def is_anesthesia_related(article: Article) -> bool:
    """Check if an article is related to anesthesia/perioperative medicine.
    
    Args:
        article: Article to check
        
    Returns:
        True if article is anesthesia/perioperative related, False otherwise
    """
    anesthesia_keywords = [
        "anesthesia", "anaesthesia", "anesthesiology", "perioperative", 
        "peri-operative", "regional anesthesia", "airway", "intubation", 
        "nerve block", "analgesia", "surgery", "operative", "surgical"
    ]
    
    # Check MeSH terms
    mesh_match = any(any(keyword in term.lower() for keyword in anesthesia_keywords) 
                     for term in article.mesh_terms)
    
    # Check title and abstract
    text = (article.title + " " + article.abstract).lower()
    text_match = any(keyword in text for keyword in anesthesia_keywords)
    
    return mesh_match or text_match


def is_preferred_language(article: Article) -> bool:
    """Check if article is in a preferred language.
    
    Args:
        article: Article to check
        
    Returns:
        True if article is in preferred language, False otherwise
    """
    preferred_languages = ["english", "french"]
    return article.language.lower() in preferred_languages


def is_protocol_or_letter(article: Article) -> bool:
    """Check if article is a protocol or letter without results.
    
    Args:
        article: Article to check
        
    Returns:
        True if article is a protocol or letter, False otherwise
    """
    # Check if protocols are allowed
    if settings.allow_protocols:
        return False
    
    # Check for protocol/letter keywords
    protocol_keywords = [
        "protocol", "study protocol", "letter", "editorial", 
        "commentary", "correspondence", "discussion"
    ]
    
    text = (article.title + " " + article.abstract).lower()
    return any(keyword in text for keyword in protocol_keywords)


def is_pediatric_only(article: Article) -> bool:
    """Check if article is pediatric-only.
    
    Args:
        article: Article to check
        
    Returns:
        True if article is pediatric-only, False otherwise
    """
    # If pediatric studies are allowed, return False
    if settings.allow_pediatric:
        return False
    
    # Check for pediatric keywords
    pediatric_keywords = [
        "pediatric", "paediatric", "child", "infant", "neonate", 
        "newborn", "adolescent", "children", "kids", "under 18"
    ]
    
    text = (article.title + " " + article.abstract).lower()
    return any(keyword in text for keyword in pediatric_keywords)


def deduplicate_articles(articles: List[Article]) -> List[Article]:
    """Remove duplicate articles based on DOI or PMID.
    
    Args:
        articles: List of articles to deduplicate
        
    Returns:
        List of unique articles
    """
    seen_dois = set()
    seen_pmids = set()
    unique_articles = []
    
    for article in articles:
        # Use DOI if available, otherwise use PMID
        identifier = article.doi if article.doi else article.pmid
        
        if identifier and identifier not in seen_dois and identifier not in seen_pmids:
            if article.doi:
                seen_dois.add(article.doi)
            if article.pmid:
                seen_pmids.add(article.pmid)
            unique_articles.append(article)
    
    return unique_articles


def filter_articles(articles: List[Article]) -> List[Article]:
    """Apply all filters to a list of articles.
    
    Args:
        articles: List of articles to filter
        
    Returns:
        List of filtered articles
    """
    filtered_articles = []
    
    for article in articles:
        # Apply all filters
        if (is_rct_article(article) and 
            is_human_study(article) and 
            is_anesthesia_related(article) and 
            is_preferred_language(article) and 
            not is_protocol_or_letter(article) and 
            not is_pediatric_only(article)):
            filtered_articles.append(article)
    
    # Deduplicate articles
    unique_articles = deduplicate_articles(filtered_articles)
    
    return unique_articles