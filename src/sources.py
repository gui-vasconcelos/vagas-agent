import requests
from bs4 import BeautifulSoup
import uuid
import logging

def collect_jobs(config):
    all_jobs = []
    # Usar headers reais para evitar bloqueios
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # 1. KTH
    all_jobs.extend(fetch_kth(headers))
    
    # 2. Jobs.ac.uk (Referência HCI)
    all_jobs.extend(fetch_jobs_ac_uk(headers))
    
    # 3. Academic Positions (Nordics)
    all_jobs.extend(fetch_academic_positions(headers))

    return all_jobs

def fetch_kth(headers):
    logging.info("Buscando KTH...")
    jobs = []
    url = "https://www.kth.se/en/om/work-at-kth/lediga-jobb"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        # Procura links dentro da área de conteúdo principal
        for a in soup.select('article a[href*="lediga-jobb"]'):
            title = a.text.strip()
            if len(title) > 15: # Evitar links de navegação
                jobs.append(create_job_dict(title, "KTH", "SE", a['href']))
    except Exception as e: logging.error(f"KTH error: {e}")
    return jobs

def fetch_jobs_ac_uk(headers):
    logging.info("Buscando Jobs.ac.uk...")
    jobs = []
    url = "https://www.jobs.ac.uk/search/?keywords=interaction+design+hci&sort=rd"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        # Seletor atualizado conforme debug
        for res in soup.select('.j-search-result__text'):
            a = res.find('a')
            if a:
                title = a.text.strip()
                link = "https://www.jobs.ac.uk" + a['href']
                jobs.append(create_job_dict(title, "Jobs.ac.uk", "UK/EU", link))
    except Exception as e: logging.error(f"Jobs.ac.uk error: {e}")
    return jobs

def fetch_academic_positions(headers):
    logging.info("Buscando Academic Positions...")
    jobs = []
    url = "https://academicpositions.com/jobs/design-and-hc-interaction"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        # Tenta encontrar itens de vaga na lista
        for item in soup.select('.job-card, .job-item'):
            title_node = item.find(['h2', 'h3'])
            link_node = item.find('a', href=True)
            if title_node and link_node:
                jobs.append(create_job_dict(title_node.text.strip(), "Academic Positions", "Nordics", link_node['href']))
    except Exception as e: logging.error(f"Academic Positions error: {e}")
    return jobs

def create_job_dict(title, company, country, url):
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, url)),
        "title": title,
        "company": company,
        "country": country,
        "url": url,
        "description": f"Position: {title} at {company}. Check full details at {url}"
    }
