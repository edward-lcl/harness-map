# harness-map

> Continuous audit of the AI harness layer — the orchestration, tools, skills, sub-agents, and behavioral training that sit between base models and deployed capability.

## Why This Exists

Frontier AI labs ship black-box harnesses on top of their base models. Public visibility exists only at the surface (docs) and via episodic jailbreaks (e.g., elder-plinius/CL4R1T4S). Nobody continuously maps the full stack across versions.

The **harness is the product**; the model is a component. Mapping it is both a research contribution (alignment-upstream thesis) and a commercial capability (audit for infrastructure clients).

## The 7 Layers

| Layer | Content | Our Work |
|---|---|---|
| L1 | Published prompts | Baseline ingest |
| L2 | Leaked consumer prompts | **Phase 1** — passive watcher |
| L3 | Tool names + schemas | Phase 1 Week 4–6 |
| L4 | Skill contents | Phase 1 Week 4–6 |
| L5 | Orchestration prompts | Phase 2 — harness mapper |
| L6 | Training-baked behaviors | Phase 1 Week 2–3 — probe battery |
| L7 | Safety classifier outputs | Phase 2 |

## Phase 1 — Levi Infrastructure (Weeks 1–8)

Research-grade, publishable. Build thesis + reputation + dataset.

- **Week 1:** `watcher/anthropic_prompt_watch.py` — L2 passive monitoring, hourly cron, diff-on-change, Discord notify.
- **Week 2–3:** Behavioral probe battery (L6).
- **Week 4–6:** Tool schema + skill content extractors (L3/L4).

## Phase 2 — Node:Security Commercial (Months 3+)

Productize once methodology proven + dataset 3+ months deep.

- Harness mapper (L5).
- Full jailbreak agent (continuous, not episodic).
- Commercial offering: "continuous audit of the AI substrate."

## Red Lines (Non-Negotiable)

**Never public:**
- Working jailbreak recipes
- L5/L6/L7 extraction pipelines
- Client-specific findings

**Public:**
- L1/L2 diffs and meta-analyses
- Thesis work on alignment-upstream
- Shape of findings (not recipes)

**Conditionally public (invite-only research groups):**
- L3/L4/L5 structural findings
- Harness maps (shape, not content)

## Security Framing

External content ingested by this repo (leaked prompts, scraped pages) is treated as `EXTERNAL_UNTRUSTED`. Sanitization layer strips known prompt-injection markers before any LLM processing. Pattern-matching metadata extraction preferred over LLM summarization where possible.

## Thesis Connection

> **"Alignment is upstream of the model."**

Prompt-layer and training-layer decisions at frontier labs diffuse through the ecosystem — fine-tunes inherit patterns, derivative harnesses copy verification flows, safety rules propagate. This program generates the empirical dataset for that claim.

## Publication Cadence

**Milestone-based**, not calendar-based. Publish when findings warrant it. Candidate milestones:
- First captured material prompt change with diffusion evidence
- Cross-version behavioral drift detected in probe battery
- Harness graph completion for a given surface

## License

TBD — not currently public. See `NOTICE.md` when the repo opens.

## Related

- `/mnt/volume_nyc3_01/obsidian-vault/blueprint/Projects/Wisdom Architecture/Harness Map Program.md` — master program doc
- `/mnt/volume_nyc3_01/obsidian-vault/blueprint/Projects/Wisdom Architecture/Harness Map — Layer Glossary.md` — L1–L7 reference
- `/mnt/volume_nyc3_01/obsidian-vault/blueprint/essay-alignment-upstream-of-model.md` — thesis
