"""PubMed E-utilities client for searching and fetching articles."""
import requests
from typing import List, Dict, Optional
from xml.etree import ElementTree as ET
from ..cache import cache_session
from ..config import settings
import time
import logging

logger = logging.getLogger(__name__)


class PubMedClient:
    """Client for interacting with PubMed E-utilities API."""
    
    def __init__(self):
        """Initialize the PubMed client with cache session."""
        self.session = cache_session
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    def search_articles(
        self, 
        query: str, 
        max_results: int = 200,
        recent_days: int = 180
    ) -> List[str]:
        """Search for articles using ESearch.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            recent_days: Number of recent days to search
            
        Returns:
            List of PubMed IDs
        """
        # Add date restriction to query
        date_query = f"({query}) AND (\"{recent_days}\"[Date - Publication] : \"0\"[Date - Publication])"
        
        params = {
            "db": "pubmed",
            "term": date_query,
            "retmax": max_results,
            "retmode": "json",
            "usehistory": "y"
        }
        
        url = f"{self.base_url}/esearch.fcgi"
        logger.info(f"Searching PubMed with query: {query}")
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        pmids = data["esearchresult"]["idlist"]
        
        logger.info(f"Found {len(pmids)} articles")
        return pmids
    
    def fetch_article_details(self, pmids: List[str]) -> List[Dict]:
        """Fetch detailed article information using EFetch.
        
        Args:
            pmids: List of PubMed IDs
            
        Returns:
            List of article details
        """
        if not pmids:
            return []
            
        # PubMed limits EFetch to 10000 IDs at a time
        if len(pmids) > 10000:
            pmids = pmids[:10000]
            
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml"
        }
        
        url = f"{self.base_url}/efetch.fcgi"
        logger.info(f"Fetching details for {len(pmids)} articles")
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        # Parse XML response
        root = ET.fromstring(response.content)
        articles = []
        
        for article in root.findall(".//PubmedArticle"):
            parsed_article = self._parse_article(article)
            if parsed_article:
                articles.append(parsed_article)
                
        logger.info(f"Parsed {len(articles)} articles")
        return articles
    
    def _parse_article(self, article_xml) -> Optional[Dict]:
        """Parse a single article from XML.
        
        Args:
            article_xml: XML element for a single article
            
        Returns:
            Dictionary with article details or None if parsing failed
        """
        try:
            # Extract PMID
            pmid_elem = article_xml.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else ""
            
            # Extract title
            title_elem = article_xml.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else ""
            
            # Extract abstract
            abstract_elem = article_xml.find(".//AbstractText")
            abstract = abstract_elem.text if abstract_elem is not None else ""
            
            # Extract journal
            journal_elem = article_xml.find(".//Journal/Title")
            journal = journal_elem.text if journal_elem is not None else ""
            
            # Extract publication date
            pub_date_elem = article_xml.find(".//PubDate/Year")
            year = pub_date_elem.text if pub_date_elem is not None else ""
            
            # Extract authors
            authors = []
            for author_elem in article_xml.findall(".//Author"):
                last_name = author_elem.find("LastName")
                first_name = author_elem.find("ForeName")
                if last_name is not None and first_name is not None:
                    authors.append(f"{first_name.text} {last_name.text}")
                elif last_name is not None:
                    authors.append(last_name.text)
            
            # Extract DOI
            doi_elem = article_xml.find(".//ArticleId[@IdType='doi']")
            doi = doi_elem.text if doi_elem is not None else None
            
            # Extract MeSH terms
            mesh_terms = []
            for mesh_elem in article_xml.findall(".//MeshHeading/DescriptorName"):
                if mesh_elem.text:
                    mesh_terms.append(mesh_elem.text)
            
            # Extract language
            language_elem = article_xml.find(".//Language")
            language = language_elem.text if language_elem is not None else "English"
            
            return {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "journal": journal,
                "year": int(year) if year.isdigit() else 0,
                "pub_date": year,
                "doi": doi,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                "language": language,
                "mesh_terms": mesh_terms
            }
        except Exception as e:
            logger.error(f"Error parsing article: {e}")
            return None


# Create a global client instance
pubmed_client = PubMedClient()