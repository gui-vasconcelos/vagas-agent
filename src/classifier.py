import os
import requests
import json
import time
import logging

log = logging.getLogger(__name__)

URL = "https://api.deepseek.com/v1/chat/completions"

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
   Use BOM SENSO — o candidato é interdisciplinar (Arquitetura + HCI). Uma vaga não precisa
   mencionar os termos exatos da pesquisa dele pra ser relevante. Se a descrição sugere que
   o perfil dele se encaixa, seja generoso.

   - FIT FORTE (70-100): Vaga tenured/tenure-track em HCI, Interaction Design, Design Research,
     Research-through-Design, Computational Design, Spatial Computing, Arquitetura Digital,
     Media Architecture, Interactive Architecture, Creative Technology, Tangible Interaction,
     XR/VR/AR, Game Design, Real-time Environments,
     ou qualquer área onde a combinação Arquitetura+HCI do candidato seja um diferencial claro.
     Soma Design, Fenomenologia, slow technology, RtD, experiência em Unity/Unreal são bônus,
     não requisito.
   - POSSÍVEL (50-69): Vaga tenured/tenure-track em área fronteiriça: Computer Science com
     abertura pra HCI, Architecture com ênfase digital ou midiática, Media Technology,
     Information Studies com componente de design, Digital Humanities com interface interativa,
     Architectural Technology. O candidato se encaixa, mas não é o perfil óbvio.
   - EM DÚVIDA (40-49): Vaga tenure-track em área tangente onde você não tem certeza se o
     candidato se encaixa. Pode ser que sim, pode ser que não. Use esta categoria quando
     a descrição for vaga, genérica, ou ambígua demais pra decidir. Ex: "Assistant Professor
     in Computer Science" sem especificar área — talvez tenha slot HCI, talvez não. Essas
     vagas vão para revisão manual do candidato.
   - ANOTAR (25-39): Vaga tenure-track claramente fora da área do candidato (CS puro,
     ML/Dados, IT, Arquitetura tradicional), mas que por algum motivo específico pode
     ser interessante (localização, prestígio, salário).
   - FORA (0-24): Vaga fora do perfil (CS algorítmico, ML/data science, IT, arquitetura
     tradicional sem tech), OU qualquer postdoc comum / PhD position.

   IMPORTANTE: quando estiver em dúvida, use "EM DÚVIDA" (40-49) em vez de "ANOTAR" ou
   "FORA". É melhor o candidato ver uma vaga duvidosa e decidir por si mesmo do que
   perder uma oportunidade.

VAGA A AVALIAR:
Título: {title}
Empresa: {company}
País: {country}
Descrição: {description}

Retorne APENAS um JSON válido:
{{
    "fit_score": (inteiro 0-100),
    "fit_category": "Forte" | "Possível" | "Em Dúvida" | "Anotar" | "Fora",
    "justification": "2 lines in English. ALWAYS mention the job level (postdoc, tenure-track, etc) and why the score was given."
}}
"""


def classify_jobs(jobs, config):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        log.error("DEEPSEEK_API_KEY não configurada")
        return jobs

    model = config.get("filters", {}).get("llm_model", "deepseek-chat")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
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
