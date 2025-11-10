from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

def ensure_page_param(url: str, page: int = 1) -> str:
    """
    Ensure the URL has a 'page' query parameter. If absent, set to the provided page.
    """
    parts = urlparse(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    if "page" not in q:
        q["page"] = str(page)
        new_query = urlencode(q, doseq=True)
        return urlunparse(parts._replace(query=new_query))
    return url

def next_page_url(current_url: str, next_page_num: int) -> Optional[str]:
    """
    Compute the next page URL by bumping the 'page' parameter.
    Returns None if the URL cannot be paginated.
    """
    parts = urlparse(current_url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    # If no page parameter, we cannot reliably paginate
    if "page" not in q:
        return None
    q["page"] = str(next_page_num)
    new_query = urlencode(q, doseq=True)
    return urlunparse(parts._replace(query=new_query))