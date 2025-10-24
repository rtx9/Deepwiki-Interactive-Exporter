import os
import sys
import time
import queue
import hashlib
from urllib.parse import urlparse, urljoin, urldefrag

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from markdownify import markdownify as html_to_md
import argparse


def input_nonempty(prompt: str) -> str:
    while True:
        v = input(prompt).strip()
        if v:
            return v


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def sanitize_filename(name: str) -> str:
    return name.replace("\\", "_").replace("/", "_")


def url_to_filepath(base_output: str, url: str, md: bool = False) -> str:
    p = urlparse(url)
    path = p.path
    if not path or path.endswith("/"):
        path = path + ("index.md" if md else "index.html")
    if path.startswith("/"):
        path = path[1:]
    if not os.path.splitext(path)[1]:
        path = path + (".md" if md else ".html")
    full_path = os.path.join(base_output, path)
    ensure_dir(os.path.dirname(full_path))
    return full_path


def same_origin(u1: str, u2: str) -> bool:
    p1, p2 = urlparse(u1), urlparse(u2)
    return (p1.scheme, p1.hostname, p1.port or (443 if p1.scheme == "https" else 80)) == (
        p2.scheme, p2.hostname, p2.port or (443 if p2.scheme == "https" else 80)
    )


def within_path(root: str, target: str) -> bool:
    rp, tp = urlparse(root).path.rstrip("/"), urlparse(target).path
    return tp.startswith(rp)


def normalize_link(current_url: str, href: str) -> str | None:
    if not href:
        return None
    href = href.strip()
    if href.startswith("mailto:") or href.startswith("javascript:") or href.startswith("#"):
        return None
    absu = urljoin(current_url, href)
    absu, _ = urldefrag(absu)
    return absu


def build_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def fetch(url: str, session: requests.Session, timeout: int = 20) -> tuple[int | None, str | None, str | None]:
    try:
        r = session.get(url, timeout=timeout, headers={"User-Agent": "DeepWikiExporter/2.0"})
        ctype = r.headers.get("Content-Type", "")
        return r.status_code, ctype, r.text if "html" in ctype.lower() else None
    except requests.RequestException:
        return None, None, None

def extract_mermaid_blocks(soup: BeautifulSoup) -> list[tuple[str, str]]:
    blocks = []
    idx = 0
    for el in soup.find_all(["div", "pre"]):
        cls = " ".join(el.get("class", [])).lower()
        is_mermaid = "mermaid" in cls or (el.name == "pre" and el.code and "language-mermaid" in " ".join(el.code.get("class", [])).lower())
        if is_mermaid:
            text = el.get_text("\n")
            token = f"__MERMAID_BLOCK_{idx}__"
            placeholder = soup.new_string(token)
            el.replace_with(placeholder)
            blocks.append((token, text))
            idx += 1
    return blocks


def download_asset(session: requests.Session, asset_url: str, page_md_path: str, out_base: str) -> str | None:
    try:
        r = session.get(asset_url, timeout=20, stream=True, headers={"User-Agent": "DeepWikiExporter/2.0"})
        if r.status_code != 200:
            return None
        page_dir = os.path.dirname(page_md_path)
        assets_dir = os.path.join(page_dir, "assets")
        ensure_dir(assets_dir)
        name = sanitize_filename(os.path.basename(urlparse(asset_url).path) or hashlib.sha1(asset_url.encode()).hexdigest())
        local_path = os.path.join(assets_dir, name)
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
        rel = os.path.relpath(local_path, page_dir).replace(os.sep, "/")
        return rel
    except requests.RequestException:
        return None


def html_to_markdown_document(html: str, page_url: str, root_url: str, out_base: str, session: requests.Session, page_md_path: str, download_assets: bool) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    mermaid_blocks = extract_mermaid_blocks(soup)
    # Rewrite internal anchors to relative .md paths
    for a in soup.find_all("a"):
        href = a.get("href")
        nu = normalize_link(page_url, href)
        if not nu:
            continue
        if same_origin(root_url, nu) and within_path(root_url, nu):
            target_md = url_to_filepath(out_base, nu, md=True)
            rel = os.path.relpath(target_md, os.path.dirname(page_md_path)).replace(os.sep, "/")
            a["href"] = rel
    for img in soup.find_all("img"):
        src = img.get("src")
        nu = normalize_link(page_url, src)
        if not nu:
            continue
        if same_origin(root_url, nu) and within_path(root_url, nu) and download_assets:
            rel = download_asset(session, nu, page_md_path, out_base)
            if rel:
                img["src"] = rel
    md = html_to_md(str(soup), heading_style="ATX", strip=['script', 'style'])
    if title:
        md = f"# {title}\n\n" + md
    for token, code in mermaid_blocks:
        fenced = f"```mermaid\n{code.strip()}\n```"
        md = md.replace(token, fenced)
    return md


def crawl(root_url: str, out_dir: str, max_pages: int | None = None, delay: float = 0.0, download_assets: bool = True) -> None:
    parsed = urlparse(root_url)
    if not parsed.scheme.startswith("http"):
        raise ValueError("URL must start with http or https")
    ensure_dir(out_dir)
    session = build_session()
    seen: set[str] = set()
    q: queue.Queue[str] = queue.Queue()
    q.put(root_url)
    total = 0
    pbar = tqdm(disable=False, unit="page")
    try:
        while not q.empty():
            if max_pages is not None and total >= max_pages:
                break
            url = q.get()
            if url in seen:
                continue
            seen.add(url)
            status, ctype, html = fetch(url, session)
            if status != 200 or not html:
                pbar.write(f"skip {url} ({status})")
                continue
            md_path = url_to_filepath(out_dir, url, md=True)
            md_text = html_to_markdown_document(html, url, root_url, out_dir, session, md_path, download_assets)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_text)
            total += 1
            pbar.update(1)
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a"):
                nu = normalize_link(url, a.get("href"))
                if not nu:
                    continue
                if same_origin(root_url, nu) and within_path(root_url, nu) and nu not in seen:
                    q.put(nu)
            if delay > 0:
                time.sleep(delay)
    finally:
        pbar.close()


def main():
    parser = argparse.ArgumentParser(description="Export a DeepWiki space to Markdown with folder nesting and mermaid diagrams.")
    parser.add_argument("--url", dest="url", help="DeepWiki space root URL, e.g. https://deepwiki.com/example/example")
    parser.add_argument("--out", dest="out_dir", help="Output directory (will be created if missing)")
    parser.add_argument("--max-pages", dest="max_pages", type=int, default=None, help="Maximum number of pages to crawl")
    parser.add_argument("--delay", dest="delay", type=float, default=0.0, help="Delay seconds between requests (politeness)")
    parser.add_argument("--no-assets", dest="download_assets", action="store_false", help="Do not download page assets (images/CSS/JS)")
    args = parser.parse_args()

    print("DeepWiki Markdown Exporter")
    print("Press Enter to accept defaults in brackets.")

    url = args.url or input_nonempty("Enter DeepWiki space URL (e.g., https://deepwiki.com/example/example): ")
    default_out = os.getcwd()
    out_dir = args.out_dir or (input(f"Output directory [{default_out}]: ").strip() or default_out)

    if args.max_pages is not None:
        max_pages = args.max_pages
    else:
        mp = input("Optional max pages (empty for no limit): ").strip()
        max_pages = int(mp) if mp.isdigit() else None

    if args.delay is not None and args.url is not None and args.out_dir is not None:
        delay = args.delay
    else:
        d = input("Optional polite delay seconds between requests (e.g., 0.25) [0]: ").strip()
        try:
            delay = float(d) if d else 0.0
        except ValueError:
            delay = 0.0

    if args.url and args.out_dir is not None:
        download_assets = args.download_assets if hasattr(args, 'download_assets') else True
    else:
        da = input("Download assets (images/CSS/JS) [Y/n]: ").strip().lower()
        download_assets = False if da == "n" else True

    crawl(url, out_dir, max_pages=max_pages, delay=delay, download_assets=download_assets)
    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in {"-h", "--help"}:
        print("Usage: python deepwiki_exporter.py\nExports DeepWiki space to Markdown with folder nesting.")
        sys.exit(0)
    main()
