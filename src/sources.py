import uuid
import logging
import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 20


def collect_jobs(config):
    all_jobs = []
    fetchers = [
        ("EURAXESS", fetch_euraxess),
        ("Academic Positions", fetch_academic_positions),
        ("Jobs.ac.uk", fetch_jobs_ac_uk),
        ("Nature Careers", fetch_nature_careers),
        ("KTH", fetch_kth),
        ("Aarhus", fetch_aarhus),
        ("ITU Copenhagen", fetch_itu_copenhagen),
        ("NTNU", fetch_ntnu),
        ("Aalto", fetch_aalto),
    ]
    for name, fn in fetchers:
        try:
            jobs = fn()
            log.info("%s: %d vagas", name, len(jobs))
            all_jobs.extend(jobs)
        except Exception as e:
            log.warning("%s falhou: %s", name, e)
    return _dedup(all_jobs)


# ---------- fontes globais ----------

def fetch_euraxess():
    """EURAXESS é a fonte mais importante para vagas europeias.
    Busca por keyword principal; o pré-filtro do main.py refina depois."""
    jobs = []
    for kw in ["interaction design", "human-computer interaction", "design research"]:
        url = "https://euraxess.ec.europa.eu/jobs/search"
        r = requests.get(url, params={"keywords": kw}, headers=HEADERS, timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "lxml")
        for card in soup.select("article, .views-row, .job-listing"):
            a = card.select_one("h2 a, h3 a, .job-title a, a[href*='/jobs/']")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not title or len(title) < 8:
                continue
            if href.startswith("/"):
                href = "https://euraxess.ec.europa.eu" + href
            desc_el = card.select_one(".field--name-body, .job-summary, p")
            desc = desc_el.get_text(" ", strip=True)[:1500] if desc_el else title
            country = _extract_country(card)
            jobs.append(_create_job(title, "EURAXESS", country, href, desc))
    return jobs


def fetch_academic_positions():
    jobs = []
    urls = [
        "https://academicpositions.com/jobs/field/human-computer-interaction",
        "https://academicpositions.com/jobs/field/interaction-design",
        "https://academicpositions.com/jobs/field/design",
    ]
    for url in urls:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "lxml")
        for card in soup.select("article, .job-card, .listing-card, [class*='JobCard']"):
            a = card.find("a", href=True)
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a["href"]
            if not title or len(title) < 8:
                continue
            if not href.startswith("http"):
                href = "https://academicpositions.com" + href
            desc = card.get_text(" ", strip=True)[:1500]
            jobs.append(_create_job(title, "Academic Positions", "EU", href, desc))
    return jobs


def fetch_jobs_ac_uk():
    jobs = []
    url = "https://www.jobs.ac.uk/search/?keywords=interaction+design+hci&sort=rd"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "lxml")
    for res in soup.select(".j-search-result__text, .result, .job-result"):
        a = res.find("a", href=True)
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a["href"]
        if not title or len(title) < 8:
            continue
        if not href.startswith("http"):
            href = "https://www.jobs.ac.uk" + href
        desc = res.get_text(" ", strip=True)[:1500]
        jobs.append(_create_job(title, "Jobs.ac.uk", "UK", href, desc))
    return jobs


def fetch_nature_careers():
    jobs = []
    url = "https://www.nature.com/naturecareers/jobs"
    r = requests.get(url, params={"q": "human-computer interaction"}, headers=HEADERS, timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "lxml")
    for card in soup.select("article, li.job-result, [class*='job']"):
        a = card.find("a", href=True)
        if not a:
            continue
        title = a.get_text(strip=True)
        if not title or len(title) < 10:
            continue
        href = a["href"]
        if not href.startswith("http"):
            href = "https://www.nature.com" + href
        desc = card.get_text(" ", strip=True)[:1500]
        jobs.append(_create_job(title, "Nature Careers", "EU", href, desc))
    return jobs


# ---------- fontes institucionais ----------

def fetch_kth():
    jobs = []
    url = "https://www.kth.se/lediga-jobb?l=en"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "lxml")
    for a in soup.select("a[href*='/lediga-jobb/']"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or len(title) < 8 or href.endswith("/lediga-jobb/"):
            continue
        if not href.startswith("http"):
            href = "https://www.kth.se" + href
        jobs.append(_create_job(title, "KTH", "SE", href, title))
    return jobs


def fetch_aarhus():
    jobs = []
    url = "https://international.au.dk/about/profile/vacant-positions"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "lxml")
    for a in soup.select("a[href*='/vacant-positions/job/']"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or len(title) < 8:
            continue
        if not href.startswith("http"):
            href = "https://international.au.dk" + href
        jobs.append(_create_job(title, "Aarhus University", "DK", href, title))
    return jobs


def fetch_itu_copenhagen():
    jobs = []
    url = "https://en.itu.dk/About-ITU/Vacant-positions"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "lxml")
    keywords_in_title = ("professor", "lecturer", "postdoc", "researcher", "phd")
    for a in soup.select("a[href]"):
        title = a.get_text(strip=True)
        if not title or len(title) < 15:
            continue
        if not any(k in title.lower() for k in keywords_in_title):
            continue
        href = a["href"]
        if not href.startswith("http"):
            href = "https://en.itu.dk" + href
        jobs.append(_create_job(title, "IT University of Copenhagen", "DK", href, title))
    return jobs


def fetch_ntnu():
    jobs = []
    url = "https://www.ntnu.edu/vacancies"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "lxml")
    keywords_in_title = ("professor", "førsteamanuensis", "researcher", "postdoc", "lecturer")
    for a in soup.select("a[href]"):
        title = a.get_text(strip=True)
        if not title or len(title) < 15:
            continue
        if not any(k in title.lower() for k in keywords_in_title):
            continue
        href = a["href"]
        if not href.startswith("http"):
            href = "https://www.ntnu.edu" + href
        jobs.append(_create_job(title, "NTNU", "NO", href, title))
    return jobs


def fetch_aalto():
    jobs = []
    url = "https://www.aalto.fi/en/open-positions"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "lxml")
    for a in soup.select("a[href*='/open-positions/']"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or len(title) < 8:
            continue
        if not href.startswith("http"):
            href = "https://www.aalto.fi" + href
        jobs.append(_create_job(title, "Aalto University", "FI", href, title))
    return jobs


# ---------- utils ----------

def _create_job(title, company, country, url, description):
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, url.split("?")[0])),
        "title": title,
        "company": company,
        "country": country,
        "url": url,
        "description": description or title,
    }


def _extract_country(card):
    el = card.select_one(".field--name-field-country, .country")
    if not el:
        return ""
    text = el.get_text(strip=True).upper()
    mapping = {
        "SWEDEN": "SE", "DENMARK": "DK", "NORWAY": "NO", "FINLAND": "FI",
        "NETHERLANDS": "NL", "GERMANY": "DE", "UNITED KINGDOM": "UK",
        "SWITZERLAND": "CH", "ICELAND": "IS",
    }
    for k, v in mapping.items():
        if k in text:
            return v
    return text[:2]


def _dedup(jobs):
    seen = set()
    out = []
    for j in jobs:
        if j["id"] in seen:
            continue
        seen.add(j["id"])
        out.append(j)
    return out
