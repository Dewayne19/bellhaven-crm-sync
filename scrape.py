"""Scrape every Bellhaven community from the operator public website.

Discovery crawls the paginated index and the home and about pages, because at
least one community (Bellhaven Meadows of Findlay) is linked only from the
home page and is missed by walking /communities alone.
"""

import concurrent.futures
import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

import config

SEED_PATHS = ["/", "/communities", "/about"]
COMMUNITY_HREF = re.compile(r"^/communities/[^/]+$")


def _session():
    session = requests.Session()
    session.headers["User-Agent"] = "bellhaven-sync/1.0"
    return session


def _fetch(session, path, tries=3):
    """GET with retries; the sandbox is free-tier and cold-starts."""
    url = config.SITE_BASE + path
    for attempt in range(tries):
        try:
            response = session.get(url, timeout=20)
            response.raise_for_status()
            return response.text
        except Exception:
            if attempt == tries - 1:
                raise
    return ""


def discover(session):
    """Every distinct community path found anywhere on the site."""
    pages = list(SEED_PATHS)
    page = 1
    while True:
        pages.append("/communities?page=%d" % page)
        html = _fetch(session, "/communities?page=%d" % page)
        if "page=%d" % (page + 1) not in html:
            break
        page += 1

    seen, found = set(), []
    for path in pages:
        html = _fetch(session, path)
        for anchor in BeautifulSoup(html, "html.parser").find_all("a", href=True):
            href = anchor["href"]
            if COMMUNITY_HREF.match(href) and href not in seen:
                seen.add(href)
                found.append(href)
    return found


def _definition(soup, label):
    for term in soup.select("dl.detail dt"):
        if term.get_text(strip=True).lower() == label.lower():
            return term.find_next_sibling("dd")
    return None


def parse_community(session, path):
    soup = BeautifulSoup(_fetch(session, path), "html.parser")
    name = soup.find("h1").get_text(strip=True)

    address = _definition(soup, "Address")
    lines = []
    if address:
        lines = [
            part.strip()
            for part in address.get_text("\n", strip=True).split("\n")
            if part.strip()
        ]
    street = lines[0] if lines else ""
    city = state = zip_code = ""
    if len(lines) > 1:
        match = re.match(r"(.*),\s*([A-Za-z]{2})\s*(\d{5})", lines[1])
        if match:
            city, state, zip_code = (group.strip() for group in match.groups())

    care = _definition(soup, "Care Offerings")
    care_types = []
    if care:
        care_types = [badge.get_text(strip=True) for badge in care.select(".badge")]

    def text_of(label):
        node = _definition(soup, label)
        return node.get_text(" ", strip=True) if node else ""

    return {
        "slug": path.rsplit("/", 1)[-1],
        "url": config.SITE_BASE + path,
        "name": name,
        "street": street,
        "city": city,
        "state": state,
        "zip": zip_code,
        "care_types": care_types,
        "phone": text_of("Phone"),
        "administrator": text_of("Administrator"),
    }


def scrape():
    session = _session()
    paths = discover(session)
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        rows = list(pool.map(lambda path: parse_community(session, path), paths))
    rows.sort(key=lambda row: row["slug"])
    return {
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": config.SITE_BASE,
        "count": len(rows),
        "communities": rows,
    }


def main():
    snapshot = scrape()
    config.SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print("scraped %d communities -> %s" % (snapshot["count"], config.SNAPSHOT_PATH))
    return 0


if __name__ == "__main__":
    sys.exit(main())
