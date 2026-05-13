def generate_report(jobs):
    lines = ["# Relatório de Vagas Acadêmicas\n"]
    
    for job in jobs:
        lines.append(f"## [{job['title']}]({job['url']})")
        lines.append(f"- **Univ/Empresa**: {job['company']} ({job['country']})")
        lines.append(f"- **Fit**: {job['fit_category']} ({job['fit_score']}/100)")
        lines.append(f"- **Justificativa**: {job['justification']}")
        lines.append("\n---\n")
        
    return "\n".join(lines)
