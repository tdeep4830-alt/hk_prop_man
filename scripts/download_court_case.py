"""
HK Judiciary Court Case Scraper
================================
Downloads Building Management cases from the HK Judiciary Legal Reference System.

URL pattern:
  Frame page: https://legalref.judiciary.hk/lrs/common/ju/ju_frame.jsp?DIS={DIS}&currpage=T
  Body page:  https://legalref.judiciary.hk/lrs/common/ju/ju_body.jsp?DIS={DIS}&currpage=T

Logic:
  1. Fetch the body page for a given DIS number
  2. Extract the first ~50 lines of visible text
  3. Check if it contains "Building Management Application" OR "建築物管理申請"
  4. If yes → save the full cleaned text as a .txt file in rag_data/Count_case/scraped/
  5. If no  → skip (not a BM case)

Usage:
  # Single case
  python scripts/download_court_case.py --dis 71992

  # Range of DIS numbers
  python scripts/download_court_case.py --start 60000 --end 80000

  # From a file containing one DIS number per line
  python scripts/download_court_case.py --file scripts/dis_numbers.txt

  # Dry-run (check without saving)
  python scripts/download_court_case.py --start 70000 --end 71000 --dry-run
"""

import argparse
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ─── Config ───────────────────────────────────────────────────────────────────

BASE_URL    = "https://legalref.judiciary.hk/lrs/common/ju/ju_body.jsp"
OUTPUT_DIR  = Path(__file__).parent.parent / "rag_data" / "Count_case" / "scraped"
DELAY_SEC   = 1.5          # polite delay between requests
TIMEOUT_SEC = 20
HEADERS     = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PropManAI-Scraper/1.0; "
        "research use; contact: admin@propmanai.hk)"
    ),
    "Accept":          "text/html,application/xhtml+xml",
    "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
}

# Keywords that confirm this is a Building Management case
BM_KEYWORDS_EN = [
    "Building Management Application",
    "Building Management Ordinance",
    "Lands Tribunal",
]
BM_KEYWORDS_ZH = [
    "建築物管理申請",
    "建築物管理條例",
    "土地審裁處",
]
ALL_BM_KEYWORDS = BM_KEYWORDS_EN + BM_KEYWORDS_ZH

# Regex to extract case reference (LDBM / CACV / HCMP etc.)
CASE_REF_RE = re.compile(
    r"\b(LDBM|CACV|HCMP|HCA|HCAL|HCMC|CACV)\s*\d+[\w/]*",
    re.IGNORECASE,
)


# ─── Core functions ───────────────────────────────────────────────────────────

def fetch_body(dis: int, session: requests.Session) -> str | None:
    """Fetch the HTML body of a judgment. Returns None on HTTP error."""
    url = f"{BASE_URL}?DIS={dis}&currpage=T"
    try:
        resp = session.get(url, timeout=TIMEOUT_SEC, headers=HEADERS)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text
    except requests.RequestException as e:
        print(f"  [WARN] DIS {dis}: request failed — {e}", file=sys.stderr)
        return None


def extract_text(html: str) -> str:
    """Parse HTML and return clean plain text with one paragraph per line.

    Strategy: replace <br> with newline, then extract text from each <p>
    individually so numbered paragraphs and headings land on their own lines.
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "meta", "link"]):
        tag.decompose()

    # Replace <br> tags with newline placeholder before text extraction
    for br in soup.find_all("br"):
        br.replace_with("\n")

    lines = []
    # Walk every <p> — each paragraph becomes one line
    for p in soup.find_all("p"):
        t = p.get_text(separator=" ", strip=True)
        t = t.replace("\xa0", " ").strip()
        if t:
            lines.append(t)

    # Also grab text from custom tags (parties, coram, date) that are not <p>
    for tag_name in ["parties", "coram", "date"]:
        for elem in soup.find_all(tag_name):
            # Only pick up direct text not already captured via <p> children
            direct = "".join(
                str(c) for c in elem.children
                if isinstance(c, str)
            ).strip().replace("\xa0", " ")
            if direct:
                lines.append(direct)

    return "\n".join(lines)


def is_bm_case(text: str, preview_lines: int = 60) -> bool:
    """Return True if the first `preview_lines` lines contain a BM keyword."""
    head = "\n".join(text.splitlines()[:preview_lines])
    return any(kw.lower() in head.lower() for kw in ALL_BM_KEYWORDS)


def extract_case_ref(text: str) -> str | None:
    """Try to extract the case reference (e.g. LDBM000110_2009) from the text."""
    m = CASE_REF_RE.search(text[:500])
    if m:
        # Normalise: remove spaces, keep alphanumeric + /
        return m.group(0).replace(" ", "").replace("/", "_")
    return None


def save_case(dis: int, case_ref: str | None, text: str) -> Path:
    """Write case text to OUTPUT_DIR. Returns the saved file path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = case_ref if case_ref else f"DIS{dis}"
    out_path = OUTPUT_DIR / f"{stem}.txt"
    # Avoid overwriting with empty content
    out_path.write_text(text, encoding="utf-8")
    return out_path


def process_dis(
    dis: int,
    session: requests.Session,
    dry_run: bool = False,
    verbose: bool = True,
) -> bool:
    """
    Process one DIS number.
    Returns True if it was a BM case (saved or would be saved in dry-run).
    """
    html = fetch_body(dis, session)
    if html is None:
        if verbose:
            print(f"  DIS {dis:>7}: ✗ (no response / 404)")
        return False

    text = extract_text(html)
    if not text.strip():
        if verbose:
            print(f"  DIS {dis:>7}: ✗ (empty content)")
        return False

    if not is_bm_case(text):
        if verbose:
            print(f"  DIS {dis:>7}: — (not a BM case)")
        return False

    case_ref = extract_case_ref(text)
    label    = case_ref or f"DIS{dis}"

    if dry_run:
        print(f"  DIS {dis:>7}: ✓ BM case [{label}] — DRY RUN, not saved")
        return True

    out_path = save_case(dis, case_ref, text)
    print(f"  DIS {dis:>7}: ✓ BM case [{label}] → {out_path.name}")
    return True


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download HK Building Management court cases from the Judiciary LRS."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dis",   type=int,        help="Single DIS number")
    group.add_argument("--start", type=int,        help="Start of DIS range (inclusive)")
    group.add_argument("--file",  type=Path,       help="Text file with one DIS per line")

    parser.add_argument("--end",     type=int,   default=None,
                        help="End of DIS range (inclusive, used with --start)")
    parser.add_argument("--delay",   type=float, default=DELAY_SEC,
                        help=f"Seconds between requests (default {DELAY_SEC})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Check cases without saving files")
    parser.add_argument("--quiet",   action="store_true",
                        help="Only print BM cases found")
    args = parser.parse_args()

    # Build DIS list
    if args.dis:
        dis_list = [args.dis]
    elif args.start is not None:
        end = args.end if args.end is not None else args.start
        if end < args.start:
            parser.error("--end must be >= --start")
        dis_list = list(range(args.start, end + 1))
    else:
        path = args.file
        if not path.exists():
            parser.error(f"File not found: {path}")
        dis_list = [
            int(line.strip())
            for line in path.read_text().splitlines()
            if line.strip().isdigit()
        ]

    verbose = not args.quiet
    total   = len(dis_list)
    found   = 0

    print(f"Scanning {total} DIS number(s)…")
    print(f"Output directory: {OUTPUT_DIR}")
    if args.dry_run:
        print("DRY RUN — no files will be written\n")

    session = requests.Session()
    session.headers.update(HEADERS)

    for i, dis in enumerate(dis_list, 1):
        if verbose and total > 1:
            print(f"[{i:>5}/{total}] ", end="", flush=True)

        hit = process_dis(
            dis,
            session,
            dry_run=args.dry_run,
            verbose=verbose or args.quiet is False,
        )
        if hit:
            found += 1

        if i < total:
            time.sleep(args.delay)

    print(f"\nDone. Found {found} BM case(s) out of {total} DIS numbers scanned.")
    if not args.dry_run and found:
        print(f"Files saved to: {OUTPUT_DIR}")
        print(
            "\nNext step — re-run ingestion to index the new cases:\n"
            "  docker compose exec api python scripts/run_ingestion.py"
        )


if __name__ == "__main__":
    main()
