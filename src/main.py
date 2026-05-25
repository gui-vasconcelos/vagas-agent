"""Orquestrador semanal.

Pipeline:
1. Lê config.yaml
2. Coleta vagas de todas as fontes
3. Deduplica contra SQLite
4. Pré-filtra por keyword (poupa chamadas LLM em vagas obviamente irrelevantes)
5. Classifica via OpenRouter
6. Filtra por fit_score mínimo
7. Gera relatório + envia email
8. Marca todas as classificadas como vistas

Rodar via: python -m src.main
"""
import logging
import sys
import yaml

from src.sources import collect_jobs
from src.storage import Database
from src.classifier import classify_jobs
from src.reporter import generate_report, markdown_to_html
from src.emailer import send_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("main")


def load_config():
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def keyword_match(job, keywords):
    """Match com word boundary para evitar falsos positivos com keywords curtas
    (AR bater em 'software', VR em 'server', etc).
    Keywords <=4 caracteres usam regex \\b...\\b; mais longas usam substring."""
    import re
    haystack = (job["title"] + " " + job.get("description", "")).lower()
    for k in keywords:
        kl = k.lower()
        if len(kl) <= 4:
            if re.search(rf"\b{re.escape(kl)}\b", haystack):
                return True
        else:
            if kl in haystack:
                return True
    return False


def main():
    config = load_config()
    db = Database("data/seen.db")

    log.info("=" * 60)
    log.info("Iniciando coleta de vagas...")
    raw_jobs = collect_jobs(config)
    log.info("Total bruto: %d vagas", len(raw_jobs))

    # Filtra novas
    new_jobs = [j for j in raw_jobs if not db.is_seen(j["id"])]
    log.info("Não vistas antes: %d", len(new_jobs))

    if not new_jobs:
        log.info("Nada novo. Encerrando sem enviar email.")
        return 0

    # Pré-filtro por keyword — descarta vagas obviamente fora antes de gastar tokens
    keywords = config.get("keywords", [])
    candidates = []
    for j in new_jobs:
        if keyword_match(j, keywords):
            candidates.append(j)
        else:
            # marca como vista mesmo sem classificar — não vale gastar LLM nela de novo
            db.add(j["id"])
    log.info("Após pré-filtro por keyword: %d candidatas", len(candidates))

    if not candidates:
        log.info("Nenhuma vaga passou no pré-filtro. Encerrando.")
        return 0

    # Cap defensivo
    cap = config.get("filters", {}).get("max_llm_calls_per_run", 60)
    if len(candidates) > cap:
        log.warning("Excedeu cap de %d chamadas LLM; truncando.", cap)
        candidates = candidates[:cap]

    # Classifica
    classified = classify_jobs(candidates, config)

    # Marca todas como vistas
    for j in classified:
        db.add(j["id"])

    # Filtra por score mínimo
    min_score = config.get("filters", {}).get("min_fit_score_for_email", 40)
    relevant = [j for j in classified if j.get("fit_score", 0) >= min_score]
    log.info("Vagas relevantes (score >= %d): %d", min_score, len(relevant))

    if not relevant:
        # Weekly digest: manda email mesmo sem vagas, pra confirmar que o job rodou
        summary = (
            f"# Vagas acadêmicas — semanal\n\n"
            f"**Nenhuma vaga acima do threshold ({min_score}) esta semana.**\n\n"
            f"- Total bruto: {len(raw_jobs)}\n"
            f"- Não vistas: {len(new_jobs)}\n"
            f"- Após pré-filtro: {len(candidates)}\n"
            f"- Classificadas: {len(classified)}\n\n"
            f"_Fontes ativas: EURAXESS, Jobs.ac.uk, KTH, ITU Copenhagen, NTNU, Aalto_\n"
            f"_Fontes com erro: Academic Positions (403), Nature Careers (403), Aarhus (timeout)_\n"
        )
        html = markdown_to_html(summary)
        subject = "📋 Vagas acadêmicas — sem novidades esta semana"
        ok = send_email(subject, summary, html_body=html)
        if not ok:
            log.error("Email de digest falhou.")
            return 2
        log.info("Weekly digest enviado (sem vagas relevantes).")
        return 0

    # Relatório + email
    report = generate_report(relevant)
    html = markdown_to_html(report)

    strong = sum(1 for j in relevant if j.get("fit_category") == "Forte")
    possible = sum(1 for j in relevant if j.get("fit_category") == "Possível")
    subject = f"📋 Vagas acadêmicas — {strong} fit forte, {possible} possível"

    ok = send_email(subject, report, html_body=html)
    if not ok:
        log.error("Email falhou. Dump do relatório para recovery:")
        print(report)
        return 2

    log.info("Concluído. %d vagas no relatório.", len(relevant))
    return 0


if __name__ == "__main__":
    sys.exit(main())
