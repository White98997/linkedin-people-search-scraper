from __future__ import annotations

import http.cookiejar as cookiejar
from typing import Dict, Iterable, List, Union

import requests

def cookie_header_from_cookie_editor_json(cookies_json: Union[List[dict], Dict]) -> str:
    """
    Convert Cookie-Editor export JSON into a Cookie header string.
    Accepts either list-of-cookies or an object with 'cookies' field containing the list.

    Each cookie entry should include at least 'name' and 'value'.
    """
    if isinstance(cookies_json, dict) and "cookies" in cookies_json:
        items = cookies_json.get("cookies", [])
    elif isinstance(cookies_json, list):
        items = cookies_json
    else:
        raise ValueError("Unsupported Cookie-Editor JSON format")

    parts: List[str] = []
    for c in items:
        name = c.get("name")
        value = c.get("value")
        if not name or value is None:
            continue
        parts.append(f"{name}={value}")
    return "; ".join(parts)

def cookie_jar_from_cookie_string(cookie_string: str) -> requests.cookies.RequestsCookieJar:
    """
    Convert a raw 'Cookie' header string into a RequestsCookieJar.
    Example: 'li_at=abc; li_a=1; JSESSIONID="foo"'
    """
    jar = requests.cookies.RequestsCookieJar()
    for part in cookie_string.split(";"):
        if not part.strip():
            continue
        if "=" not in part:
            # Flag-style cookie (rare)
            jar.set(part.strip(), "")
            continue
        name, value = part.split("=", 1)
        jar.set(name.strip(), value.strip())
    return jar