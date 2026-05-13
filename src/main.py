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
