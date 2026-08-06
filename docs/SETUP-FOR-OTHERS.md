# Setting Up vagas-agent for a New Person

This guide explains how to take the `vagas-agent` codebase and set it up for a
different candidate: their own profile, their own keywords, their own email.
Everything person-specific lives in two places — `config.yaml` and the
classifier prompt in `src/classifier.py`. The rest of the system is generic.

## What the system does

Every Monday morning (GitHub Actions cron, 06:17 UTC), the agent:

1. Collects academic job postings from ~14 source groups (EURAXESS, Jobs.ac.uk,
   KTH, ITU Copenhagen, NTNU, Aalto, Varbi for 8 Swedish universities, Reachmee
   RSS for Konstfack/Malmö, Helsinki RSS, Nordic university pages, Jobbnorge API
   for all Norwegian universities, and more).
2. Deduplicates against a SQLite database (`data/seen.db`, keyed by job URL).
3. Pre-filters by keyword (cheap gate, saves LLM calls).
4. Scores each surviving job 0-100 with DeepSeek (`deepseek-chat`) against the
   candidate profile in `config.yaml`. Categories: Forte (70-100), Possível
   (50-69), Em Dúvida (40-49), Anotar (25-39), Fora (0-24).
5. Emails a ranked Markdown report via Resend. If nothing passes the threshold
   it still sends a "no news" digest with run stats — silence means something
   broke, not that there were no jobs.

## 0. What you need before starting

| Account | Purpose | Cost |
|---|---|---|
| GitHub | hosts the repo, runs the weekly cron | free |
| DeepSeek (platform.deepseek.com) | API key for job classification (`deepseek-chat`) | pay-as-you-go, a few cents/run |
| Resend (resend.com) | transactional email delivery | free tier: 100 emails/day |

That's it. You do not need a server, a Mac, or Python locally for production —
everything runs in GitHub's cloud.

## 1. Get the code

Fork the repository (GitHub's "Fork" button) or download/copy the folder and
push it to a new repo you own. Contents:

```
vagas-agent/
├── .github/workflows/weekly.yml   # cron + manual run button
├── src/
│   ├── main.py                    # orchestrator
│   ├── sources.py                 # the scrapers (14 source groups)
│   ├── classifier.py              # DeepSeek scoring prompt (PERSON-SPECIFIC)
│   ├── emailer.py                 # Resend email
│   ├── reporter.py                # Markdown report → HTML
│   └── storage.py                 # SQLite seen.db (dedup)
├── config.yaml                    # profile + keywords + thresholds (PERSON-SPECIFIC)
├── docs/universidades-escandinavia.md  # map of the Scandinavian sources
└── requirements.txt               # requests, beautifulsoup4, lxml, pyyaml
```

Public repos get unlimited GitHub Actions minutes, so keep it public unless you
have a reason not to.

## 2. Adapt config.yaml — the person-specific file

This is the most important step. Four sections:

### candidate_profile (free text)

Rewrite for the new person: field, seniority, methods, what they want.
Example shape (this is the original author's profile — replace entirely):

```yaml
candidate_profile: >
  Postdoc na KTH com foco em Embodied Design e Soma Design.
  Pesquisador híbrido: Arquitetura, Interação Humano-Computador (HCI) e Tecnologias Imersivas (XR/VR).
  Busca exclusivamente posições TENURE-TRACK ou TENURED.
  Postdocs comuns NÃO interessam.
```

Write it in the candidate's language (the classifier prompt is Portuguese, but
it handles other languages fine — just be consistent).

### keywords (list of strings)

Controls the pre-filter: a job must match at least one keyword in title or
description to reach the LLM. Two rules that matter a lot:

- **Include local-language terms.** Scandinavian sources list titles in Swedish,
  Norwegian, Danish, Finnish. Terms like `universitetslektor`, `doktorand`,
  `stipendiat`, `adjunkt`, `førsteamanuensis` must be in the list or relevant
  jobs die before the LLM ever sees them.
- **Job-level signals** (`assistant professor`, `tenure-track`, `lektor`,
  `professor`...) are deliberately in the list so the pre-filter lets things
  through and the LLM does the real filtering.

### countries (ISO codes)

Currently `SE, DK, NO, FI, NL, DE, UK, CH`. Change freely.

### filters

```yaml
filters:
  min_fit_score_for_email: 40   # 40-49 = "Em Dúvida", emailed for manual review
  max_llm_calls_per_run: 250    # cost/speed cap
  llm_model: "deepseek-chat"
```

`min_fit_score_for_email: 40` means borderline jobs reach the inbox so the
person decides. Raise it to 50 if they want fewer emails; lower it if they're
missing things.

## 3. Adapt the classifier prompt — also person-specific

`src/classifier.py` contains a long Portuguese prompt (PROMPT_TEMPLATE) that is
written for the original candidate. You must rewrite two parts for the new
person:

1. **Level rules.** The current prompt hard-caps common postdocs at score 25
   ("the candidate is already a postdoc") and excludes PhD positions. If the new
   person wants postdocs or PhD positions, this cap must be removed or changed —
   otherwise every postdoc gets scored out of the report.
2. **Fit areas.** The prompt lists strong-fit areas (HCI, Interaction Design,
   Design Research, RtD, Computational Design, XR...). Replace with the new
   person's actual field, and add explicit "this is NOT relevant" areas if
   useful. Do not keep labels the person does not identify with — the prompt
   will then look for jobs matching those labels.

The scoring philosophy is worth keeping: **recall over precision**. The prompt
tells the model to use common sense, not require exact terms, and when in doubt
score "Em Dúvida" (40-49) so the candidate decides instead of the job being
silently dropped.

## 4. Create the repo and push

```
git init
git add .
git commit -m "initial"
git branch -M main
git remote add origin https://github.com/YOU/vagas-agent.git
git push -u origin main
```

## 5. Set the secrets

Repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Value |
|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API key (platform.deepseek.com → API Keys) |
| `RESEND_API_KEY` | Resend API key (resend.com → API Keys) |
| `EMAIL_TO` | destination address — see the Resend note below |
| `EMAIL_FROM` | `onboarding@resend.dev` or your verified domain |

**Resend gotcha (important):** the address `onboarding@resend.dev` only delivers
to the email of the account owner. If `EMAIL_TO` is anyone else, Resend accepts
the request (HTTP 200) but silently drops the email. Either:
- set `EMAIL_TO` to the exact address you registered at Resend with, or
- verify your own domain in Resend (add DNS records) and use
  `EMAIL_FROM: vagas@yourdomain.com`.

Free tier limit is 100 emails/day — one weekly digest is nothing.

## 6. Run it

- **Manual first run:** GitHub → Actions → "Weekly Job Search" → "Run workflow"
  (workflow_dispatch button). A run takes ~9 minutes (up to 250 LLM calls with
  0.3s sleep between them). The email should arrive within minutes of finish.
- **Schedule:** the cron is `17 6 * * 1` (Monday 06:17 UTC ≈ 08:17 Stockholm
  CEST). The odd minutes are deliberate — GitHub Actions free tier is
  unreliable at exact-hour times. Change the expression in
  `.github/workflows/weekly.yml` if you want a different time.
- **Re-run:** the same "Run workflow" button anytime.

## 7. Local testing (optional)

You need Python 3.11+ and the dependencies (`pip install -r requirements.txt`).
Then, from the repo root:

```
python3 scripts/dry_run_pipeline.py
```

This runs collect → pre-filter → classify → report without sending email and
without marking jobs as seen. It needs `DEEPSEEK_API_KEY` in the environment —
export it first:

```
export DEEPSEEK_API_KEY=sk-...
python3 scripts/dry_run_pipeline.py
```

**If the key is missing, every job scores 0 and nothing reaches the email** —
the run "succeeds" but silently. This is the #1 cause of "no email" when
testing locally.

## What a run does to the repo

After each run, the workflow commits `data/seen.db` back to the repo so the next
run only classifies new jobs. Consequences:

- **Never edit/push local changes to seen.db.** If you push locally after a
  remote run, you get a binary merge conflict. Resolution:
  ```
  git checkout --theirs data/seen.db && git add data/seen.db && GIT_EDITOR=true git rebase --continue
  ```
- To force a full re-classification (e.g. after changing the prompt), delete
  seen.db locally and push, or just accept that only new jobs get scored.

## Tuning: diagnosing "no email for weeks"

1. Run `python3 scripts/dry_run_pipeline.py` locally (with the key) — the log
   shows raw collected counts and scores. You'll see why nothing passed.
2. If most relevant jobs score 40-55 → the threshold or prompt is too strict.
   Lower `min_fit_score_for_email` or soften the prompt.
3. If there simply are no jobs matching → the sources don't cover your
   geography/field. The current sources are Scandinavia-heavy (the original
   candidate works in Sweden). See `src/sources.py` and
   `docs/universidades-escandinavia.md`; add sources that fit the new person.
4. Seasonal effect: European academic hiring is dead in July-August. Don't tune
   the system in August.

## Known pitfalls (from production experience)

- **Scraper rot:** institutional DOMs change. The EURAXESS scraper is
  link-based (`a[href*="/jobs/"]`) because the old selectors broke. If a source
  returns 0 for weeks, that source's page layout probably changed — check it
  manually and fix the selector.
- **JobTeaser is blocked (403)** — Tampere/Lapland. Don't waste time; EURAXESS
  covers them.
- **Varbi subdomains:** only some Swedish universities run Varbi (uu, su, umu,
  kth, hh, kau, miun, ju). Others don't exist (gu, liu, chalmers...).
- **`git push || true`** in weekly.yml: if the push of seen.db fails, the
  workflow still shows green and the next run re-classifies everything. Known
  wart; fine for a solo user.
- **Node 20 deprecation warning** in Actions: the workflow sets
  `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` to silence it. Keep it.

## Maintenance cheat sheet

- Edit `config.yaml` or the classifier prompt → push → click "Run workflow".
- Want different sources? Edit `src/sources.py` — each source is a function
  returning a list of job dicts `{title, url, description, country, source}`.
- The dedup UUID is computed over the **full URL** — if you add a source whose
  job IDs live in query strings (e.g. `?rmjob=N`), keep the full URL, never
  truncate at `?`.
