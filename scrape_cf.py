#!/usr/bin/env python3
"""
Carbon Future (ISSN 2960-0561) Article Scraper
Scrapes 2024-2026 articles from SciOpen and saves structured data to JSON.
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import json
from pathlib import Path

BASE_URL = "https://www.sciopen.com"
ISSN = "2960-0561"
JOURNAL_ID = "1627866359668432898"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

OUTPUT_DIR = Path("D:/Claw/Carbon_Future_Year/articles_md")

def get_meta(soup, name):
    """Extract single meta tag content."""
    tag = soup.find("meta", attrs={"name": name})
    if not tag:
        tag = soup.find("meta", attrs={"property": name})
    return tag["content"] if tag and tag.get("content") else None

def get_meta_all(soup, name):
    """Extract all meta tag contents with given name."""
    results = []
    for tag in soup.find_all("meta", attrs={"name": name}):
        if tag.get("content"):
            results.append(tag["content"])
    return results

def extract_article_type(soup):
    """Extract article type from .v4-art-info span."""
    art_info = soup.select(".v4-art-info span")
    if art_info:
        return art_info[0].get_text().strip()
    return None

def extract_research_area(title, keywords, abstract):
    """Assign research areas based on keyword matching against Carbon Future taxonomy."""
    text = (title or "").lower()
    kw_text = " ".join(keywords or []).lower()
    abstract_text = (abstract or "").lower()
    combined = f"{text} {kw_text} {abstract_text}"

    CATEGORY_RULES = {
        "Carbon materials": ["carbon material", "carbon fiber", "carbon nanotube", "graphene", "carbon black", "activated carbon", "carbon aerogel", "carbon sphere", "carbon dot", "carbon quantum", "carbon-based", "carbon composite", "carbon structure", "carbon synthesis", "carbon precursor"],
        "Catalysis": ["catalys", "catalyst", "catalytic", "photocatalys", "electrocatalys", "biocatalys", "enzyme", "catalytic activity", "catalytic performance", "metal-organic framework", "mof", "zeolite", "catalysis"],
        "Low-carbon energy": ["renewable energy", "solar", "wind energy", "hydrogen", "fuel cell", "battery", "energy storage", "clean energy", "low-carbon energy", "photovoltaic", "biomass", "geothermal", "tidal", "nuclear", "electrolysis", "energy conversion", "energy efficiency", "carbon capture", "ccs", "ccus", "carbon sequestration"],
        "Low-carbon chemical engineering": ["chemical engineering", "chemical process", "reaction engineering", "separation", "distillation", "absorption", "adsorption", "membrane", "reactor", "process design", "chemical production", "green chemistry", "sustainable chemistry"],
        "Carbon economics and policy": ["carbon economic", "carbon policy", "carbon market", "carbon trading", "carbon tax", "carbon pricing", "emission trading", "climate policy", "carbon footprint", "life cycle assessment", "lca", "carbon accounting", "carbon neutrality", "net zero", "decarbonization", "carbon reduction"],
    }

    scores = {}
    for category, rules in CATEGORY_RULES.items():
        score = 0
        for rule in rules:
            # Title match (weight 3)
            if rule in text:
                score += 3
            # Keyword match (weight 2)
            if rule in kw_text:
                score += 2
            # Abstract match (weight 1)
            if rule in abstract_text:
                score += 1
        scores[category] = score

    # Sort by score, take top 3 with threshold
    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    result = []
    top_score = sorted_cats[0][1] if sorted_cats else 0
    for cat, score in sorted_cats:
        if score == 0:
            break
        if len(result) == 0:
            result.append(cat)
        elif score >= top_score / 3 and len(result) < 3:
            result.append(cat)
        else:
            break

    return result

def scrape_article(doi):
    """Scrape a single article page and return structured data."""
    url = f"{BASE_URL}/article/{doi}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract metadata
    article = {
        "doi": get_meta(soup, "citation_doi") or doi,
        "title": get_meta(soup, "citation_title"),
        "authors": get_meta_all(soup, "citation_author"),
        "keywords": get_meta_all(soup, "citation_keywords"),
        "abstract": get_meta(soup, "og:description") or get_meta(soup, "citation_abstract"),
        "volume": get_meta(soup, "citation_volume"),
        "issue": get_meta(soup, "citation_issue"),
        "firstpage": get_meta(soup, "citation_firstpage"),
        "lastpage": get_meta(soup, "citation_lastpage"),
        "year": None,  # Will be set from DOI
        "publication_date": get_meta(soup, "citation_publication_date"),
        "online_date": get_meta(soup, "citation_online_date"),
        "publisher": get_meta(soup, "citation_publisher"),
        "issn": get_meta(soup, "citation_issn"),
        "article_type": extract_article_type(soup),
        "url": url,
        "pdf": get_meta(soup, "citation_pdf_url"),
    }

    # Clean abstract
    if article["abstract"]:
        article["abstract"] = re.sub(r'<[^>]+>', '', article["abstract"]).strip()

    # Extract year from DOI
    match = re.search(r'CF\.(\d{4})\.', doi)
    if match:
        article["year"] = int(match.group(1))

    # Assign research areas
    article["research_area"] = extract_research_area(
        article["title"], article["keywords"], article["abstract"]
    )

    return article

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load DOI mapping
    mapping_file = OUTPUT_DIR / "doi_volume_issue_mapping.json"
    with open(mapping_file, "r", encoding="utf-8") as f:
        doi_mapping = json.load(f)

    # Filter to only 2024-2026 DOIs
    dois_2024_2026 = [d for d in sorted(doi_mapping.keys()) if re.match(r'10\.26599/CF\.(2024|2025|2026)\.', d)]
    print(f"Articles to scrape: {len(dois_2024_2026)}")

    results = []
    for i, doi in enumerate(dois_2024_2026):
        print(f"[{i+1}/{len(dois_2024_2026)}] {doi}...", end=" ", flush=True)
        try:
            details = scrape_article(doi)
            # Override volume/issue from mapping
            if doi in doi_mapping:
                details["volume"] = doi_mapping[doi]["volume"]
                details["issue"] = doi_mapping[doi]["issue"]
            results.append(details)
            print(f"OK - {details.get('article_type', 'N/A')} - {details.get('title', '')[:50]}...")
        except Exception as e:
            print(f"ERROR: {e}")
        time.sleep(0.3)  # polite delay

    # Save results
    output_file = OUTPUT_DIR / "articles.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Done! Scraped {len(results)} / {len(dois_2024_2026)} articles")
    print(f"Saved to: {output_file}")

    # Print summary by year
    from collections import Counter
    years = Counter(a["year"] for a in results)
    print(f"\nArticles by year: {dict(sorted(years.items()))}")

    # Print research area summary
    areas = Counter()
    for a in results:
        for area in a.get("research_area", []):
            areas[area] += 1
    print(f"\nArticles by research area:")
    for area, count in areas.most_common():
        print(f"  {area}: {count}")

    return results

if __name__ == "__main__":
    main()
