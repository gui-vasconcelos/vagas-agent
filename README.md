# vagas-agent

Automated academic job search: every Monday, a GitHub Actions workflow collects
~900-1000 academic job postings from 14 source groups (EURAXESS, Jobs.ac.uk,
KTH, Varbi for 8 Swedish universities, Jobbnorge API for all Norwegian
universities, and more), scores each one against a candidate profile using
DeepSeek's LLM, and emails a ranked report via Resend.

This README is the full onboarding guide for a new user. Everything
person-specific lives in two files — `config.yaml` and the classifier prompt in
`src/classifier.py` — and everything account-related lives in GitHub Secrets.
No servers, no local Python, nothing to keep running: GitHub's cloud does it all.

## How it works

```
every Monday 06:17 UTC (GitHub Actions cron)
  └─ collect jobs from 14 source groups          (src/sources.py)
  └─ deduplicate against SQLite seen.db          (src/storage.py)
  └─ keyword pre-filter (cheap gate, saves LLM)  (src/main.py)
  └─ score each job 0-100 via DeepSeek           (src/classifier.py)
  └─ rank + build Markdown report                (src/reporter.py)
  └─ email the report via Resend                 (src/emailer.py)
  └─ commit seen.db back to the repo
```

If nothing passes the threshold it still sends a "no news" digest with run
stats — silence means something broke, not that there were no jobs.

---

## Accounts to create (3 services)

You need exactly three accounts. All have free tiers sufficient for this
project. Follow each section in order and copy the API keys when the screen
shows them — every key is displayed only once.

### 1. GitHub — hosts the repo and runs the weekly cron

**Cost:** free. Public repos get unlimited Actions minutes.

1. Go to https://github.com/signup
2. Enter your email → click "Continue".
3. Create a password (min 15 chars, or passphrase) → continue.
4. Enter a username (this becomes your repo URL, e.g. `github.com/yourname/`) → continue.
5. Choose whether to receive product updates → continue.
6. GitHub sends a verification puzzle ("Verify your account") → solve it.
7. Check your inbox for the verification email from GitHub → click the
   "Verify email address" button.
8. Pick the **Free** plan (Personal) → "Continue".
9. GitHub may ask for a phone number to verify the account — enter it.
   This is a one-time anti-abuse check, not a subscription.
10. You now have an account. You do NOT need any GitHub API key or token for
    this project — the workflow authenticates itself automatically.

Recommended (optional): enable two-factor authentication later under
Settings → Password and authentication → Two-factor authentication.

### 2. DeepSeek — the LLM that scores each job

**Cost:** prepaid credits, pay-as-you-go. `deepseek-chat` costs about
$0.27 per million input tokens — a full weekly run (up to 250 classified jobs)
costs a few cents, well under $1/month.

1. Go to https://platform.deepseek.com → "Sign up".
2. Register with your email (or phone) → enter the verification code you
   receive → set a password.
3. **Top up credits BEFORE using the API.** API usage is prepaid — the
   classifier returns errors (and every job scores 0) until the balance is
   positive. Left sidebar → "充值 / Top up" → choose an amount (minimum top-up
   is about ¥10, roughly $1.50) → pay.
   - **Payment methods: Alipay or WeChat Pay** (Chinese payment methods).
     If you don't have either, use the OpenRouter fallback in the box below —
     this project ran on OpenRouter until May 2026, it is a proven path.
4. Create the API key: left sidebar → "API Keys" → "Create new API key" →
   give it a name (e.g. `vagas-agent`) → click Create.
5. **Copy the key immediately** — it looks like `sk-...` and is shown exactly
   once. Save it in your password manager. This becomes `DEEPSEEK_API_KEY`.

> **Fallback: OpenRouter** (if you cannot pay with Alipay/WeChat)
>
> 1. Create an account at https://openrouter.ai (accepts international credit
>    cards) → add a small credit balance.
> 2. Keys → Create key → copy it (format `sk-or-v1-...`).
> 3. In `src/classifier.py`, change the line
>    `URL = "https://api.deepseek.com/v1/chat/completions"` to
>    `URL = "https://openrouter.ai/api/v1/chat/completions"`.
> 4. Use the OpenRouter key as `DEEPSEEK_API_KEY` in the GitHub secrets
>    (step "Set the secrets" below). Everything else stays the same.

### 3. Resend — sends the weekly email

**Cost:** free tier = 100 emails/day. The weekly digest uses 1.

1. Go to https://resend.com/signup → sign up with your email and a password
   (or "Sign in with GitHub/Google").
2. Verify your email with the code Resend sends you.
3. Create the API key: left sidebar → **API Keys** → "Create API Key" →
   name it `vagas-agent` → click Create.
4. **Copy the key immediately** — it looks like `re_...` and is shown exactly
   once. This becomes `RESEND_API_KEY`.
5. Decide your sender address (`EMAIL_FROM`):

   **Option A — simplest (use for the first run):**
   Use `EMAIL_FROM: onboarding@resend.dev` and set `EMAIL_TO` to **the exact
   email address you registered at Resend with**. This is a hard constraint:
   the `onboarding@resend.dev` address only delivers to the account owner's
   inbox. If `EMAIL_TO` is anyone else, Resend accepts the request (HTTP 200)
   but silently drops the email.

   **Option B — your own domain (recommended before going live):**
   Resend → Settings → **Domains** → Add Domain → enter your domain (e.g.
   `yourname.com`) → Resend shows 3 DNS records to add at your DNS provider
   (one SPF TXT, one DKIM, one MX for bounce handling) → add them → wait for
   the status to become "Verified" (minutes to a few hours) → then use
   `EMAIL_FROM: vagas@yourname.com`, and `EMAIL_TO` can be any address you own.

---

## Project setup

### 1. Get the code

Fork this repository (GitHub's "Fork" button) or download the folder and push
it to a repo you own. Structure:

```
vagas-agent/
├── .github/workflows/weekly.yml   # cron + manual "Run workflow" button
├── src/
│   ├── main.py                    # orchestrator
│   ├── sources.py                 # the 14 source groups (scrapers)
│   ├── classifier.py              # DeepSeek scoring prompt (PERSON-SPECIFIC)
│   ├── emailer.py                 # Resend email
│   ├── reporter.py                # Markdown report → HTML
│   └── storage.py                 # SQLite seen.db (dedup)
├── config.yaml                    # profile + keywords + thresholds (PERSON-SPECIFIC)
├── docs/universidades-escandinavia.md  # map of the Scandinavian sources
└── requirements.txt
```

Keep the repo **public** (unlimited Actions minutes). If it must be private,
the free quota of 2,000 Actions minutes/month is still far more than one
~9-minute run per week.

### 2. Adapt config.yaml — the person-specific file

Four sections to rewrite for the new candidate:

**`candidate_profile`** (free text) — who the candidate is: field, seniority,
methods, what they want. Written in the classifier's scoring language (the
prompt is Portuguese; keep the profile consistent with it or translate both).
Example shape (replace entirely with the real profile):

```yaml
candidate_profile: >
  Pesquisador híbrido: Arquitetura e Interação Humano-Computador (HCI).
  Busca exclusivamente posições TENURE-TRACK ou TENURED.
  Postdocs comuns NÃO interessam.
```

**`keywords`** (list of strings) — the pre-filter: a job must match at least
one keyword in its title/description to reach the LLM. Two rules:

- **Include local-language terms.** Scandinavian sources list titles in
  Swedish/Norwegian/Danish/Finnish: `universitetslektor`, `doktorand`,
  `stipendiat`, `adjunkt`, `førsteamanuensis` must be in the list or relevant
  jobs die before the LLM sees them.
- **Job-level signals** (`assistant professor`, `tenure-track`, `lektor`,
  `professor`...) are deliberately present so the pre-filter lets things
  through and the LLM does the real filtering.

**`countries`** — ISO codes, currently `SE, DK, NO, FI, NL, DE, UK, CH`.
Change freely.

**`filters`**:

```yaml
filters:
  min_fit_score_for_email: 40   # 40-49 = "Em Dúvida", emailed for manual review
  max_llm_calls_per_run: 250    # cost/speed cap
  llm_model: "deepseek-chat"
```

`min_fit_score_for_email: 40` means borderline jobs reach the inbox so the
candidate decides. Raise to 50 for fewer emails, lower for more coverage.

### 3. Adapt the classifier prompt — also person-specific

`src/classifier.py` contains a long Portuguese prompt (`PROMPT_TEMPLATE`)
written for the original candidate. Rewrite two parts:

1. **Level rules.** The current prompt hard-caps common postdocs at score 25
   ("the candidate is already a postdoc") and excludes PhD positions. If the
   new candidate wants postdocs/PhD positions, remove or change this cap —
   otherwise those jobs never make it into the report.
2. **Fit areas.** The prompt lists strong-fit areas (HCI, Interaction Design,
   Design Research, RtD, Computational Design, XR...). Replace with the new
   candidate's field, and drop any labels they do not identify with.

Keep the scoring philosophy: **recall over precision**. The prompt tells the
model to use common sense, not require exact terms, and when in doubt score
"Em Dúvida" (40-49) so the candidate decides instead of the job being silently
dropped.

### 4. Create the repo and push

```
git init
git add .
git commit -m "initial"
git branch -M main
git remote add origin https://github.com/YOURNAME/vagas-agent.git
git push -u origin main
```

### 5. Set the secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**
— create four:

| Secret | Value |
|---|---|
| `DEEPSEEK_API_KEY` | the `sk-...` key from step "DeepSeek" (or the OpenRouter fallback key) |
| `RESEND_API_KEY` | the `re_...` key from step "Resend" |
| `EMAIL_TO` | destination address (see the onboarding@resend.dev constraint above) |
| `EMAIL_FROM` | `onboarding@resend.dev` or your verified `vagas@yourdomain.com` |

### 6. Run it

- **Manual first run:** GitHub → Actions → "Weekly Job Search" → **Run
  workflow**. A run takes ~9 minutes (up to 250 LLM calls, 0.3s apart). The
  email arrives within minutes of the run finishing.
- **Schedule:** the cron is `17 6 * * 1` — Monday 06:17 UTC (≈ 08:17
  Stockholm CEST). The odd minutes are deliberate: GitHub Actions free tier is
  unreliable at exact-hour times. Edit `.github/workflows/weekly.yml` to
  change it.
- **Re-run anytime:** same "Run workflow" button.

### 7. Local testing (optional)

Python 3.11+, then from the repo root:

```
pip install -r requirements.txt
export DEEPSEEK_API_KEY=sk-...      # the real key
python3 scripts/dry_run_pipeline.py
```

This runs collect → pre-filter → classify → report without sending email and
without marking jobs as seen. **If the key is missing, every job scores 0 and
nothing reaches the email — the run "succeeds" but silently.** This is the #1
cause of "no email" when testing locally.

---

## What a run does to the repo

After each run the workflow commits `data/seen.db` back to the repo so the
next run only classifies new jobs.

- **Never edit/push local changes to seen.db.** If you push locally after a
  remote run, you get a binary merge conflict. Resolution:
  ```
  git checkout --theirs data/seen.db && git add data/seen.db && GIT_EDITOR=true git rebase --continue
  ```
- To force a full re-classification (e.g. after changing the prompt), delete
  `data/seen.db` and push.

## Tuning: diagnosing "no email for weeks"

1. Run the local dry-run (step 7) — the log shows raw collected counts and
   per-job scores, so you can see exactly why nothing passed.
2. Most relevant jobs score 40-55 → threshold or prompt too strict. Lower
   `min_fit_score_for_email` or soften the prompt.
3. No relevant jobs at all → the sources don't cover your geography/field.
   The current sources are Scandinavia-heavy (the original candidate works in
   Sweden). See `src/sources.py` and `docs/universidades-escandinavia.md`;
   add sources that fit the new candidate.
4. Seasonal effect: European academic hiring is dead in July-August. Don't
   tune the system in August.

## Known pitfalls

- **Scraper rot:** institutional DOMs change. The EURAXESS scraper is
  link-based (`a[href*="/jobs/"]`) because the old selectors broke. If a
  source returns 0 for weeks, its page layout probably changed — fix the
  selector.
- **JobTeaser is blocked (403)** — Tampere/Lapland. Don't waste time;
  EURAXESS covers them.
- **Varbi subdomains:** only some Swedish universities run Varbi (uu, su, umu,
  kth, hh, kau, miun, ju). Others don't exist (gu, liu, chalmers...).
- **`git push || true`** in weekly.yml: if the seen.db push fails, the
  workflow still shows green and the next run re-classifies everything. Known
  wart; fine for a solo user.

## Maintenance cheat sheet

- Edit `config.yaml` or the classifier prompt → push → click "Run workflow".
- Want different sources? Edit `src/sources.py` — each source is a function
  returning a list of job dicts `{title, url, description, country, source}`.
- The dedup UUID is computed over the **full URL** — if you add a source whose
  job IDs live in query strings (e.g. `?rmjob=N`), keep the full URL, never
  truncate at `?`.
