"""Selection logic for choosing the top-ranked RCT article."""
from typing import List, Optional, Tuple
from .model import Article
from .config import settings
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)

# History file path
HISTORY_FILE = Path("data") / "selection_history.json"


def load_selection_history() -> List[dict]:
    """Load the history of previously selected articles.
    
    Returns:
        List of previously selected articles
    """
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load selection history: {e}")
            return []
    return []


def save_selection_history(history: List[dict]) -> None:
    """Save the history of selected articles.
    
    Args:
        history: List of selected articles to save
    """
    try:
        HISTORY_FILE.parent.mkdir(exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save selection history: {e}")


def is_article_previously_selected(article: Article, history: List[dict]) -> bool:
    """Check if an article has been previously selected.
    
    Args:
        article: Article to check
        history: Selection history
        
    Returns:
        True if article was previously selected, False otherwise
    """
    article_identifier = article.doi or article.pmid
    if not article_identifier:
        return False
        
    for entry in history:
        # Check if DOI matches
        if article.doi and entry.get("doi") == article.doi:
            return True
        # Check if PMID matches
        if article.pmid and entry.get("pmid") == article.pmid:
            return True
            
    return False


def select_top_article(articles: List[Article], avoid_history: bool = True) -> Optional[Tuple[Article, str]]:
    """Select the top-ranked article from a list of scored articles.
    
    Args:
        articles: List of scored articles
        avoid_history: Whether to avoid previously selected articles
        
    Returns:
        Tuple of (selected article, selection rationale) or None if no articles
    """
    if not articles:
        return None
    
    # Load selection history if we want to avoid it
    history = load_selection_history() if avoid_history else []
    
    # Sort articles by score
    sorted_articles = sorted(articles, key=lambda x: x.score or 0.0, reverse=True)
    
    # If we're not avoiding history, just return the top article
    if not avoid_history:
        top_article = sorted_articles[0]
        rationale = f"Selected article with highest score ({top_article.score}) based on: {top_article.rationale}"
        logger.info(f"Selected top article: {top_article.title} with score {top_article.score}")
        return top_article, rationale
    
    # Try to find an article that hasn't been previously selected
    for article in sorted_articles:
        if not is_article_previously_selected(article, history):
            top_article = article
            rationale = f"Selected article with highest score ({top_article.score}) based on: {top_article.rationale}"
            logger.info(f"Selected top article: {top_article.title} with score {top_article.score}")
            return top_article, rationale
    
    # If all articles have been previously selected, return the highest scoring one
    # but add a note to the rationale
    top_article = sorted_articles[0]
    rationale = f"Selected article with highest score ({top_article.score}) based on: {top_article.rationale} (Note: This article has been previously selected)"
    logger.info(f"Selected previously selected top article: {top_article.title} with score {top_article.score}")
    return top_article, rationale


def record_selected_article(article: Article, rationale: str) -> None:
    """Record a selected article in the history.
    
    Args:
        article: Selected article
        rationale: Selection rationale
    """
    history = load_selection_history()
    
    # Create entry for the selected article
    entry = {
        "title": article.title,
        "doi": article.doi,
        "pmid": article.pmid,
        "journal": article.journal,
        "date_selected": article.pub_date,
        "score": article.score,
        "rationale": rationale
    }
    
    # Add to history
    history.append(entry)
    
    # Save updated history
    save_selection_history(history)


def widen_search_if_needed(articles: List[Article]) -> bool:
    """Determine if we need to widen the search window.
    
    Args:
        articles: List of articles after filtering
        
    Returns:
        True if search should be widened, False otherwise
    """
    # If we have no candidates and haven't already widened the search
    return len(articles) == 0 and settings.recent_days < 365


def get_selection_rationale(article: Article) -> str:
    """Generate a detailed rationale for the article selection.
    
    Args:
        article: Selected article
        
    Returns:
        Detailed rationale string
    """
    rationale_parts = [
        f"Selected '{article.title}' published in {article.journal} with a score of {article.score}.",
        f"Key factors: {article.rationale}."
    ]
    
    return " ".join(rationale_parts)