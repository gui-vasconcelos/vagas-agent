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
