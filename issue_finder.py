#!/usr/bin/env python3
"""
Usage:
export GITHUB_TOKEN=ghp_...
python github_issue_pr_miner.py \
  --out prs.csv \
  --min-stars 50 --max-repo-mb 9.9 \
  --min-files 5 --max-files 10 \
  --min-lines 80 --max-lines 1000 \
  --max-repos 1000 --max-issues 1000 \
  --autosave-every 20 \
  --repo-name falcony/falcon \
  --verify-clone-size false

Requirements:
- Python 3.9+
- pip install requests
- git on PATH if using --verify-clone-size true
"""

from __future__ import annotations
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Callable, Set

import requests

GITHUB_API = "https://api.github.com"
SESSION = requests.Session()

# Autosave
ON_RATE_LIMIT_CB: Optional[Callable[[], None]] = None

TITLE_EXCLUDE_RE = re.compile(
    r"\b(doc|docs|documentation|readme|typo)\b",
    re.IGNORECASE,
)

# Exclude PRs when affected files are only docs/ci/examples
DOC_LIKE_DIRS = ("docs/", "doc/", ".github/", "examples/", "example/")
DOC_LIKE_EXTS = (".md", ".rst", ".txt", ".adoc")
CI_FILES = (".pre-commit-config.yaml", "pyproject.toml", ".flake8", ".pylintrc", ".coveragerc", ".gitignore", ".editorconfig")

FIELDNAMES = [
    "repo", "stars", "repo_size_mb",
    "issue_number", "issue_title", "issue_url",
    "pr_number", "pr_url", "merged_at",
    "additions", "deletions", "changed_files","is_merged"
]

# ----------------------------- HTTP helpers ---------------------------------

def setup_session(token: Optional[str]):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    SESSION.headers.update(headers)


def backoff(resp: requests.Response):
    if resp.status_code != 403:
        return
    rem = resp.headers.get("X-RateLimit-Remaining")
    reset = resp.headers.get("X-RateLimit-Reset")
    resource = resp.headers.get("X-RateLimit-Resource", "core")
    if rem == "0" and reset:
        # save progress
        if ON_RATE_LIMIT_CB:
            try:
                ON_RATE_LIMIT_CB()
            except Exception as e:
                print(f"[warn] Autosave before sleep failed: {e}", file=sys.stderr)
        sleep_s = max(0, int(reset) - int(time.time()) + 2)
        t_at = time.strftime('%H:%M:%S', time.localtime(int(reset)))
        print(f"[rate-limit] resource={resource} Sleeping {sleep_s}s (until ~{t_at})…", file=sys.stderr)
        time.sleep(sleep_s)


def gh_get(url: str, params: Optional[Dict] = None) -> requests.Response:
    while True:
        r = SESSION.get(url, params=params)
        if r.status_code == 403:
            backoff(r)
            continue
        if r.status_code >= 400:
            print(f"[warn] HTTP {r.status_code} for URL: {url}", file=sys.stderr)
            return None
        return r

# ----------------------------- Repo search -----------------------------------

def search_repos(min_stars: int, max_repos: int, repo_name: str = None) -> Iterable[Dict]:
    q = f"language:Python stars:>={min_stars} fork:false archived:false"
    if repo_name:
        q+= f" repo:{repo_name}"
    per_page = 100
    page = 1
    fetched = 0
    while fetched < max_repos:
        params = {"q": q, "sort": "stars", "order": "desc", "per_page": per_page, "page": page}
        resp = gh_get(f"{GITHUB_API}/search/repositories", params=params)
        items = resp.json().get("items", []) or []
        if not items:
            break
        for it in items:
            yield it
            fetched += 1
            if fetched >= max_repos:
                break
        page += 1

# ----------------------------- Repo size -------------------------------------

def repo_size_mb_api(repo: Dict) -> float:
    # GitHub API repo.size is  KB
    return float(repo.get("size", 0)) / 1024.0


def measure_clone_size_mb(clone_url: str) -> float:
    tmp = Path(tempfile.mkdtemp(prefix="repo_"))
    try:
        subprocess.run(["git", "clone", clone_url, str(tmp / "r")], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        total = 0
        for p in (tmp / "r").rglob("*"):
            if p.is_file():
                total += p.stat().st_size
        return total / (1024.0 * 1024.0)
    except Exception as e:
        print(f"[warn] clone failed for {clone_url}: {e}", file=sys.stderr)
        return float("inf")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ----------------------------- Issues & PR link -------------------------------

def list_closed_issues(owner: str, name: str, max_pages: int = 10) -> Iterable[Dict]:
    """Closed issues, most recents first"""
    per_page = 100
    for page in range(1, max_pages + 1):
        url = f"{GITHUB_API}/repos/{owner}/{name}/issues"
        params = {"state": "closed", "per_page": per_page, "page": page, "sort": "updated", "direction": "desc"}
        resp = gh_get(url, params=params)
        issues = resp.json() or []
        if not issues:
            break
        for it in issues:
            if it.get("pull_request"):
                continue
            yield it


def linked_pr_numbers_for_issue(owner: str, name: str, issue_number: int) -> List[int]:
    """Uses the *timeline* of the issue to dounf prs"""
    per_page = 100
    page = 1
    pr_numbers: Set[int] = set()
    while True:
        url = f"{GITHUB_API}/repos/{owner}/{name}/issues/{issue_number}/timeline"
        resp = gh_get(url, params={"per_page": per_page, "page": page})
        events = resp.json() or []
        if not events:
            break
        for ev in events:
            if ev.get("event") == "cross-referenced":
                src = (ev.get("source") or {}).get("issue") or {}
                if src.get("pull_request") and isinstance(src.get("number"), int):
                    pr_numbers.add(int(src["number"]))
        if len(events) < per_page:
            break
        page += 1
    return sorted(pr_numbers)

# ----------------------------- PR details & files -----------------------------

def get_pr_details(owner: str, name: str, number: int) -> Dict:
    url = f"{GITHUB_API}/repos/{owner}/{name}/pulls/{number}"
    resp = gh_get(url)
    if resp:
        return resp.json()
    else:
        return None


def pr_files(owner: str, name: str, number: int) -> List[Dict]:
    files = []
    per_page = 100
    page = 1
    while True:
        url = f"{GITHUB_API}/repos/{owner}/{name}/pulls/{number}/files"
        resp = gh_get(url, params={"per_page": per_page, "page": page})
        chunk = resp.json() or []
        if not chunk:
            break
        files.extend(chunk)
        if len(chunk) < per_page:
            break
        page += 1
    return files


def looks_like_docs_only(files: List[Dict]) -> bool:
    code_like = 0
    for f in files:
        fn = f.get("filename", "").lower()
        if any(fn.startswith(d) for d in DOC_LIKE_DIRS):
            continue
        if any(fn.endswith(ext) for ext in DOC_LIKE_EXTS):
            continue
        if Path(fn).name in CI_FILES:
            continue
        code_like += 1
    return code_like == 0

# ----------------------------- CSV utils -------------------------------------

def ensure_csv_header(path: Path, fieldnames: List[str]):
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()


def append_csv_rows(path: Path, fieldnames: List[str], rows: List[Dict], start: int) -> int:
    if start >= len(rows):
        return start
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        for r in rows[start:]:
            w.writerow(r)
    return len(rows)

# ----------------------------- Collector -------------------------------------

def collect_and_stream(
    out_path: Path,
    autosave_every: int,
    *,
    min_stars: int,
    max_repo_mb: float,
    min_files: int,
    max_files: int,
    min_lines: int,
    max_lines: int,
    max_repos: int,
    max_issues: int,
    verify_clone_size: bool,
    repo_name: str,
) -> int:
    rows: List[Dict] = []
    ensure_csv_header(out_path, FIELDNAMES)
    state = {"last_saved": 0, "prs_checked": 0,"issues_checked":0}

    def _on_rl_cb():
        state["last_saved"] = append_csv_rows(out_path, FIELDNAMES, rows, state["last_saved"])
        print(f"[autosave] issues_saved={state['last_saved']}  issues_checked={state['issues_checked']} prs_checked={state['prs_checked']}")

    global ON_RATE_LIMIT_CB
    ON_RATE_LIMIT_CB = _on_rl_cb

    try:
        seen = 0
        for repo in search_repos(min_stars=min_stars, max_repos=max_repos, repo_name= repo_name):
            if len(rows) >= max_issues:
                break
            owner = repo["owner"]["login"]
            name = repo["name"]
            stars = int(repo.get("stargazers_count", 0))

            
            if verify_clone_size:
                size_mb = measure_clone_size_mb(repo["clone_url"])
                if size_mb > max_repo_mb:
                    print (f"Repo bigger than {max_repo_mb}. Repository size: {round(size_mb,3)} ")
                    continue
            else:
                size_mb = repo_size_mb_api(repo)
                if size_mb > max_repo_mb:
                    continue

            for issue in list_closed_issues(owner, name, max_pages=10):
                try:
                    if len(rows) >= max_issues:
                        break

                    state["issues_checked"]+=1
                    issue_number = int(issue.get("number"))
                    issue_title = issue.get("title", "")
                    issue_url = issue.get("html_url")

                    
                    pr_nums = linked_pr_numbers_for_issue(owner, name, issue_number)
                    if len(pr_nums) != 1:
                        continue
                    pr_number = pr_nums[0]

                    # PR details and filters
                    pr = get_pr_details(owner, name, pr_number)
                    if pr is None:
                        continue

                    
                    state["prs_checked"] += 1

                    # filter docs
                    pr_title = pr.get("title", "") or ""
                    if TITLE_EXCLUDE_RE.search(pr_title):
                        print (f"PR ignored. title: {pr_title}")
                        continue

                    additions = int(pr.get("additions", 0))
                    deletions = int(pr.get("deletions", 0))
                    changed_files = int(pr.get("changed_files", 0))
                    total_lines = additions + deletions

                    # Thresholds min/max
                    if changed_files < min_files or total_lines < min_lines:
                        print (f"PR ignored. Min files or min lines not reached: {pr_title}")
                        continue
                    if changed_files > max_files or total_lines > max_lines:
                        print (f"Max files or mas lines not reached.")

                    files = pr_files(owner, name, pr_number)
                    if looks_like_docs_only(files):
                        print (f"Looks lile docs only.  {pr_title}")
                        continue

                    
                    is_merged = pr.get("merged_at")
                        

                    rows.append({
                        "repo": f"{owner}/{name}",
                        "stars": stars,
                        "repo_size_mb": round(size_mb, 2),
                        "issue_number": issue_number,
                        "issue_title": issue_title,
                        "issue_url": issue_url,
                        "pr_number": pr_number,
                        "pr_url": pr.get("html_url"),
                        "merged_at": pr.get("merged_at"),
                        "additions": additions,
                        "deletions": deletions,
                        "changed_files": changed_files,
                        "is_merged": is_merged
                    })

                    if (len(rows) - state["last_saved"]) >= autosave_every:
                        state["last_saved"] = append_csv_rows(out_path, FIELDNAMES, rows, state["last_saved"])
                        print(f"[autosave] issues_saved={state['last_saved']}  issues_checked={state['issues_checked']} prs_checked={state['prs_checked']}")

                    seen += 1
                    if len(rows) >= max_issues:
                        break
                except:
                    continue

    except KeyboardInterrupt:
        print("[info] Interrupted by user, flushing rows…", file=sys.stderr)
    finally:
        state["last_saved"] = append_csv_rows(out_path, FIELDNAMES, rows, state["last_saved"])
        print(f"[done] total issues_saved={state['last_saved']} total prs_checked={state['prs_checked']} issues_checked={state['issues_checked']}")
        ON_RATE_LIMIT_CB = None
    return state["last_saved"]

# ----------------------------- CLI -------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Mine closed issues with exactly one linked merged PR from small Python repos.")
    p.add_argument("--out", required=True, help="Output CSV path")
    p.add_argument("--repo-name", type=str, default=50, help="Repository Name")
    p.add_argument("--min-stars", type=int, default=50, help="Minimum repo stars")
    p.add_argument("--max-repo-mb", type=float, default=9.9, help="Max repo size in MB (API or clone verified)")
    p.add_argument("--min-files", type=int, default=5, help="Minimum changed files in PR")
    p.add_argument("--max-files", type=int, default=999999, help="Maximum changed files in PR")
    p.add_argument("--min-lines", type=int, default=200, help="Minimum (additions+deletions) in PR")
    p.add_argument("--max-lines", type=int, default=999999, help="Maximum (additions+deletions) in PR")
    p.add_argument("--max-repos", type=int, default=1000, help="Max repos to scan (search API)")
    p.add_argument("--max-issues", type=int, default=500, help="Max issues (rows) to collect")
    p.add_argument("--autosave-every", type=int, default=20, help="Autosave to CSV every N new rows (and on rate limit)")
    p.add_argument("--verify-clone-size", type=str, default="false", choices=["true","false"], help="Clone & measure size on disk")
    return p.parse_args()


def main():
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[warn] GITHUB_TOKEN não definido; você ficará limitado a 60 req/h.", file=sys.stderr)
    setup_session(token)

    out_path = Path(args.out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    verify = args.verify_clone_size.lower() == "true"

    collect_and_stream(
        out_path=out_path,
        autosave_every=args.autosave_every,
        min_stars=args.min_stars,
        max_repo_mb=args.max_repo_mb,
        min_files=args.min_files,
        max_files=args.max_files,
        min_lines=args.min_lines,
        max_lines=args.max_lines,
        max_repos=args.max_repos,
        max_issues=args.max_issues,
        verify_clone_size=verify,
        repo_name = args.repo_name
    )


if __name__ == "__main__":
    main()
