CATEGORY_LABELS = {
    "Forte": "Strong",
    "Possível": "Possible",
    "Em Dúvida": "Unsure",
    "Anotar": "Noted",
    "Fora": "Out",
    "Erro": "Error",
}


def generate_report(jobs):
    by_cat = {"Forte": [], "Possível": [], "Em Dúvida": [], "Anotar": [], "Fora": [], "Erro": []}
    for j in jobs:
        cat = j.get("fit_category", "Erro")
        by_cat.setdefault(cat, []).append(j)

    lines = ["# Weekly Academic Job Report", ""]
    lines.append(
        f"**Summary:** {len(by_cat['Forte'])} strong · "
        f"{len(by_cat['Possível'])} possible · "
        f"{len(by_cat['Em Dúvida'])} unsure · "
        f"{len(by_cat['Anotar'])} noted · "
        f"total: {len(jobs)}"
    )
    lines.append("")

    for cat, emoji in [
        ("Forte", "🟢"),
        ("Possível", "🟡"),
        ("Em Dúvida", "🟠"),
        ("Anotar", "⚪"),
    ]:
        items = by_cat[cat]
        if not items:
            continue
        label = CATEGORY_LABELS.get(cat, cat)
        if cat == "Em Dúvida":
            lines.append(f"## {emoji} {label} ({len(items)}) — review manually")
        else:
            lines.append(f"## {emoji} {label} ({len(items)})")
        lines.append("")
        for j in items:
            lines.append(f"### [{j['title']}]({j['url']})")
            lines.append(f"- **Institution**: {j['company']} ({j.get('country', '?')})")
            lines.append(f"- **Score**: {j.get('fit_score', '?')}/100")
            lines.append(f"- **Category**: {CATEGORY_LABELS.get(cat, cat)}")
            lines.append(f"- **Analysis**: {j.get('justification', '')}")
            lines.append("")
        lines.append("---")
        lines.append("")

    if not any(by_cat[c] for c in ("Forte", "Possível", "Em Dúvida", "Anotar")):
        lines.append("_No relevant jobs in the sources this week._")

    return "\n".join(lines)


def markdown_to_html(md):
    """Conversão simples — Resend renderiza HTML, então um wrapper estilizado ajuda."""
    html_lines = ["<!DOCTYPE html><html><head><meta charset='utf-8'><style>",
                  "body{font-family:-apple-system,sans-serif;max-width:760px;margin:2em auto;color:#222;line-height:1.5;padding:0 1em}",
                  "h1{font-size:1.4em;border-bottom:2px solid #333;padding-bottom:.3em}",
                  "h2{font-size:1.15em;margin-top:2em;color:#444}",
                  "h3{font-size:1em;margin-bottom:.3em}",
                  "a{color:#246}",
                  "hr{border:none;border-top:1px solid #ddd;margin:1em 0}",
                  "</style></head><body>"]
    for line in md.split("\n"):
        if line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{_render_inline(line[4:])}</h3>")
        elif line.startswith("- "):
            html_lines.append(f"<p style='margin:.2em 0'>{_render_inline(line[2:])}</p>")
        elif line.strip() == "---":
            html_lines.append("<hr>")
        elif line.strip() == "":
            html_lines.append("")
        else:
            html_lines.append(f"<p>{_render_inline(line)}</p>")
    html_lines.append("</body></html>")
    return "\n".join(html_lines)


def _render_inline(text):
    # Markdown links [texto](url)
    import re
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return text
