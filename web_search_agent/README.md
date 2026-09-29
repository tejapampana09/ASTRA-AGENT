# 🔍 Web Search & Research Agent

A simple, fast autonomous research agent that searches the web, deeply inspects top articles, synthesizes the findings, and automatically saves a comprehensive report into a file.

## ✨ Features

- **Autonomous Multi-Query Search**: Breaks down any research topic into multiple targeted search queries.
- **Deep Web Scraping**: Fetches and extracts clean article content from top search results, filtering out ads and navigation noise.
- **Zero-Config Ready (Works 100% Free)**: Uses DuckDuckGo search (no API keys required) and includes a local heuristic synthesis engine.
- **Optional LLM Power**: Supports **Google Gemini** (`gemini-3.8-flash`) or any **OpenAI-compatible API** (Groq, OpenRouter, DeepSeek, Ollama) if you provide API keys in `.env`.
- **Automatic File Saving**: Generates structured Markdown reports saved directly to the `reports/` folder or a custom path you specify.

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Keys (Optional)
If you want AI synthesis with Gemini or OpenAI/Groq, add your key to `.env`:
```ini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.8-flash

# Or OpenAI / Groq:
# OPENAI_API_KEY=your_key_here
```
*(If no API keys are provided or quota is exceeded, the agent automatically uses its built-in local research engine!)*

---

## 💻 Usage

### Interactive Mode (Just run and type your topic!)
```bash
python main.py
```
It will prompt:
```
🔍 Enter what you want to research:
```

### CLI One-Liner
```bash
python main.py --topic "Solid State Battery advancements in 2026"
```

### Save to a Custom File Name
```bash
python main.py --topic "CRISPR gene therapy latest approvals" --output my_crispr_report.md
```

### Advanced Flags
- `--topic` / `-q`: Research prompt or question.
- `--output` / `-o`: Specific file path where the report is saved.
- `--max-sources` / `-n`: Total number of search results to gather (default: 6).
- `--scrape-top`: How many top websites to scrape full text from (default: 3).

---

## 📁 Project Structure

```
web_search_agent/
│── main.py            # Interactive CLI & entrypoint
│── agent.py           # Research orchestrator workflow
│── searcher.py        # DuckDuckGo search integration
│── scraper.py         # Web page extraction & cleaning (BeautifulSoup)
│── llm_client.py      # Multi-model synthesis (Gemini, OpenAI, Heuristic fallback)
│── requirements.txt   # Python dependencies
│── .env               # API keys (optional)
│── .env.example       # Template environment variables
└── reports/           # Saved research reports (auto-created)
```
