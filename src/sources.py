import uuid
import logging
import re
import xml.etree.ElementTree as ET
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

# Vagas publicadas no sistema Varbi (subdominio.varbi.com) — usado pela maioria
# das universidades suecas. Validado em 2026-08-03.
VARBI_INSTITUTIONS = [
    # (subdominio, nome, pais)
    ("uu", "Uppsala University", "SE"),        # ~207 vagas
    ("su", "Stockholm University", "SE"),      # ~174 vagas
    ("umu", "Umeå University", "SE"),          # ~186 vagas
    ("kth", "KTH Royal Institute of Technology", "SE"),  # ~228 vagas
    ("hh", "Halmstad University", "SE"),       # ~24 vagas
    ("kau", "Karlstad University", "SE"),      # ~39 vagas
    ("miun", "Mid Sweden University", "SE"),   # ~48 vagas
    ("ju", "Jönköping University", "SE"),      # ~18 vagas
    # ltu (Luleå) existe mas não lista via what:job — página própria falha 404;
    # chalmers/gu/liu/his/sh/bth/oru usam outros sistemas (páginas diretas abaixo).
]

# Feeds RSS Reachmee — usado por Konstfack e Malmö (escolas de arte/design).
# URL pattern: site{N}.reachmee.com/Public/rssfeed/external.ashx?id={id}&InstallationID={inst}&CustomerName={name}&lang={lang}
REACHMEE_FEEDS = [
    # (nome, pais, url_feed, lang)
    ("Konstfack University of Arts, Crafts and Design", "SE",
     "https://site106.reachmee.com/Public/rssfeed/external.ashx?id=9&InstallationID=I008&CustomerName=konstfack&lang=SE", "SE"),
    ("Malmö University", "SE",
     "https://site103.reachmee.com/Public/rssfeed/external.ashx?id=6&InstallationID=I005&CustomerName=mau&lang=UK", "UK"),
]

# Páginas institucionais que listam links de vaga direto no HTML.
# Cada entrada: (nome, pais, url, regex_link, title_min)
PAGE_SOURCES = [
    # --- Suécia ---
    ("Örebro University", "SE",
     "https://www.oru.se/jobba-hos-oss/lediga-jobb/",
     r"jobbannons\?jid=", 10),
    # --- Dinamarca ---
    ("University of Copenhagen", "DK",
     "https://employment.ku.dk/all-vacancies/",
     r"employment\.ku\.dk/.*\?show=", 10),
    ("Aarhus University", "DK",
     "https://international.au.dk/about/profile/vacant-positions",
     r"vacant-positions/(job|position)", 10),
    ("University of Southern Denmark (SDU)", "DK",
     "https://www.sdu.dk/da/om-sdu/job-sdu/videnskabelige",
     r"/job-sdu/[a-z]", 10),
    # --- Noruega (links apontam direto para vagas no Jobbnorge) ---
    ("University of Agder (UiA)", "NO",
     "https://www.uia.no/ledige-stillinger",
     r"jobbnorge\.no/ledige-stillinger/stilling/", 10),
    ("Oslo School of Architecture and Design (AHO)", "NO",
     "https://aho.no/om/ledige-stillinger/",
     r"jobbnorge\.no/ledige-stillinger/stilling/", 10),
    ("Nord University", "NO",
     "https://www.nord.no/om/ledige-stillinger",
     r"jobbnorge\.no/ledige-stillinger/stilling/", 10),
    ("Western Norway University of Applied Sciences (HVL)", "NO",
     "https://www.hvl.no/ledige-stillingar/",
     r"/ledige-stillingar/[a-z]", 10),
    ("Oslo Metropolitan University (OsloMet)", "NO",
     "https://www.oslomet.no/om/ledige-stillinger",
     r"/om/ledige-stillinger/[a-z]", 10),
    # --- Finlândia ---
    ("University of Oulu", "FI",
     "https://www.oulu.fi/en/open-positions",
     r"varbi\.com/.*what:job", 10),
    # --- Islândia ---
    ("University of Iceland", "IS",
     "https://english.hi.is/about-ui/working-ui/vacancies",
     r"english\.hi\.is/.*(vacanc|position)", 10),
]

# Páginas com forte tendência a JS (SPA) — scraping pode renderizar 0 vagas.
# Mantidas porque listam links em algumas renderizações; o log mostra se falharem.
PAGE_SOURCES_JS = [
    ("Chalmers University of Technology", "SE",
     "https://www.chalmers.se/en/about-chalmers/work-with-us/vacancies/",
     r"chalmers\.se/en/positions|vacancies/", 10),
    ("Gothenburg University", "SE",
     "https://www.gu.se/om-universitetet/jobba-hos-oss/lediga-anstallningar",
     r"anstallning|jobID", 10),
    ("Linköping University", "SE",
     "https://liu.se/en/work-at-liu/vacancies",
     r"liu\.se/.*(vacanc|position|jobb)", 10),
    ("Blekinge Institute of Technology (BTH)", "SE",
     "https://www.bth.se/english/about-bth/work-at-bth/vacancies",
     r"bth\.se/.*vacanc", 10),
    ("Tampere University", "FI",
     "https://www.tuni.fi/en/about-us/working-at-tampere-universities",
     r"tuni\.fi/.*(job|vacanc|open)", 10),
]

# Feeds RSS Helsinki (por categoria) — validado 2026-08-03.
HELSINKI_RSS = [
    ("University of Helsinki — Professors", "FI",
     "https://jobs.helsinki.fi/services/rss/category/?catid=8703702"),
    ("University of Helsinki — Teaching & Research", "FI",
     "https://jobs.helsinki.fi/services/rss/category/?catid=8703802"),
]


def collect_jobs(config):
    all_jobs = []
    fetchers = [
        ("EURAXESS", fetch_euraxess),
        ("Jobs.ac.uk", fetch_jobs_ac_uk),
        ("KTH", fetch_kth),
        ("ITU Copenhagen", fetch_itu_copenhagen),
        ("NTNU", fetch_ntnu),
        ("Aalto", fetch_aalto),
        ("Varbi (universidades suecas)", fetch_varbi),
        ("Reachmee RSS (Konstfack/Malmö)", fetch_reachmee_rss),
        ("Helsinki RSS", fetch_helsinki_rss),
        ("Páginas diretas nórdicas", fetch_page_sources),
        ("Páginas JS (best-effort)", fetch_page_sources_js),
        ("Aalborg (JSON-LD)", fetch_aalborg),
        ("KADK (hr-manager)", fetch_kadk),
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
    Coleta usando links /jobs/<id> — mais robusto que seletores de card."""
    jobs = []
    seen = set()
    for kw in ["interaction design", "human-computer interaction", "design research"]:
        url = "https://euraxess.ec.europa.eu/jobs/search"
        r = requests.get(url, params={"keywords": kw}, headers=HEADERS, timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "lxml")
        for a in soup.select('a[href*="/jobs/"]'):
            href = a.get("href", "")
            if "/jobs/search" in href or href in seen:
                continue
            seen.add(href)
            title = a.get_text(strip=True)
            if not title or len(title) < 8:
                continue
            if not href.startswith("http"):
                href = "https://euraxess.ec.europa.eu" + href
            # Sobe até o container para extrair contexto (descrição + país)
            parent = a
            full_text = title
            for _ in range(5):
                parent = parent.parent
                if parent:
                    full_text = parent.get_text(" ", strip=True)
                    if len(full_text) > 100:
                        break
            desc = full_text[:1500]
            country = _extract_country_from_text(full_text)
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
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 403:
                log.warning("Academic Positions: bloqueado por Cloudflare (403). Pulei.")
                continue
            r.raise_for_status()
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
        except Exception as e:
            log.warning("Academic Positions falhou: %s", e)
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
    try:
        r = requests.get(url, params={"q": "human-computer interaction"}, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 403:
            log.warning("Nature Careers: bloqueado por Cloudflare (403). Pulei.")
            return jobs
        r.raise_for_status()
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
    except Exception as e:
        log.warning("Nature Careers falhou: %s", e)
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


# ---------- fontes nórdicas novas (validadas 2026-08-03) ----------

def fetch_varbi():
    """Sistema Varbi: cobre a maioria das universidades suecas de uma vez.
    Cada instituição tem <sub>.varbi.com/se/ listando links what:job/jobID:N."""
    jobs = []
    for sub, name, country in VARBI_INSTITUTIONS:
        url = f"https://{sub}.varbi.com/se/"
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.select("a[href*='what:job']"):
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if not title or len(title) < 8:
                    continue
                if not href.startswith("http"):
                    href = f"https://{sub}.varbi.com" + href
                jobs.append(_create_job(title, name, country, href, title))
        except Exception as e:
            log.warning("Varbi %s (%s) falhou: %s", sub, name, e)
    return jobs


def fetch_reachmee_rss():
    """RSS Reachmee: Konstfack e Malmö publicam feeds XML com <item>/<title>/<link>."""
    jobs = []
    for name, country, url, lang in REACHMEE_FEEDS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            root = ET.fromstring(r.text)
            ns = {"rss": "http://backend.userland.com/rss2"}
            for item in root.iter("item"):
                title_el = item.find("title")
                link_el = item.find("link")
                title = (title_el.text or "").strip() if title_el is not None else ""
                link = (link_el.text or "").strip() if link_el is not None else ""
                if not title or len(title) < 8:
                    continue
                # URL da vaga: padrao rmjob=<CommAdSeqNo> quando nao ha link util
                if not link or "reachmee" not in link:
                    seq = item.find("CommAdSeqNo")
                    if seq is not None and seq.text:
                        site = "konstfack" if "konstfack" in url.lower() else "mau"
                        link = f"https://www.{site}.se/sv/Aktuellt/Jobba-pa-Konstfack/?rmpage=job&rmjob={seq.text}"
                desc = (item.findtext("description") or title)[:1500]
                jobs.append(_create_job(title, name, country, link, desc))
        except Exception as e:
            log.warning("Reachmee RSS %s falhou: %s", name, e)
    return jobs


def fetch_helsinki_rss():
    jobs = []
    for name, country, url in HELSINKI_RSS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            root = ET.fromstring(r.text)
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                if not title or len(title) < 8:
                    continue
                desc = (item.findtext("description") or title)[:1500]
                jobs.append(_create_job(title, name, country, link, desc))
        except Exception as e:
            log.warning("Helsinki RSS %s falhou: %s", name, e)
    return jobs


def _fetch_page(name, country, url, link_re, title_min=10):
    """Genérico: baixa a página, pega <a href> que casam com link_re, cria jobs."""
    jobs = []
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "lxml")
    base = re.match(r"(https?://[^/]+)", url).group(1)
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/"):
            href = base + href
        elif href.startswith("//"):
            href = "https:" + href
        # resolve antes de testar o regex: links relativos não casam
        # padrões com domínio completo (ex: employment.ku.dk/.*\?show=)
        if not re.search(link_re, href, re.I):
            continue
        if href in seen:
            continue
        seen.add(href)
        title = a.get_text(" ", strip=True)
        if not title or len(title) < title_min:
            continue
        jobs.append(_create_job(title, name, country, href, title))
    return jobs


def fetch_page_sources():
    jobs = []
    for name, country, url, link_re, title_min in PAGE_SOURCES:
        try:
            jobs.extend(_fetch_page(name, country, url, link_re, title_min))
        except Exception as e:
            log.warning("%s falhou: %s", name, e)
    return jobs


def fetch_page_sources_js():
    """Páginas com JS — best-effort. Falham silenciosamente quando renderizam 0."""
    jobs = []
    for name, country, url, link_re, title_min in PAGE_SOURCES_JS:
        try:
            jobs.extend(_fetch_page(name, country, url, link_re, title_min))
        except Exception as e:
            log.warning("%s (JS) falhou: %s", name, e)
    return jobs


def fetch_aalborg():
    """Aalborg (stillinger.aau.dk) renderiza por JS; o HTML embute JSON-LD com as vagas."""
    jobs = []
    url = "https://www.stillinger.aau.dk/videnskabelige-stillinger"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "lxml")
    # JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            import json as _json
            data = _json.loads(script.string or "{}")
            items = data if isinstance(data, list) else [data]
            for it in items:
                if isinstance(it, dict) and it.get("@type") == "JobPosting":
                    title = it.get("title", "")
                    link = it.get("url", "")
                    if title and link:
                        jobs.append(_create_job(title, "Aalborg University", "DK", link,
                                                (it.get("description") or title)[:1500]))
        except Exception:
            continue
    # fallback: links com padrão de vaga
    if not jobs:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r"stillinger\.aau\.dk/[a-z].*?(?<!krav)(?<!rekrutterings)", href) and "/videnskabelige-stillinger" not in href:
                title = a.get_text(" ", strip=True)
                if title and len(title) > 10:
                    jobs.append(_create_job(title, "Aalborg University", "DK", href, title))
    return jobs


def fetch_kadk():
    """KADK (Royal Danish Academy) publica vagas via candidate.hr-manager.net."""
    jobs = []
    url = "https://kglakademi.dk/en/vacancies"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "hr-manager" not in href and "ApplicationInit" not in href:
            continue
        title = a.get_text(" ", strip=True)
        if not title or len(title) < 8:
            continue
        if href.startswith("/"):
            href = "https://kglakademi.dk" + href
        jobs.append(_create_job(title, "Royal Danish Academy (KADK)", "DK", href, title))
    return jobs


# ---------- utils ----------

def _create_job(title, company, country, url, description):
    # NOTA: uuid sobre a URL COMPLETA (com query string). Fontes como Reachmee
    # (rmjob=N), Örebro (jid=N) e KU (?show=N) carregam o id da vaga na query;
    # truncar em "?" colapsava todas as vagas da fonte na mesma id (bug 2026-08-03).
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, url)),
        "title": title,
        "company": company,
        "country": country,
        "url": url,
        "description": description or title,
    }


def _extract_country(card):
    """Extração legada — mantida para compatibilidade com outras fontes."""
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


def _extract_country_from_text(text):
    """Extrai código de país de texto livre (usado pelo EURAXESS)."""
    mapping = [
        ("Sweden", "SE"), ("Denmark", "DK"), ("Norway", "NO"),
        ("Finland", "FI"), ("Netherlands", "NL"), ("Germany", "DE"),
        ("United Kingdom", "UK"), ("Switzerland", "CH"),
        ("France", "FR"), ("Italy", "IT"), ("Spain", "ES"),
        ("Portugal", "PT"), ("Belgium", "BE"), ("Austria", "AT"),
        ("Ireland", "IE"), ("Iceland", "IS"),
    ]
    for name, code in mapping:
        if name in text:
            return code
    return ""


def _dedup(jobs):
    seen = set()
    out = []
    for j in jobs:
        if j["id"] in seen:
            continue
        seen.add(j["id"])
        out.append(j)
    return out
