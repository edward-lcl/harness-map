#!/usr/bin/env python3
"""Validate Phase 2 (114-probe) findings vs Phase 1 (44-probe)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from harness_map.probe.differ import diff_snapshots

# Phase 1 snapshots (44-probe)
P1_HAIKU = "capsnap-claude-haiku-4-5-2026-04-19-b10f7ecb66a5-20260419T025244Z"
P1_SONNET = "capsnap-claude-sonnet-4-6-2026-04-19-b10f7ecb66a5-20260419T025246Z"
P1_OPUS = "capsnap-claude-opus-4-7-2026-04-19-b10f7ecb66a5-20260419T025248Z"

# Phase 2 snapshots (114-probe)
P2_HAIKU = "capsnap-claude-haiku-4-5-2026-04-19-98450254fea0-20260419T041725Z"
P2_SONNET = "capsnap-claude-sonnet-4-6-2026-04-19-98450254fea0-20260419T041727Z"
P2_OPUS = "capsnap-claude-opus-4-7-2026-04-19-98450254fea0-20260419T041729Z"

print("\n" + "=" * 80)
print("PHASE 2 EXPANSION VALIDATION")
print("=" * 80)
print(f"\nPhase 1: 44-probe battery (shared across tiers)")
print(f"Phase 2: 114-probe battery (expanded + new categories)")
print(f"\n")

# Part 1: Cross-tier drift on Phase 2 corpus
print("▸ PHASE 2 CROSS-TIER DRIFT (114-probe)")
print("  " + "-" * 76)

pairs_p2 = [
    ("Haiku", P2_HAIKU, "Sonnet", P2_SONNET),
    ("Haiku", P2_HAIKU, "Opus", P2_OPUS),
    ("Sonnet", P2_SONNET, "Opus", P2_OPUS),
]

results_p2 = {}

for model_a, snap_a, model_b, snap_b in pairs_p2:
    print(f"  {model_a} vs {model_b}...", end=" ", flush=True)
    try:
        drift = diff_snapshots(snap_a, snap_b)
        score = drift.aggregate_drift_score
        severity = drift.severity
        results_p2[f"{model_a} vs {model_b}"] = {"score": score, "severity": severity}
        print(f"✓ {score:.3f} ({severity})")
    except Exception as e:
        print(f"✗ ERROR: {e}")
        results_p2[f"{model_a} vs {model_b}"] = {"error": str(e)}

# Part 2: Within-tier expansion impact (Phase 1 vs Phase 2 on same tier)
print("\n▸ WITHIN-TIER EXPANSION IMPACT (44-probe vs 114-probe)")
print("  " + "-" * 76)

expansion_pairs = [
    ("Haiku", P1_HAIKU, P2_HAIKU),
    ("Sonnet", P1_SONNET, P2_SONNET),
    ("Opus", P1_OPUS, P2_OPUS),
]

expansion_results = {}

for model, snap_p1, snap_p2 in expansion_pairs:
    print(f"  {model} (temporal)...", end=" ", flush=True)
    try:
        drift = diff_snapshots(snap_p1, snap_p2)
        score = drift.aggregate_drift_score
        severity = drift.severity
        expansion_results[model] = {"score": score, "severity": severity}
        print(f"✓ {score:.3f} ({severity})")
    except Exception as e:
        print(f"✗ ERROR: {e}")
        expansion_results[model] = {"error": str(e)}

# Part 3: Compare to Phase 1 cross-tier
print("\n" + "=" * 80)
print("COMPARISON: PHASE 1 vs PHASE 2 DRIFT SIGNATURES")
print("=" * 80 + "\n")

phase1_baseline = {
    "Haiku vs Sonnet": 0.878,
    "Haiku vs Opus": 0.792,
    "Sonnet vs Opus": 0.792,  # Updated from earlier validation
}

print("Cross-tier drift stability (44-probe vs 114-probe):\n")

consistency_count = 0

for pair, p1_score in phase1_baseline.items():
    p2_result = results_p2.get(pair, {})
    if "score" in p2_result:
        p2_score = p2_result["score"]
        delta = abs(p2_score - p1_score)
        is_consistent = delta < 0.10  # <10% for expanded corpus
        symbol = "✓" if is_consistent else "⚠"
        status = "STABLE" if is_consistent else "SHIFTED"
        consistency_count += is_consistent
        
        print(f"{symbol} {pair}")
        print(f"    Phase 1 (44):   {p1_score:.3f}")
        print(f"    Phase 2 (114):  {p2_score:.3f}")
        print(f"    Delta:          {delta:.3f} — {status}")
        print()

# Part 4: Within-model temporal drift on expanded corpus
print("=" * 80)
print("WITHIN-MODEL TEMPORAL DRIFT (on expanded 114-probe corpus)")
print("=" * 80 + "\n")

for model, result in expansion_results.items():
    if "score" in result:
        score = result["score"]
        severity = result["severity"]
        print(f"▸ {model}: {score:.3f} ({severity})")
        if score > 0.25:
            print(f"  ⚠️  Higher than Phase 1 baseline (0.173). Expansion added variable probes?")
        else:
            print(f"  ✓ Consistent with Phase 1 baseline (0.173)")

print("\n" + "=" * 80)
print("VERDICT")
print("=" * 80 + "\n")

if consistency_count == 3:
    print("✅ PHASE 2 EXPANSION VALIDATED")
    print("")
    print("Cross-tier drift signature STABLE across 44→114 probe expansion.")
    print("Conclusion: Findings are robust to corpus size increase.")
    print("")
    print("Recommendation: Ready for publication with expanded corpus.")
elif consistency_count >= 2:
    print("✓ MOSTLY STABLE")
    print(f"  {consistency_count}/3 pairs within tolerance. Some minor shifts observed.")
    print("  Likely due to new category distribution. Still publication-ready.")
else:
    print("⚠ CAUTION: Significant shifts observed")
    print("  New probes may be changing the signal. Recommend human review of delta.")

print()
