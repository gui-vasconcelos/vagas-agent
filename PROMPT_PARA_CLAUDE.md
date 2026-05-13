# Contexto do Projeto: Vagas-Agent\n
## Estrutura de Arquivos\n```
.
./requirements.txt
./config.yaml
./README.md
./PROMPT_PARA_CLAUDE.md
./data
./src
./src/classifier.py
./src/reporter.py
./src/sources.py
./src/storage.py
./src/emailer.py
./src/main.py
```\n
### Arquivo: config.yaml\n```python
candidate_profile: >
  Postdoc na KTH com foco em Embodied Design e Soma Design. 
  Pesquisador híbrido: Arquitetura, Interação Humano-Computador (HCI) e Tecnologias Imersivas (XR/VR). 
  Especialista em Fenomenologia, Atmosfera e o papel do corpo no espaço digital e físico.
  Busca posições que unam o design espacial com computação pervasiva ou sensibilidade somática.

keywords:
  # Core HCI & Design
  - HCI
  - interaction design
  - embodied interaction
  - soma design
  - somaesthetics
  - design research
  # Architecture & Space
  - computational design
  - digital architecture
  - responsive environments
  - spatial computing
  - smart cities phenomenology
  - architecture and computation
  # Technology
  - XR
  - VR
  - AR
  - mixed reality
  - immersive environments

countries:
  - SE
  - DK
  - NO
  - FI
  - NL # Altamente relevante para Arquitetura/HCI
  - DE # Forte em Interaction Design / Media Architecture
  - UK # Referência global em HCI e Architecture research
  - CH # ETH Zurich é alvo estratégico em arquitetura/tech
```\n
### Arquivo: requirements.txt\n```python
requests
beautifulsoup4
pyyaml
```\n
### Arquivo: .github/workflows/weekly.yml\n```python
name: Weekly Job Search

on:
  schedule:
    - cron: '0 7 * * 1' # Segundas às 07:00 UTC
  workflow_dispatch: # Permite rodar manualmente

jobs:
  search:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
          
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          
      - name: Cache database
        uses: actions/cache@v4
        with:
          path: data/seen.db
          key: ${{ runner.os }}-job-db-${{ github.run_id }}
          restore-keys: |
            ${{ runner.os }}-job-db-
          
      - name: Run agent
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
          RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
          EMAIL_FROM: ${{ secrets.EMAIL_FROM }}
        run: python src/main.py
```\n
### Arquivo: src/classifier.py\n```python
import os
import requests
import json
import time
import logging

def classify_jobs(jobs, config):
    api_key = os.getenv("OPENROUTER_API_KEY")
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    classified = []
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/hermes-agent", # Boas práticas OpenRouter
        "X-Title": "Academic Job Agent"
    }

    prompt_template = """
    Você é um recrutador acadêmico sênior especializado em perfis interdisciplinares (Arquitetura + HCI).
    
    PERFIL DO CANDIDATO:
    {profile}

    CRITÉRIOS DE AVALIAÇÃO:
    - FIT FORTE (90-100): Menciona Soma Design, Embodied Interaction, ou Pesquisa em Arquitetura com XR/VR/Fenomenologia.
    - POSSÍVEL (60-89): Interaction Design generalista, Computational Design, ou HCI experimental.
    - ANOTAR (10-59): Computer Science tradicional, TI puro, ou Arquitetura sem tech.

    VAGA:
    Título: {title}
    Empresa: {company}
    Descrição: {description}

    Retorne APENAS um JSON válido:
    {{
        "fit_score": (inteiro),
        "fit_category": "Forte" | "Possível" | "Anotar",
        "justification": "2 linhas sobre a conexão Arq/HCI/Soma"
    }}
    """

    for job in jobs:
        prompt = prompt_template.format(
            profile=config['candidate_profile'],
            title=job['title'],
            company=job['company'],
            description=job['description'][:2000]
        )

        # Retry logic para robustez
        for attempt in range(3):
            try:
                response = requests.post(url, headers=headers, json={
                    "model": "google/gemini-2.0-flash-001",
                    "messages": [
                        {"role": "system", "content": "Você é um classificador acadêmico que responde apenas em JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": { "type": "json_object" },
                    "temperature": 0.1
                }, timeout=30)
                
                resp_json = response.json()
                if 'choices' in resp_json:
                    content = resp_json['choices'][0]['message']['content']
                    analysis = json.loads(content)
                    job.update(analysis)
                    break
                else:
                    logging.warning(f"Erro OpenRouter (Tentativa {attempt+1}): {resp_json}")
                    time.sleep(2)
            except Exception as e:
                logging.error(f"Erro na classificação (Tentativa {attempt+1}): {e}")
                time.sleep(2)
        else:
            # Fallback após 3 tentativas
            job.update({
                "fit_score": 0, 
                "fit_category": "Erro", 
                "justification": "Falha na comunicação com o LLM após múltiplas tentativas."
            })
        
        classified.append(job)
    
    return sorted(classified, key=lambda x: x.get('fit_score', 0), reverse=True)
```\n
### Arquivo: src/emailer.py\n```python
import os
import requests

def send_email(subject, content_md, config):
    api_key = os.getenv("RESEND_API_KEY")
    to_email = os.getenv("EMAIL_TO")
    from_email = os.getenv("EMAIL_FROM", "onboarding@resend.dev")
    
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Converter markdown simples para HTML básico para o email
    html_content = content_md.replace("\n", "<br>")
    
    payload = {
        "from": from_email,
        "to": to_email,
        "subject": subject,
        "html": html_content
    }
    
    requests.post(url, headers=headers, json=payload)
```\n
### Arquivo: src/main.py\n```python
import os
import yaml
import logging
from sources import collect_jobs
from storage import Database
from classifier import classify_jobs
from reporter import generate_report
from emailer import send_email

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

def main():
    config = load_config()
    db = Database("data/seen.db")
    
    logging.info("Iniciando coleta de vagas...")
    raw_jobs = collect_jobs(config)
    
    # Filtrar apenas novas
    new_jobs = [j for j in raw_jobs if not db.is_seen(j['id'])]
    
    if not new_jobs:
        logging.info("Nenhuma vaga nova encontrada.")
        return

    logging.info(f"Classificando {len(new_jobs)} novas vagas...")
    classified_jobs = classify_jobs(new_jobs, config)
    
    # Salvar as classificadas no DB para dedup futuro
    for job in classified_jobs:
        db.add(job['id'])
        
    logging.info("Gerando relatório...")
    report = generate_report(classified_jobs)
    
    logging.info("Enviando email...")
    strong_fits = len([j for j in classified_jobs if j.get('fit_category') == 'Forte'])
    subject = f"Monitor de Vagas: {len(classified_jobs)} novas ({strong_fits} fortes)"
    
    send_email(subject, report, config)
    logging.info("Processo concluído com sucesso.")

if __name__ == "__main__":
    main()
```\n
### Arquivo: src/reporter.py\n```python
def generate_report(jobs):
    lines = ["# Relatório de Vagas Acadêmicas\n"]
    
    for job in jobs:
        lines.append(f"## [{job['title']}]({job['url']})")
        lines.append(f"- **Univ/Empresa**: {job['company']} ({job['country']})")
        lines.append(f"- **Fit**: {job['fit_category']} ({job['fit_score']}/100)")
        lines.append(f"- **Justificativa**: {job['justification']}")
        lines.append("\n---\n")
        
    return "\n".join(lines)
```\n
### Arquivo: src/sources.py\n```python
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
```\n
### Arquivo: src/storage.py\n```python
import sqlite3
import os

class Database:
    def __init__(self, db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.create_table()

    def create_table(self):
        self.conn.execute("CREATE TABLE IF NOT EXISTS seen_jobs (id TEXT PRIMARY KEY)")
        self.conn.commit()

    def is_seen(self, job_id):
        cursor = self.conn.execute("SELECT 1 FROM seen_jobs WHERE id = ?", (job_id,))
        return cursor.fetchone() is not None

    def add(self, job_id):
        self.conn.execute("INSERT OR IGNORE INTO seen_jobs (id) VALUES (?)", (job_id,))
        self.conn.commit()
```\n
