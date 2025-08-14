"""
Module for retrieving and parsing full-text articles from various sources.
"""

import os
import re
import time
import requests
from typing import Optional, Dict, Any, TypedDict
from urllib.parse import urljoin, urlparse

# Type definitions
class FullTextResult(TypedDict, total=False):
    route: str                 # "pmc"|"unpaywall"|"europempc"|"publisher"|"abstract"|"override"
    pmcid: Optional[str]
    oa_pdf_url: Optional[str]
    publisher_url: Optional[str]
    html: Optional[str]        # cleaned HTML string
    pdf_bytes: Optional[bytes] # raw PDF if fetched
    abstract: Optional[str]


def resolve_fulltext(
    doi: Optional[str], 
    pmid: Optional[str], 
    settings: Dict[str, Any]
) -> Optional[FullTextResult]:
    """
    Main entry point for full-text retrieval.
    
    Args:
        doi: Digital Object Identifier
        pmid: PubMed ID
        settings: Analysis settings with retrieval options
        
    Returns:
        FullTextResult with retrieved content
    """
    # If fulltext_override provided, use it (route="override")
    if settings.get("fulltext_override"):
        return {
            "route": "override",
            "html": settings["fulltext_override"]
        }
    
    # Honor allow_network setting
    if not settings.get("allow_network", True):
        return None
    
    # Try retrieval in order
    # 1. PubMed Central (PMC) via PMCID or via Europe PMC
    result = _fetch_pmc(doi, pmid, None, settings)
    if result:
        return result
    
    # 2. Unpaywall (requires unpaywall_email)
    if settings.get("unpaywall_email"):
        result = _fetch_unpaywall(doi, settings)
        if result:
            return result
    
    # 3. Europe PMC REST API
    result = _fetch_europe_pmc(doi, pmid, settings)
    if result:
        return result
    
    # 4. Crossref (DOI → publisher landing page)
    if doi:
        result = _fetch_crossref(doi, settings)
        if result:
            return result
    
    # 5. Fallback to abstract if allowed
    if settings.get("abstract_only_ok", True):
        result = _fetch_abstract(doi, pmid, settings)
        if result:
            return result
    
    return None


def _fetch_pmc(
    doi: Optional[str], 
    pmid: Optional[str], 
    pmcid: Optional[str],
    settings: Dict[str, Any]
) -> Optional[FullTextResult]:
    """
    Fetch from PubMed Central.
    
    Tries direct PMCID access first, then queries Europe PMC to get PMCID.
    """
    try:
        # If we already have PMCID, try direct access
        if pmcid:
            # Try to fetch PDF first
            pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
            response = _make_request(pdf_url, settings, "application/pdf")
            if response and response.status_code == 200:
                return {
                    "route": "pmc",
                    "pmcid": pmcid,
                    "oa_pdf_url": pdf_url,
                    "pdf_bytes": response.content
                }
            
            # Try HTML version
            html_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
            response = _make_request(html_url, settings, "text/html")
            if response and response.status_code == 200:
                return {
                    "route": "pmc",
                    "pmcid": pmcid,
                    "html": response.text
                }
        
        # If we don't have PMCID, try to get it from identifiers
        pmcid_from_identifiers = _get_pmcid_from_identifiers(doi, pmid, settings)
        if pmcid_from_identifiers:
            return _fetch_pmc(doi, pmid, pmcid_from_identifiers, settings)
            
    except Exception as e:
        # Silently fail and let other methods try
        pass
    
    return None


def _fetch_unpaywall(
    doi: str, 
    settings: Dict[str, Any]
) -> Optional[FullTextResult]:
    """
    Fetch from Unpaywall API.
    
    Requires unpaywall_email in settings.
    """
    try:
        email = settings.get("unpaywall_email")
        if not email:
            return None
        
        # Construct Unpaywall API URL
        url = f"https://api.unpaywall.org/v2/{doi}"
        params = {"email": email}
        
        response = _make_request(url, settings)
        if response and response.status_code == 200:
            data = response.json()
            
            # Check for best OA location
            best_oa_location = data.get("best_oa_location")
            if best_oa_location:
                pdf_url = best_oa_location.get("pdf_url")
                if pdf_url:
                    # Fetch the PDF
                    pdf_response = _make_request(pdf_url, settings, "application/pdf")
                    if pdf_response and pdf_response.status_code == 200:
                        return {
                            "route": "unpaywall",
                            "oa_pdf_url": pdf_url,
                            "pdf_bytes": pdf_response.content
                        }
                
                # Fallback to URL if PDF not available
                url = best_oa_location.get("url")
                if url:
                    html_response = _make_request(url, settings, "text/html")
                    if html_response and html_response.status_code == 200:
                        return {
                            "route": "unpaywall",
                            "publisher_url": url,
                            "html": html_response.text
                        }
    except Exception as e:
        # Silently fail and let other methods try
        pass
    
    return None


def _fetch_europe_pmc(
    doi: Optional[str], 
    pmid: Optional[str], 
    settings: Dict[str, Any]
) -> Optional[FullTextResult]:
    """
    Fetch from Europe PMC REST API.
    """
    try:
        # Build query
        query = ""
        if doi:
            query = f"DOI:{doi}"
        elif pmid:
            query = f"EXT_ID:{pmid}"
        else:
            return None
        
        # Europe PMC API URL
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": query,
            "resultType": "core",
            "format": "json"
        }
        
        response = _make_request(url, settings)
        if response and response.status_code == 200:
            data = response.json()
            
            # Check if we have results
            results = data.get("resultList", {}).get("result", [])
            if results:
                result = results[0]
                pmcid = result.get("pmcid")
                
                # Try to get full text links
                full_text_links = result.get("fullTextUrlList", {}).get("fullTextUrl", [])
                for link in full_text_links:
                    doc_type = link.get("documentType")
                    if doc_type == "pdf":
                        pdf_url = link.get("url")
                        if pdf_url:
                            # Fetch the PDF
                            pdf_response = _make_request(pdf_url, settings, "application/pdf")
                            if pdf_response and pdf_response.status_code == 200:
                                return {
                                    "route": "europempc",
                                    "pmcid": pmcid,
                                    "oa_pdf_url": pdf_url,
                                    "pdf_bytes": pdf_response.content
                                }
                    elif doc_type == "html":
                        html_url = link.get("url")
                        if html_url:
                            html_response = _make_request(html_url, settings, "text/html")
                            if html_response and html_response.status_code == 200:
                                return {
                                    "route": "europempc",
                                    "pmcid": pmcid,
                                    "html": html_response.text
                                }
                
                # If we have PMCID, try PMC directly
                if pmcid:
                    return _fetch_pmc(doi, pmid, pmcid, settings)
    except Exception as e:
        # Silently fail and let other methods try
        pass
    
    return None


def _fetch_crossref(
    doi: str, 
    settings: Dict[str, Any]
) -> Optional[FullTextResult]:
    """
    Fetch from Crossref and publisher landing page.
    """
    try:
        # Crossref API URL
        url = f"https://api.crossref.org/works/{doi}"
        
        response = _make_request(url, settings)
        if response and response.status_code == 200:
            data = response.json()
            
            # Get publisher URL
            publisher_url = data.get("message", {}).get("url")
            if publisher_url:
                # Try to get HTML content
                html_response = _make_request(publisher_url, settings, "text/html")
                if html_response and html_response.status_code == 200:
                    # Check if it's a PDF
                    content_type = html_response.headers.get("content-type", "")
                    if "application/pdf" in content_type:
                        return {
                            "route": "publisher",
                            "publisher_url": publisher_url,
                            "pdf_bytes": html_response.content
                        }
                    else:
                        return {
                            "route": "publisher",
                            "publisher_url": publisher_url,
                            "html": html_response.text
                        }
    except Exception as e:
        # Silently fail and let other methods try
        pass
    
    return None


def _fetch_abstract(
    doi: Optional[str], 
    pmid: Optional[str], 
    settings: Dict[str, Any]
) -> Optional[FullTextResult]:
    """
    Fetch abstract as fallback.
    """
    try:
        # Try Europe PMC for abstract
        query = ""
        if doi:
            query = f"DOI:{doi}"
        elif pmid:
            query = f"EXT_ID:{pmid}"
        else:
            return None
        
        # Europe PMC API URL for abstract
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": query,
            "resultType": "core",
            "format": "json"
        }
        
        response = _make_request(url, settings)
        if response and response.status_code == 200:
            data = response.json()
            
            # Check if we have results
            results = data.get("resultList", {}).get("result", [])
            if results:
                result = results[0]
                abstract = result.get("abstractText")
                if abstract:
                    return {
                        "route": "abstract",
                        "abstract": abstract
                    }
    except Exception as e:
        # Silently fail
        pass
    
    return None


def _make_request(
    url: str, 
    settings: Dict[str, Any],
    expected_content_type: Optional[str] = None
) -> Optional[requests.Response]:
    """
    Make HTTP request with appropriate headers and timeout.
    """
    try:
        # Get timeout from settings or default to 30 seconds
        timeout = settings.get("timeout_seconds", 30)
        
        # Get user agent from settings or environment
        user_agent = settings.get("user_agent") or os.environ.get("HTTP_USER_AGENT")
        if not user_agent:
            user_agent = "Mozilla/5.0 ( compatible; podcast-rct/1.0 )"
        
        headers = {
            "User-Agent": user_agent
        }
        
        # Make request
        response = requests.get(url, headers=headers, timeout=timeout)
        
        # Check content type if specified
        if expected_content_type:
            content_type = response.headers.get("content-type", "")
            if expected_content_type not in content_type:
                return None
        
        return response
    except Exception as e:
        # Silently fail
        return None


def _get_pmcid_from_identifiers(
    doi: Optional[str], 
    pmid: Optional[str], 
    settings: Dict[str, Any]
) -> Optional[str]:
    """
    Query Europe PMC to get PMCID from DOI or PMID.
    """
    try:
        # Build query
        query = ""
        if doi:
            query = f"DOI:{doi}"
        elif pmid:
            query = f"EXT_ID:{pmid}"
        else:
            return None
        
        # Europe PMC API URL
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": query,
            "resultType": "core",
            "format": "json"
        }
        
        response = _make_request(url, settings)
        if response and response.status_code == 200:
            data = response.json()
            
            # Check if we have results
            results = data.get("resultList", {}).get("result", [])
            if results:
                result = results[0]
                return result.get("pmcid")
    except Exception as e:
        # Silently fail
        pass
    
    return None