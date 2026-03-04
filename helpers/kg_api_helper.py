"""Knowledge Graph API helper — copied from shared toolkit."""

import os
import requests
from typing import Dict, Any, Optional


DEFAULT_KG_API_URL = "https://knowledge-graph-api-1053548598846.us-central1.run.app"
DEFAULT_KG_API_KEY = "1nbtfQeoY9/nmY8xvdbhrF9H23q6tqh6q7jmIiu8Xxs="


def _call_api(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base_url = os.environ.get("KG_API_URL", DEFAULT_KG_API_URL)
    api_key = os.environ.get("KG_API_KEY", DEFAULT_KG_API_KEY)
    url = f"{base_url}{endpoint}"
    headers = {"Content-Type": "application/json", "X-API-Key": api_key}

    try:
        if params:
            response = requests.post(url, headers=headers, json=params, timeout=30)
        else:
            response = requests.get(url, headers=headers, timeout=30)
        if not response.ok:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_messaging(audience: str = "", industry: str = "") -> Dict[str, Any]:
    params = {}
    if audience:
        params["audience"] = audience
    if industry:
        params["industry"] = industry
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return _call_api(f"/api/messaging?{qs}" if qs else "/api/messaging")


def get_product_profile(product_name: str) -> Dict[str, Any]:
    return _call_api(f"/api/products/{product_name}/profile")


def get_product_sections(product_name: str) -> Dict[str, Any]:
    return _call_api(f"/api/products/{product_name}/sections")


def get_competitor_details(competitor_name: str) -> Dict[str, Any]:
    return _call_api(f"/api/competitors/{competitor_name}")


def get_all_products() -> Dict[str, Any]:
    return _call_api("/api/products")


def get_all_competitors() -> Dict[str, Any]:
    return _call_api("/api/competitors")


def get_industries() -> Dict[str, Any]:
    return _call_api("/api/industries")


def search_documents(keyword: str) -> Dict[str, Any]:
    return _call_api(f"/api/documents/search?q={keyword}")


def cascade_validate(content: str, context: str = "") -> Dict[str, Any]:
    return _call_api("/api/v5/validate/cascade", {"content": content, "context": context})
