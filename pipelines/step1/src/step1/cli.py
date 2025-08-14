"""CLI entrypoint for the RCT podcast pipeline."""
import typer
from typing import Optional
from pathlib import Path
import json
from datetime import datetime
import logging
from .config import settings
from .clients.pubmed import pubmed_client
from .filters import filter_articles
from .scoring import score_articles, sort_articles_by_score
from .select import select_top_article, widen_search_if_needed, record_selected_article
from .model import Article

app = typer.Typer()
logger = logging.getLogger(__name__)


def setup_logging():
    """Set up basic logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def save_articles(articles: list, filename: str):
    """Save articles to a JSON file.
    
    Args:
        articles: List of articles to save
        filename: Name of file to save to
    """
    # Convert Article objects to dictionaries
    articles_dict = []
    for article in articles:
        if isinstance(article, Article):
            articles_dict.append(article.dict())
        else:
            articles_dict.append(article)
    
    filepath = Path("data") / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(articles_dict, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(articles)} articles to {filepath}")


def generate_markdown_card(article: Article, rationale: str):
    """Generate a markdown card for the selected article.
    
    Args:
        article: Selected article
        rationale: Selection rationale
    """
    # Create markdown content
    content = f"""---
title: "{article.title}"
journal: "{article.journal}"
date: "{article.pub_date}"
doi: "{article.doi or ''}"
pmid: "{article.pmid}"
score: {article.score}
rationale: "{rationale}"
---
**Design:** randomized (parallel/crossover), (multi)center, sample size ~{article.sample_size or 'N/A'}.  
**Population:** ...  
**Intervention vs comparator:** {article.intervention} vs {article.comparator}  
**Primary outcome:** {article.primary_outcome}  
**Key result:** {article.effect_summary or '...'}  
**Why it matters (peri-op):** 2–3 bullet points for clinicians.  
**Caveats:** 2–3 bullet points (bias, generalizability, power).
"""

    # Save to file
    filepath = Path("out") / "rct_card.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    
    logger.info(f"Generated markdown card at {filepath}")


def create_pubmed_query(extra_query: Optional[str] = None) -> str:
    """Create the PubMed search query.
    
    Args:
        extra_query: Additional query terms to include
        
    Returns:
        PubMed search query string
    """
    base_query = (
        "(anesthesia OR anaesthesia OR anesthesiology OR perioperative OR "
        "peri-operative OR \"perioperative care\" OR \"regional anesthesia\" OR "
        "airway OR intubation OR \"nerve block\" OR analgesia) AND "
        "(randomized OR randomised)"
    )
    
    if extra_query:
        return f"({base_query}) AND ({extra_query})"
    
    return base_query


@app.command()
def fetch(
    days: int = typer.Option(
        None, 
        "--days", 
        help="Number of recent days to search (default: RECENT_DAYS env var or 180)"
    ),
    max_results: int = typer.Option(
        None,
        "--max-results",
        help="Maximum number of results to fetch (default: MAX_RESULTS env var or 200)"
    ),
    allow_protocols: bool = typer.Option(
        None,
        "--allow-protocols/--no-allow-protocols",
        help="Allow protocol papers (default: no)"
    ),
    allow_pediatric: bool = typer.Option(
        None,
        "--allow-pediatric/--no-allow-pediatric",
        help="Allow pediatric studies (default: yes)"
    ),
    extra_query: Optional[str] = typer.Option(
        None,
        "--extra-query",
        help="Additional query terms to add to the search"
    ),
    allow_repeat: bool = typer.Option(
        False,
        "--allow-repeat",
        help="Allow selection of previously selected articles"
    )
):
    """Fetch and process RCT articles from PubMed."""
    setup_logging()
    
    # Use environment variables or defaults if not provided
    if days is None:
        days = settings.recent_days
    if max_results is None:
        max_results = settings.max_results
    if allow_protocols is None:
        allow_protocols = settings.allow_protocols
    if allow_pediatric is None:
        allow_pediatric = settings.allow_pediatric
    
    logger.info(f"Starting RCT discovery with {days} days window")
    
    # Create search query
    query = create_pubmed_query(extra_query)
    logger.info(f"Search query: {query}")
    
    # Search for articles
    pmids = pubmed_client.search_articles(query, max_results, days)
    
    if not pmids:
        if widen_search_if_needed([]):
            logger.info("No articles found, widening search to 365 days")
            pmids = pubmed_client.search_articles(query, max_results, 365)
            if not pmids:
                typer.echo("No RCTs found even with widened search window.")
                raise typer.Exit(code=1)
        else:
            typer.echo("No RCTs found in the specified time window.")
            raise typer.Exit(code=1)
    
    # Fetch article details
    articles_data = pubmed_client.fetch_article_details(pmids)
    
    if not articles_data:
        typer.echo("Failed to fetch article details.")
        raise typer.Exit(code=1)
    
    # Convert to Article objects
    articles = [Article(**article_data) for article_data in articles_data]
    logger.info(f"Fetched {len(articles)} articles")
    
    # Filter articles
    filtered_articles = filter_articles(articles)
    logger.info(f"Filtered to {len(filtered_articles)} RCT articles")
    
    if not filtered_articles:
        if widen_search_if_needed([]):
            logger.info("No filtered articles, widening search to 365 days")
            pmids = pubmed_client.search_articles(query, max_results, 365)
            if pmids:
                articles_data = pubmed_client.fetch_article_details(pmids)
                articles = [Article(**article_data) for article_data in articles_data]
                filtered_articles = filter_articles(articles)
        
        if not filtered_articles:
            typer.echo("No articles passed filters.")
            raise typer.Exit(code=1)
    
    # Score articles
    scored_articles = score_articles(filtered_articles)
    sorted_articles = sort_articles_by_score(scored_articles)
    
    # Generate timestamp for filenames
    timestamp = datetime.now().strftime("%Y-%m-%d")
    
    # Save all candidates
    candidates_filename = f"candidates_{timestamp}.json"
    save_articles(sorted_articles, candidates_filename)
    
    # Select top article, avoiding previously selected ones unless explicitly allowed
    selection_result = select_top_article(sorted_articles, avoid_history=not allow_repeat)
    if not selection_result:
        typer.echo("No articles available for selection.")
        raise typer.Exit(code=1)
    
    selected_article, selection_rationale = selection_result
    
    # Record the selected article in history
    record_selected_article(selected_article, selection_rationale)
    
    # Save selected article
    selected_filename = f"selected_{timestamp}.json"
    save_articles([selected_article], selected_filename)
    
    # Generate markdown card
    generate_markdown_card(selected_article, selection_rationale)
    
    # Print summary
    typer.echo(f"Selected: {selected_article.title} (Score: {selected_article.score})")
    typer.echo(f"Saved candidates to data/{candidates_filename}")
    typer.echo(f"Saved selection to data/{selected_filename}")
    typer.echo("Generated markdown card at out/rct_card.md")


if __name__ == "__main__":
    app()