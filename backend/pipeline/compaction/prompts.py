"""Prompt templates for context compaction summarization."""

GAP_SUMMARY_PROMPT = """Summarize the following research gaps into a compact structured overview.
For each gap include: title (condensed), type, confidence score, and one-line impact.
Then list cluster themes.

Gaps:
{gaps_text}

Clusters:
{clusters_text}

Output format:
- One bullet per gap: "[type] Title (confidence X) — impact summary"
- One line for cluster themes: "Themes: A, B, C"
Keep total output under {target_tokens} tokens."""

CRITIQUE_SUMMARY_PROMPT = """Summarize the following idea critiques into key themes.
Group recurring weaknesses and suggestions. List unique high-value suggestions separately.

Critiques:
{critiques_text}

Output format:
"Common weaknesses: (1) ..., (2) ...
Key suggestions: (1) ..., (2) ...
Notable unique points: ..."
Keep total output under {target_tokens} tokens."""

REPORT_SUMMARY_PROMPT = """Compress the following novelty and feasibility assessment into a brief structured summary.

Novelty: overall={novelty_score}, method={method_novelty}, problem={problem_novelty}, domain_transfer={domain_transfer}, combination={combination_novelty}
Novelty arguments: {novelty_args}

Feasibility: overall={feasibility_score}/10, data={data_avail}, compute={compute_req}, methods={method_complexity}, eval={eval_plan}
Timeline: {timeline}
Key risks: {risks}

Output format (keep under {target_tokens} tokens):
"Novelty: X (highlights). Feasibility: Y/10 (key constraint: ...). Timeline: Z. Top risks: A, B." """
