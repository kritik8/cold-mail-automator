"""Company and job posting public web research module."""
import re
from typing import Dict, Optional
import requests
from bs4 import BeautifulSoup
from src.logger import get_logger

logger = get_logger()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

NOISE_TAGS = ["script", "style", "nav", "footer", "header", "noscript", "svg", "form", "iframe", "aside"]


def clean_html_text(html_content: str, max_chars: int = 1500) -> str:
    """Extract clean, meaningful paragraphs and headings from raw HTML."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Remove noisy structural elements
        for tag in soup(NOISE_TAGS):
            tag.decompose()

        # Extract title and meta description
        meta_desc = ""
        desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if desc_tag and desc_tag.get("content"):
            meta_desc = desc_tag.get("content").strip()

        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        # Extract meaningful body text
        text_elements = []
        for elem in soup.find_all(["h1", "h2", "h3", "p", "li"]):
            t = elem.get_text(strip=True)
            if len(t) > 20 and not any(skip in t.lower() for skip in ["cookie", "privacy policy", "terms of service", "all rights reserved", "subscribe"]):
                text_elements.append(t)

        combined_text = "\n".join(text_elements)
        # Collapse multiple whitespaces
        combined_text = re.sub(r'\s+', ' ', combined_text).strip()

        summary_parts = []
        if title:
            summary_parts.append(f"Title: {title}")
        if meta_desc:
            summary_parts.append(f"Description: {meta_desc}")
        if combined_text:
            summary_parts.append(f"Content: {combined_text[:max_chars]}")

        return "\n".join(summary_parts)
    except Exception as e:
        logger.debug(f"Error parsing HTML text: {e}")
        return ""


def fetch_public_url(url: str, timeout: int = 6) -> Optional[str]:
    """Fetch public page content safely with strict timeout."""
    if not url or not isinstance(url, str):
        return None
    
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    # Skip LinkedIn or restricted domains that require authentication
    if any(domain in url.lower() for domain in ["linkedin.com", "facebook.com", "instagram.com"]):
        logger.debug(f"Skipping scraping on restricted domain: {url}")
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            return clean_html_text(response.text)
        else:
            logger.debug(f"Failed to fetch URL {url} with status {response.status_code}")
            return None
    except Exception as e:
        logger.debug(f"Could not fetch {url}: {e}")
        return None


def gather_lead_context(company_url: Optional[str] = None, job_url: Optional[str] = None) -> Dict[str, str]:
    """Gather research text from public company website and job link if available."""
    context: Dict[str, str] = {
        "company_website_info": "",
        "job_posting_info": ""
    }

    if company_url:
        web_info = fetch_public_url(company_url)
        if web_info:
            context["company_website_info"] = web_info

    if job_url:
        job_info = fetch_public_url(job_url)
        if job_info:
            context["job_posting_info"] = job_info

    return context
