# Deepwiki-Interactive-Exporter
A quick single file python executable, which let's you export deepwiki's documentation as markdown, with nested folders.
Export any public DeepWiki space to clean Markdown with nested folders, preserved Mermaid diagrams, and offline-friendly internal links.

## Features
- Markdown output with correct headings
- Folder nesting mirrors URL paths
- Mermaid diagrams preserved as fenced code blocks
- Internal links rewritten to relative `.md`
- Optional asset download per page (images/CSS/JS)
- Robust retries and polite crawling delay
- Interactive prompts or fully non-interactive CLI flags

## Requirements
- Python 3.9+ (tested on Windows with Python 3.13)

## Installation
1. Clone the repository
   ```bash
   git clone https://github.com/rtx9/Deepwiki-Interactive-Exporter.git
   cd Deepwiki-Interactive-Exporter
   ```
2. Create a virtual environment
   - Windows (PowerShell):
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - macOS/Linux (bash):
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

## How to Use
1. Decide the DeepWiki space URL (e.g., `https://deepwiki.com/example/example`).
2. Choose an output directory (it will be created if missing).
3. Run one of the following:
   - Interactive mode (prompts for options):
     ```bash
     python deepwiki_exporter.py
     ```
   - Non-interactive mode (exact flags):
     ```bash
     python deepwiki_exporter.py --url https://deepwiki.com/teableio/teable --out ./export --delay 0.25
     ```

## CLI Flags
- `--url` string
  - DeepWiki space root URL
  - Example: `--url https://deepwiki.com/teableio/teable`
- `--out` string
  - Output directory for exported Markdown
  - Example: `--out ./export`
- `--max-pages` integer
  - Maximum number of pages to crawl (omit for full export)
  - Example: `--max-pages 50`
- `--delay` float
  - Polite delay (seconds) between requests
  - Example: `--delay 0.25`
- `--no-assets`
  - Do not download assets (images/CSS/JS). By default, assets are downloaded.
  - Example: `--no-assets`

## Examples
- Minimal interactive run
  ```bash
  python deepwiki_exporter.py
  ```
- Export entire space to `./export` with a polite delay
  ```bash
  python deepwiki_exporter.py --url https://deepwiki.com/example/example o --out ./export --delay 0.25
  ```
- Quick sample (limit to 10 pages)
  ```bash
  python deepwiki_exporter.py --url https://deepwiki.com/example/example --out ./export --max-pages 10 --delay 0.25
  ```
- Skip asset downloads
  ```bash
  python deepwiki_exporter.py --url https://deepwiki.com/example/example --out ./export --no-assets
  ```

## Notes
- The crawler stays on the same origin and within the given path prefix.
- Mermaid diagrams are preserved as fenced `mermaid` blocks.
- Internal links between pages are rewritten to relative `.md` links.

---

If you find this useful, please give the repo a star! ★

[Star this repo](https://github.com/rtx9/Deepwiki-Interactive-Exporter.git)
