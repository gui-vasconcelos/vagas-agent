import os
import requests
import json
import time
import logging

log = logging.getLogger(__name__)

URL = "https://openrouter.ai/api/v1/chat/completions"

PROMPT_TEMPLATE = """
Você é um recrutador acadêmico sênior especializado em perfis interdisciplinares (Arquitetura + HCI).

PERFIL DO CANDIDATO:
{profile}

CRITÉRIOS DE AVALIAÇÃO:
- FIT FORTE (90-100): Menciona Soma Design, Embodied Interaction, ou Pesquisa em Arquitetura com XR/VR/Fenomenologia.
- POSSÍVEL (60-89): Interaction Design generalista, Computational Design, ou HCI experimental.
- ANOTAR (10-59): Computer Science tradicional, TI puro, ou Arquitetura sem tech.
- FORA (0-9): PhD position, vaga industrial pura, ML/data science, completamente fora.

VAGA:
Título: {title}
Empresa: {company}
País: {country}
Descrição: {description}

Retorne APENAS um JSON válido:
{{
    "fit_score": (inteiro 0-100),
    "fit_category": "Forte" | "Possível" | "Anotar" | "Fora",
    "justification": "2 linhas sobre a conexão Arq/HCI/Soma, em português"
}}
"""


def classify_jobs(jobs, config):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        log.error("OPENROUTER_API_KEY não configurada")
        return jobs

    model = config.get("filters", {}).get("llm_model", "google/gemini-2.0-flash-001")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vagas-agent",
        "X-Title": "Academic Job Agent",
    }

    classified = []
    for i, job in enumerate(jobs):
        log.info("Classificando %d/%d: %s", i + 1, len(jobs), job["title"][:60])
        prompt = PROMPT_TEMPLATE.format(
            profile=config["candidate_profile"],
            title=job["title"],
            company=job["company"],
            country=job.get("country", ""),
            description=job["description"][:2000],
        )

        result = None
        for attempt in range(3):
            try:
                r = requests.post(URL, headers=headers, json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Você é um classificador acadêmico que responde apenas em JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                }, timeout=30)
                resp = r.json()
                if "choices" in resp:
                    content = resp["choices"][0]["message"]["content"]
                    result = json.loads(content)
                    break
                log.warning("OpenRouter sem 'choices' (tentativa %d): %s", attempt + 1, resp)
            except Exception as e:
                log.warning("Erro na classificação (tentativa %d): %s", attempt + 1, e)
            time.sleep(2 ** attempt)

        if result is None:
            result = {
                "fit_score": 0,
                "fit_category": "Erro",
                "justification": "Falha na comunicação com o LLM após múltiplas tentativas.",
            }
        job.update(result)
        classified.append(job)
        time.sleep(0.3)  # cortesia ao rate limit

    return sorted(classified, key=lambda x: x.get("fit_score", 0), reverse=True)
