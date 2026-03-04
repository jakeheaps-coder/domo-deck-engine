"""
Research engine — pulls messaging, products, competitors, and industry data
from the Knowledge Graph API to inform slide content.
"""

from typing import Dict, Any, List
from helpers.kg_api_helper import (
    get_messaging,
    get_product_profile,
    get_competitor_details,
    get_industries,
    search_documents,
)


def research_for_deck(
    audience: str = "",
    industry: str = "",
    products: List[str] = None,
    competitors: List[str] = None,
    topic: str = "",
) -> Dict[str, Any]:
    """
    Run comprehensive research for a deck and return a unified research package.

    Returns:
        {
            "messaging": {...},       # VP, pain points, features from /api/messaging
            "products": [...],        # Product profiles
            "competitors": [...],     # Competitor intel
            "topic_docs": [...],      # Documents matching the topic
        }
    """
    products = products or []
    competitors = competitors or []

    package: Dict[str, Any] = {
        "messaging": {},
        "products": [],
        "competitors": [],
        "topic_docs": [],
    }

    # 1. Core messaging (fastest, most useful endpoint)
    audience_map = {
        "Board": "Business Executives",
        "Executive": "Business Executives",
        "Sales / Customer": "Business Executives",
        "Internal / Strategy": "IT / Data Leaders",
        "CS Team": "Business Executives",
    }
    kg_audience = audience_map.get(audience, audience)
    messaging = get_messaging(audience=kg_audience, industry=industry)
    if messaging.get("success") is not False:
        package["messaging"] = messaging

    # 2. Product profiles
    for product_name in products:
        profile = get_product_profile(product_name)
        if profile.get("success") is not False:
            package["products"].append({"name": product_name, "profile": profile})

    # 3. Competitor intel
    for competitor_name in competitors:
        details = get_competitor_details(competitor_name)
        if details.get("success") is not False:
            package["competitors"].append({"name": competitor_name, "details": details})

    # 4. Topic-based document search
    if topic:
        # Extract key terms from purpose/topic
        search_terms = topic.split()[:5]  # First 5 words as search
        search_query = " ".join(search_terms)
        docs = search_documents(search_query)
        if docs.get("success") is not False:
            package["topic_docs"] = docs.get("documents", [])[:5]

    return package


def summarize_research(research: Dict[str, Any]) -> str:
    """
    Convert research package into a concise text summary for the content writer.
    """
    parts = []

    # Messaging summary
    msg = research.get("messaging", {})
    if msg:
        if "value_propositions" in msg:
            vps = msg["value_propositions"]
            if isinstance(vps, list):
                parts.append("VALUE PROPOSITIONS:\n" + "\n".join(f"- {vp}" for vp in vps[:5]))
        if "pain_points" in msg:
            pps = msg["pain_points"]
            if isinstance(pps, list):
                parts.append("PAIN POINTS:\n" + "\n".join(f"- {pp}" for pp in pps[:5]))
        if "features" in msg:
            feats = msg["features"]
            if isinstance(feats, list):
                parts.append("KEY FEATURES:\n" + "\n".join(f"- {f}" for f in feats[:5]))
        if "recommended_products" in msg:
            prods = msg["recommended_products"]
            if isinstance(prods, list):
                parts.append("RECOMMENDED PRODUCTS: " + ", ".join(prods))

    # Product summaries
    for prod in research.get("products", []):
        name = prod["name"]
        profile = prod.get("profile", {})
        desc = profile.get("description", "")
        if desc:
            parts.append(f"PRODUCT — {name}:\n{desc[:300]}")

    # Competitor summaries
    for comp in research.get("competitors", []):
        name = comp["name"]
        details = comp.get("details", {})
        desc = details.get("description", details.get("positioning", ""))
        if desc:
            parts.append(f"COMPETITOR — {name}:\n{desc[:200]}")

    return "\n\n".join(parts) if parts else "No research data available."
