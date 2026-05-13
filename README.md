# Agente de Monitoramento de Vagas Acadêmicas (HCI/Soma Design)

Este agente automatiza a busca e classificação de vagas acadêmicas (Postdoc, Professor Assistente, etc.) com foco no perfil de pesquisa de Gui Vasconcelos.

## Configuração

1. **GitHub Secrets**: Adicione as seguintes chaves em `Settings -> Secrets and variables -> Actions`:
   - `OPENROUTER_API_KEY`
   - `RESEND_API_KEY`
   - `EMAIL_TO`: Seu email para receber os relatórios.
   - `EMAIL_FROM`: (Opcional) Seu email verificado no Resend.

2. **Personalização**: Edite `config.yaml` para ajustar palavras-chave ou o perfil enviado para o LLM.

## Como Funciona
O script roda toda segunda-feira via GitHub Actions, coleta vagas de fontes configuradas em `src/sources.py`, filtra as já vistas usando um banco SQLite (cacheado no GitHub Actions), e usa o Gemini Flash via OpenRouter para avaliar o "Fit" acadêmico de cada vaga.
