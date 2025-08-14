"""Text cleaning and sectioning utilities for full-text articles."""

import re
from typing import Dict, List, Optional, Tuple, TypedDict
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None


# Type definitions
class SectionedText(TypedDict):
    abstract: str
    introduction: str
    methods: str
    results: str
    discussion: str
    conclusion: str


class ExcerptedText(TypedDict):
    abstract: str
    introduction: str
    methods: str
    results: str
    discussion: str
    conclusion: str


# Section mapping configuration
SECTION_SYNONYMS = {
    "abstract": ["abstract", "summary"],
    "introduction": ["introduction", "background", "rationale", "purpose"],
    "methods": ["methods", "materials and methods", "patients and methods", "experimental procedures", "study design"],
    "results": ["results", "findings", "outcome", "outcomes"],
    "discussion": ["discussion", "interpretation", "clinical implications", "limitations"],
    "conclusion": ["conclusion", "conclusions", "summary"]
}

# Key terms for excerpt selection
KEY_TERMS = [
    "effect size", "confidence interval", "p-value", "subgroup", 
    "blinding", "allocation", "sample size", "attrition", 
    "primary outcome", "secondary outcome", "hypothesis"
]


def parse_and_section(
    html: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None
) -> SectionedText:
    """
    Parse and section full-text content.
    
    Args:
        html: HTML content to parse
        pdf_bytes: PDF bytes to parse
        
    Returns:
        SectionedText with content organized by section
    """
    # Initialize empty sections
    sections: SectionedText = {
        "abstract": "",
        "introduction": "",
        "methods": "",
        "results": "",
        "discussion": "",
        "conclusion": ""
    }
    
    if html:
        sections = _section_html_content(html)
    elif pdf_bytes:
        sections = _section_pdf_content(pdf_bytes)
    
    return sections


def select_excerpts_for_prompt(
    sectioned_text: SectionedText,
    max_tokens: int
) -> ExcerptedText:
    """
    Select relevant excerpts from sectioned text within token budget.
    
    Args:
        sectioned_text: Text organized by section
        max_tokens: Maximum tokens allowed for LLM prompt
        
    Returns:
        ExcerptedText with selected content
    """
    # Allocate token budget across sections
    token_allocation = _allocate_token_budget(max_tokens)
    
    # Select excerpts from each section
    excerpted_text: ExcerptedText = {
        "abstract": "",
        "introduction": "",
        "methods": "",
        "results": "",
        "discussion": "",
        "conclusion": ""
    }
    
    for section_name, section_text in sectioned_text.items():
        if section_name in token_allocation:
            allocated_tokens = token_allocation[section_name]
            excerpted_text[section_name] = _select_excerpts_from_section(
                section_text, allocated_tokens, KEY_TERMS
            )
    
    return excerpted_text


def detect_content_red_flags(sectioned_text: SectionedText) -> List[str]:
    """
    Detect additional red flags from full-text content.
    
    New flags:
    - Missing CONSORT elements in parsed text
    - Very small N in methods vs large claimed precision
    - Multiple outcomes with no stated hierarchy
    - Subgroup analyses emphasized without a priori plan
    
    Returns:
        List of content-based red flags
    """
    red_flags = []
    
    # Check for missing CONSORT elements
    methods_text = sectioned_text.get("methods", "").lower()
    if "allocation" not in methods_text and "random" in methods_text:
        red_flags.append("Missing CONSORT element: allocation concealment not mentioned")
    
    if "blinding" not in methods_text and "masking" not in methods_text:
        red_flags.append("Missing CONSORT element: blinding procedures not described")
    
    # Check for very small N vs precision claims
    # This is a simplified check - in practice would need more sophisticated analysis
    if "small sample" in methods_text and "precise estimate" in sectioned_text.get("results", "").lower():
        red_flags.append("Potential inconsistency: small sample size with precise estimates claimed")
    
    # Check for multiple outcomes without hierarchy
    results_text = sectioned_text.get("results", "").lower()
    if results_text.count("outcome") > 3 and "primary outcome" not in results_text:
        red_flags.append("Multiple outcomes reported without clear primary outcome designation")
    
    # Check for subgroup analyses without a priori plan
    if "subgroup" in results_text and "predefined" not in results_text and "a priori" not in results_text:
        red_flags.append("Subgroup analyses presented without stated a priori plan")
    
    return red_flags


# HTML parsing functions
def _clean_html(html_content: str) -> str:
    """
    Clean HTML content by removing navigation, ads, and other non-content elements.
    
    Uses beautifulsoup4 and readability-lxml style heuristics.
    """
    if BeautifulSoup is None:
        # Fallback if BeautifulSoup not available
        # Remove script and style elements
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
        # Remove HTML comments
        html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
        # Extract text content
        text = re.sub(r'<[^>]+>', '', html_content)
        return _clean_whitespace(text)
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.decompose()
    
    # Remove navigation elements
    for nav in soup.find_all(["nav", "header", "footer", "aside"]):
        nav.decompose()
    
    # Remove ads and sidebars
    for ad_class in ["advertisement", "ad", "sidebar", "banner"]:
        for element in soup.find_all(class_=re.compile(ad_class, re.I)):
            element.decompose()
    
    # Extract text content
    text = soup.get_text()
    
    # Clean whitespace
    return _clean_whitespace(text)


def _extract_main_content(html_content: str) -> str:
    """
    Extract main article content from HTML.
    """
    if BeautifulSoup is None:
        return _clean_html(html_content)
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try to find main content area
    main_content = None
    
    # Look for common content containers
    for selector in ["main", "article", ".article-content", ".fulltext", "#main-content"]:
        main_content = soup.select_one(selector)
        if main_content:
            break
    
    # If not found, use body content
    if not main_content:
        main_content = soup.find('body')
    
    if main_content:
        return _clean_html(str(main_content))
    else:
        return _clean_html(html_content)


def _section_html_content(html_content: str) -> SectionedText:
    """
    Section HTML content into standard sections.
    """
    # Extract main content
    text = _extract_main_content(html_content)
    
    # Identify section headers and their positions
    section_headers = _identify_section_headers(text)
    
    # Initialize sections
    sections: SectionedText = {
        "abstract": "",
        "introduction": "",
        "methods": "",
        "results": "",
        "discussion": "",
        "conclusion": ""
    }
    
    # Extract content for each section
    section_names = list(sections.keys())
    text_lines = text.split('\n')
    
    current_section = "abstract"  # Default to abstract
    current_content = []
    
    for line in text_lines:
        # Check if line is a section header
        header_match = _map_section_headers(line.strip())
        if header_match:
            # Save previous section content
            if current_content:
                sections[current_section] = '\n'.join(current_content).strip()
                current_content = []
            
            # Update current section
            current_section = header_match
        else:
            # Add line to current section
            current_content.append(line)
    
    # Save final section content
    if current_content:
        sections[current_section] = '\n'.join(current_content).strip()
    
    return sections


# PDF parsing functions
def _extract_pdf_text(pdf_bytes: bytes, max_pages: int = 40) -> str:
    """
    Extract text from PDF bytes.
    
    Uses PyPDF2 for text extraction.
    """
    if PyPDF2 is None:
        return "PDF parsing not available (PyPDF2 not installed)"
    
    try:
        # Convert bytes to file-like object
        from io import BytesIO
        pdf_file = BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text_parts = []
        
        # Extract text from pages up to max_pages
        for i in range(min(len(pdf_reader.pages), max_pages)):
            page = pdf_reader.pages[i]
            text_parts.append(page.extract_text())
        
        return '\n'.join(text_parts)
    except Exception as e:
        return f"Error extracting PDF text: {str(e)}"


def _section_pdf_content(pdf_bytes: bytes, max_pages: int = 40) -> SectionedText:
    """
    Section PDF text into standard sections.
    """
    # Extract text from PDF
    text = _extract_pdf_text(pdf_bytes, max_pages)
    
    # For PDF content, we'll use a simpler approach since we don't have HTML structure
    # Initialize sections
    sections: SectionedText = {
        "abstract": "",
        "introduction": "",
        "methods": "",
        "results": "",
        "discussion": "",
        "conclusion": ""
    }
    
    # Split text into lines for processing
    text_lines = text.split('\n')
    
    current_section = "abstract"  # Default to abstract
    current_content = []
    
    for line in text_lines:
        line = line.strip()
        if line:
            # Check if line is a section header
            header_match = _map_section_headers(line)
            if header_match:
                # Save previous section content
                if current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                    current_content = []
                
                # Update current section
                current_section = header_match
            else:
                # Add line to current section
                current_content.append(line)
    
    # Save final section content
    if current_content:
        sections[current_section] = '\n'.join(current_content).strip()
    
    return sections


# Sectioning logic
def _identify_section_headers(text: str) -> Dict[str, Tuple[int, int]]:
    """
    Identify section headers and their positions in text.
    
    Handles synonyms like "Materials and Methods" for "Methods".
    """
    headers = {}
    
    # Look for section headers in the text
    lines = text.split('\n')
    for i, line in enumerate(lines):
        line = line.strip()
        if line:
            # Check if line matches any section header or synonym
            section_name = _map_section_headers(line)
            if section_name:
                headers[section_name] = (i, len(line))
    
    return headers


def _map_section_headers(header: str) -> Optional[str]:
    """
    Map non-standard section headers to standard sections.
    
    Examples:
    - "Materials and Methods" -> "methods"
    - "Results and Discussion" -> "results" or "discussion"
    - "Background" -> "introduction"
    """
    header_lower = header.lower().strip()
    
    # Remove common prefixes/suffixes
    header_lower = re.sub(r'^\d+\s*', '', header_lower)  # Remove leading numbers
    header_lower = re.sub(r'\s*[:\-].*$', '', header_lower)  # Remove trailing colon/content
    
    # Check each section and its synonyms
    for section, synonyms in SECTION_SYNONYMS.items():
        # Check exact match first
        if header_lower == section:
            return section
        
        # Check synonyms
        for synonym in synonyms:
            if synonym in header_lower or header_lower in synonym:
                return section
    
    return None


# Text processing utilities
def _join_hyphenated_words(text: str) -> str:
    """
    Join hyphenated words that were split across lines.
    """
    # Pattern to match hyphenated words at end of line
    pattern = r'(\w+)-\s*\n\s*(\w+)'
    return re.sub(pattern, r'\1\2', text)


def _clean_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.
    """
    # Replace multiple whitespace characters with single space
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    return text.strip()


def _remove_figures_and_tables(text: str) -> str:
    """
    Remove figure and table references/descriptions.
    """
    # Remove figure references
    text = re.sub(r'Figure\s+\d+[A-Za-z]?(?:\s*[:\-].*?)?(?=\n|$)', '', text, flags=re.IGNORECASE)
    # Remove table references
    text = re.sub(r'Table\s+\d+[A-Za-z]?(?:\s*[:\-].*?)?(?=\n|$)', '', text, flags=re.IGNORECASE)
    # Remove figure/table captions
    text = re.sub(r'(?:Fig\.|Figure|Table)\s*\d+[A-Za-z]?.*?(?=\n\n|$)', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    return text


# Excerpt selection logic
def _estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    
    Uses rough estimate: 1 token ≈ 4 chars in English.
    """
    return len(text) // 4


def _allocate_token_budget(max_tokens: int) -> Dict[str, int]:
    """
    Allocate token budget across sections.
    
    Default allocation:
    - Abstract: 10%
    - Introduction: 10%
    - Methods: 25%
    - Results: 35%
    - Discussion: 15%
    - Conclusion: 5%
    """
    return {
        "abstract": int(max_tokens * 0.10),
        "introduction": int(max_tokens * 0.10),
        "methods": int(max_tokens * 0.25),
        "results": int(max_tokens * 0.35),
        "discussion": int(max_tokens * 0.15),
        "conclusion": int(max_tokens * 0.05)
    }


def _select_excerpts_from_section(
    section_text: str,
    allocated_tokens: int,
    key_terms: List[str]
) -> str:
    """
    Select relevant excerpts from a section.
    
    Prioritizes paragraphs containing key terms like:
    - Effect estimates
    - Confidence intervals
    - P-values
    - Subgroup analyses
    - Blinding/allocation mentions
    - Sample size references
    - Attrition/dropout information
    """
    if not section_text:
        return ""
    
    # Split into paragraphs
    paragraphs = section_text.split('\n\n')
    
    # Calculate tokens per paragraph budget
    avg_paragraph_tokens = allocated_tokens // max(len(paragraphs), 1)
    
    # Score paragraphs based on key terms
    scored_paragraphs = []
    for paragraph in paragraphs:
        score = 0
        paragraph_lower = paragraph.lower()
        
        # Score based on key terms
        for term in key_terms:
            if term in paragraph_lower:
                score += 1
        
        # Bonus for numbers (likely effect estimates, p-values, etc.)
        if re.search(r'\d+\.\d+', paragraph):
            score += 0.5
        
        scored_paragraphs.append((paragraph, score))
    
    # Sort by score (descending)
    scored_paragraphs.sort(key=lambda x: x[1], reverse=True)
    
    # Select paragraphs within token budget
    selected_paragraphs = []
    current_tokens = 0
    
    for paragraph, score in scored_paragraphs:
        paragraph_tokens = _estimate_tokens(paragraph)
        if current_tokens + paragraph_tokens <= allocated_tokens:
            selected_paragraphs.append(paragraph)
            current_tokens += paragraph_tokens
        else:
            # If we can't fit the whole paragraph, try to fit a part of it
            remaining_tokens = allocated_tokens - current_tokens
            if remaining_tokens > 10:  # Minimum for a meaningful excerpt
                # Approximate how much of the paragraph we can include
                chars_to_include = remaining_tokens * 4
                truncated_paragraph = paragraph[:chars_to_include] + "..."
                selected_paragraphs.append(truncated_paragraph)
            break
    
    return '\n\n'.join(selected_paragraphs)