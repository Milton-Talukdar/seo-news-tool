"""
Fetch SEO news from RSS feeds.
Handles parsing, deduplication, and basic relevance scoring.
"""

import feedparser
import yaml
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from typing import List, Dict
import hashlib


def load_config(path: str = "config.yaml") -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_feed(url: str, name: str, max_articles: int = 5) -> List[Dict]:
    """Fetch and parse a single RSS feed."""
    try:
        feed = feedparser.parse(url)
        articles = []
        
        for entry in feed.entries[:max_articles]:
            # Parse published date
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            else:
                published = datetime.now(timezone.utc)
            
            # Skip articles older than 7 days
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            if published < cutoff:
                continue
            
            article = {
                "title": getattr(entry, "title", "Untitled"),
                "link": getattr(entry, "link", ""),
                "summary": getattr(entry, "summary", getattr(entry, "description", "")),
                "published": published.isoformat(),
                "source": name,
                "author": getattr(entry, "author", name),
            }
            
            # Create unique hash for deduplication
            article["hash"] = hashlib.md5(
                f"{article['title']}{article['link']}".encode()
            ).hexdigest()[:12]
            
            articles.append(article)
        
        return articles
    except Exception as e:
        print(f"  ⚠️  Failed to fetch {name}: {e}")
        return []


def score_relevance(article: Dict, keywords: List[str]) -> int:
    """Score article relevance based on keyword matches in title + summary."""
    text = f"{article['title']} {article['summary']}".lower()
    score = 0
    matched = []
    
    for kw in keywords:
        if kw.lower() in text:
            score += 1
            matched.append(kw)
    
    return score, matched


def fetch_all_news(config: Dict) -> List[Dict]:
    """Fetch news from all configured sources."""
    sources = config.get("sources", [])
    keywords = config.get("relevance_keywords", [])
    max_per_source = config.get("articles_per_source", 5)
    
    all_articles = []
    seen_hashes = set()
    
    print(f"📡 Fetching from {len(sources)} sources...")
    
    for source in sources:
        name = source["name"]
        url = source["url"]
        priority = source.get("priority", "medium")
        
        print(f"  → {name}...", end=" ")
        articles = fetch_feed(url, name, max_per_source)
        print(f"{len(articles)} articles")
        
        for article in articles:
            # Deduplicate
            if article["hash"] in seen_hashes:
                continue
            seen_hashes.add(article["hash"])
            
            # Score relevance
            score, matched = score_relevance(article, keywords)
            article["relevance_score"] = score
            article["matched_keywords"] = matched
            article["priority"] = priority
            
            all_articles.append(article)
    
    # Sort by relevance score (desc), then by date (desc)
    all_articles.sort(key=lambda x: (-x["relevance_score"], x["published"]), reverse=False)
    
    print(f"\n✅ Total unique articles: {len(all_articles)}")
    return all_articles


if __name__ == "__main__":
    config = load_config()
    articles = fetch_all_news(config)
    
    # Show top 5 most relevant
    print("\n🏆 Top 5 most relevant articles:")
    for a in articles[:5]:
        print(f"  [{a['relevance_score']}] {a['title'][:70]}... ({a['source']})")
