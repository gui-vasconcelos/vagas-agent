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

REGRAS DE PONTUAÇÃO:

1. NÍVEL DA VAGA (filtro duro):
   - O candidato JÁ ESTÁ em postdoc na KTH. Postdoc comum = score MÁXIMO 25 (categoria "Fora"),
     mesmo que o conteúdo de pesquisa seja perfeito.
   - PhD position = score 0-10 (categoria "Fora"). Sem exceções.
   - Posições válidas (podem ter score alto): Assistant Professor com tenure-track,
     Associate Professor, Lektor (Suécia), Universitetslektor, Biträdande Lektor (com path
     para tenure), Førsteamanuensis (Noruega), Senior Lecturer (UK), Lecturer (UK, equivale a
     Assistant Prof), Professor, qualquer "tenured" ou "tenure-track" explícito.
   - EXCEÇÃO postdoc: se a vaga menciona EXPLICITAMENTE "tenure-track fellow", "Wallenberg
     Academy Fellow", "Research Fellow com path para tenure", ou similar, pode chegar até
     score 70 se o conteúdo encaixar. Postdoc Marie Curie sozinho NÃO é exceção (é mais um
     postdoc, mesmo que prestigioso).

2. FIT DE CONTEÚDO (aplicado só se nível passa):
   - FIT FORTE (80-100): Vaga tenured/tenure-track que menciona Soma Design, Embodied Interaction,
     Arquitetura+XR/VR/Fenomenologia, Design Research interdisciplinar, ou Spatial Computing com
     ângulo humano.
   - POSSÍVEL (50-79): Vaga tenured/tenure-track em Interaction Design generalista, HCI
     experimental, Computational Design, Digital Design, Media Technology.
   - ANOTAR (25-49): Vaga tenured/tenure-track em área tangente (Computer Science com slot
     HCI, Architecture com componente digital, Media Studies).
   - FORA (0-24): Vaga fora do perfil (CS puro algorítmico, ML/data science, IT, arquitetura
     tradicional sem tech), OU qualquer postdoc comum / PhD position.

VAGA A AVALIAR:
Título: {title}
Empresa: {company}
País: {country}
Descrição: {description}

Retorne APENAS um JSON válido:
{{
    "fit_score": (inteiro 0-100),
    "fit_category": "Forte" | "Possível" | "Anotar" | "Fora",
    "justification": "2 linhas em português. SEMPRE mencione o nível da vaga (postdoc, tenure-track, etc) e por que o score foi esse."
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
