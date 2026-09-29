"""
LLM and Synthesis Provider.
Supports:
1. Google Gemini (via google.genai SDK)
2. OpenAI / Groq / OpenRouter / DeepSeek (via openai SDK)
3. Local/Extractive Research Synthesizer fallback (Zero API keys required!)
"""

import os
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()


def get_configured_llm():
    """Check what LLM provider is available."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")

    if gemini_key:
        return "gemini"
    elif openai_key:
        return "openai"
    return "heuristic"


def generate_search_queries(topic: str) -> List[str]:
    """
    Generate 2-3 focused, short search queries for the research topic.
    """
    provider = get_configured_llm()

    if provider == "gemini":
        try:
            from google import genai
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
            prompt = (
                f"You are a web research assistant. The user wants to research: '{topic}'.\n"
                "Generate 3 short, specific search queries (maximum 5 words each) to find the best articles.\n"
                "Return ONLY the 3 queries, one per line, with no quotes or numbers."
            )
            response = client.models.generate_content(model=model_name, contents=prompt)
            lines = [l.strip().lstrip("-*123456789. \t\"'") for l in response.text.strip().split("\n") if l.strip()]
            valid_queries = [q for q in lines if 3 <= len(q) <= 60]
            if valid_queries:
                return valid_queries[:3]
        except Exception:
            pass

    elif provider == "openai":
        try:
            import openai
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL")
            client = openai.OpenAI(api_key=api_key, base_url=base_url if base_url else None)
            model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            prompt = (
                f"The user wants to research: '{topic}'.\n"
                "Generate 3 short search queries (max 5 words each) for search engines.\n"
                "Return ONLY the 3 queries, one per line."
            )
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100
            )
            text = response.choices[0].message.content.strip()
            lines = [l.strip().lstrip("-*123456789. \t\"'") for l in text.split("\n") if l.strip()]
            valid_queries = [q for q in lines if 3 <= len(q) <= 60]
            if valid_queries:
                return valid_queries[:3]
        except Exception:
            pass

    # Clean concise fallback queries
    return [
        topic.strip(),
        f"{topic} overview",
        f"{topic} latest developments"
    ]


def synthesize_research(topic: str, sources_data: List[Dict[str, Any]]) -> str:
    """
    Synthesize raw search snippets and scraped articles into an authoritative research report.
    """
    provider = get_configured_llm()

    # Prepare context text
    context_blocks = []
    for idx, item in enumerate(sources_data, 1):
        title = item.get("title", "Untitled")
        url = item.get("href", "")
        body = item.get("body", "")
        content = item.get("scraped_content") or body
        context_blocks.append(
            f"--- SOURCE [{idx}] ---\n"
            f"Title: {title}\n"
            f"URL: {url}\n"
            f"Content Summary / Excerpt:\n{content[:1500]}\n"
        )

    context_str = "\n".join(context_blocks)

    # 1. Try Gemini
    if provider == "gemini":
        try:
            from google import genai
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
            user_prompt = f"""You are a professional research agent. Synthesize a comprehensive research report on the topic: '{topic}'.

Base your report strictly on the gathered web intelligence below:
{context_str}

Format the report in clean Markdown using these sections:
# Research Report: {topic}

## 1. Executive Summary
(A clear, high-level summary of the topic and main findings)

## 2. Key Findings & Core Takeaways
(Bullet points with facts, figures, discoveries, or critical milestones found in the research)

## 3. In-Depth Analysis & Insights
(Detailed discussion of concepts, real-world context, and technical insights)

## 4. Challenges & Future Outlook
(Known limitations, unanswered questions, and future directions)

## 5. Sources & Citations
(Numbered list of all sources with markdown links [Title](URL))
"""
            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt
            )
            if response.text and len(response.text.strip()) > 100:
                return response.text.strip()
        except Exception as e:
            print(f"[!] Gemini synthesis unavailable ({e}), trying alternative...")

    # 2. Try OpenAI / Groq / OpenAI-compatible
    if os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY"):
        try:
            import openai
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL")
            client = openai.OpenAI(api_key=api_key, base_url=base_url if base_url else None)
            model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            user_prompt = f"""Synthesize comprehensive research on the topic: '{topic}'.

Data gathered:
{context_str}

Format the report in clean Markdown with:
# Research Report: {topic}
## 1. Executive Summary
## 2. Key Findings & Core Takeaways
## 3. In-Depth Analysis & Insights
## 4. Challenges & Future Outlook
## 5. Sources & Citations (with links)
"""
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a professional research agent."},
                    {"role": "user", "content": user_prompt}
                ]
            )
            content = response.choices[0].message.content.strip()
            if content and len(content) > 100:
                return content
        except Exception as e:
            print(f"[!] OpenAI-compatible synthesis unavailable ({e}), using heuristic engine...")

    # 3. Built-in Extractive / Heuristic Research Synthesizer (Guaranteed 100% offline & zero cost)
    return heuristic_synthesizer(topic, sources_data)


def heuristic_synthesizer(topic: str, sources_data: List[Dict[str, Any]]) -> str:
    """
    Extractive research synthesizer that extracts key points, paragraphs, and statistics
    to build a structured research report without external API keys.
    """
    lines = [
        f"# Research Report: {topic}",
        "",
        "> *Generated by Web Search Agent (Local Research Synthesis Engine)*",
        "",
        "## 1. Executive Summary",
        f"This report synthesizes gathered web intelligence on **{topic}**. The research agent analyzed multiple web sources and extracted key findings, developments, and perspectives to provide an integrated overview.",
        ""
    ]

    # Collect key paragraphs and bullets
    findings = []
    detailed_sections = []
    sources_list = []

    for idx, item in enumerate(sources_data, 1):
        title = item.get("title", f"Source {idx}")
        url = item.get("href", "#")
        body = item.get("body", "").strip()
        scraped = item.get("scraped_content", "").strip()

        sources_list.append(f"{idx}. [{title}]({url})")

        # Pick key facts or sentences
        text_pool = scraped if scraped else body
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text_pool) if len(s.strip()) > 35]

        for s in sentences[:3]:
            if any(term in s.lower() for term in topic.lower().split()[:2]) or any(c.isdigit() for c in s):
                if s not in findings:
                    findings.append(s)

        # Build in-depth section from scraped content
        if scraped:
            sample_paras = [p.strip() for p in scraped.split("\n\n") if len(p.strip()) > 60]
            if sample_paras:
                detailed_sections.append(f"### Insights from: *{title}*\n\n" + sample_paras[0])

    lines.append("## 2. Key Findings & Core Takeaways")
    if findings:
        for f in findings[:8]:
            lines.append(f"- {f}")
    else:
        for item in sources_data[:5]:
            lines.append(f"- **{item.get('title')}**: {item.get('body')}")
    lines.append("")

    lines.append("## 3. In-Depth Analysis & Insights")
    if detailed_sections:
        lines.extend(detailed_sections[:5])
        lines.append("")
    else:
        for item in sources_data[:4]:
            lines.append(f"### {item.get('title')}")
            lines.append(f"{item.get('body')}")
            lines.append("")

    lines.append("## 4. Challenges & Future Outlook")
    lines.append(f"Ongoing advancements in **{topic}** demonstrate active development and significant interest across research and industry sectors. Continued monitoring of source publications and technological deployments will provide further clarity.")
    lines.append("")

    lines.append("## 5. Sources & References")
    for s in sources_list:
        lines.append(s)

    return "\n".join(lines)
