"""
Main Research Agent class.
Coordinates query formulation, web search, page scraping, synthesis, and file saving.
"""

import os
import re
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

from searcher import multi_query_search, search_web
from scraper import scrape_url
from llm_client import generate_search_queries, synthesize_research


def slugify(text: str) -> str:
    """Create a safe filename slug from arbitrary text."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")[:40] or "research"


class ResearchAgent:
    """Autonomous web search and research agent."""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def run(
        self,
        topic: str,
        output_file: Optional[str] = None,
        max_search_results: int = 6,
        scrape_top_n: int = 3,
        callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Execute full research workflow for a topic and save the report to file.

        Args:
            topic: The subject to research.
            output_file: Optional explicit file path to save the report.
            max_search_results: Maximum total search results to collect.
            scrape_top_n: Number of top webpages to read deeply.
            callback: Optional status update callable `callback(step, message)`.

        Returns:
            Dict containing:
                - "topic": Topic researched
                - "file_path": Saved report path
                - "report": Complete markdown content
                - "sources_count": Number of sources used
                - "queries": Search queries used
        """
        def notify(step: int, msg: str):
            if callback:
                callback(step, msg)
            else:
                print(f"[{step}/4] {msg}")

        # 1. Generate search queries
        notify(1, f"Analyzing topic and generating search queries for: '{topic}'...")
        queries = generate_search_queries(topic)

        # 2. Search web
        notify(2, f"Searching the web across {len(queries)} queries...")
        search_results = multi_query_search(queries, max_results_per_query=3)

        if not search_results:
            notify(2, "Refining search with single direct query...")
            search_results = search_web(topic, max_results=max_search_results)

        # Truncate to max_search_results
        selected_sources = search_results[:max_search_results]

        # 3. Scrape top webpages
        notify(3, f"Extracting deep content from top {min(scrape_top_n, len(selected_sources))} websites...")
        scraped_count = 0
        for i, item in enumerate(selected_sources):
            if i < scrape_top_n:
                content = scrape_url(item["href"])
                if content:
                    item["scraped_content"] = content
                    scraped_count += 1
                else:
                    item["scraped_content"] = item["body"]
            else:
                item["scraped_content"] = item["body"]

        # 4. Synthesize research report
        notify(4, "Synthesizing research into comprehensive report...")
        report_content = synthesize_research(topic, selected_sources)

        # 5. Determine target file path and save
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"research_{slugify(topic)}_{timestamp}.md"
            target_path = os.path.join(self.output_dir, filename)
        else:
            target_path = output_file
            # Ensure parent directories exist
            parent = os.path.dirname(target_path)
            if parent:
                os.makedirs(parent, exist_ok=True)

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        return {
            "topic": topic,
            "file_path": os.path.abspath(target_path),
            "report": report_content,
            "sources_count": len(selected_sources),
            "scraped_count": scraped_count,
            "queries": queries
        }
