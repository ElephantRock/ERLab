# Section-wise rerun (patched synthesizer)

Identity check is primacy-based: title + abstract opening must name
the ground-truth method. Stricter than the original run's substring-anywhere check.

| Cell | Passed | Identity | Markers | Conflicting in primacy | Error |
|---|---|---|---|---|---|
| ablation_context_only_section_wise_rep1 | PASS | Y | Y | [] |  |
| ablation_context_only_section_wise_rep2 | PASS | Y | Y | [] |  |
| ablation_context_only_section_wise_rep3 | PASS | Y | Y | [] |  |
| ablation_full_section_wise_rep1 | PASS | Y | Y | [] |  |
| ablation_full_section_wise_rep2 | PASS | Y | Y | [] |  |
| ablation_full_section_wise_rep3 | PASS | Y | Y | [] |  |
| ablation_markers_only_section_wise_rep1 | FAIL | N | Y | ['quantum', 'vqls', 'lubrication', 'bearing', 'reynolds'] |  |
| ablation_markers_only_section_wise_rep2 | FAIL | N | Y | ['quantum', 'vqls', 'lubrication', 'bearing', 'reynolds'] |  |
| ablation_markers_only_section_wise_rep3 | FAIL | N | Y | ['quantum', 'lubrication', 'bearing', 'reynolds'] |  |
| method_substitution_absurd_section_wise_rep1 | PASS | Y | Y | [] |  |
| method_substitution_absurd_section_wise_rep2 | PASS | Y | Y | [] |  |
| method_substitution_absurd_section_wise_rep3 | PASS | Y | Y | [] |  |
| method_substitution_plausible_section_wise_rep1 | PASS | Y | Y | [] |  |
| method_substitution_plausible_section_wise_rep2 | PASS | Y | Y | [] |  |
| method_substitution_plausible_section_wise_rep3 | PASS | Y | Y | [] |  |
| method_substitution_subtle_section_wise_rep1 | PASS | Y | Y | [] |  |
| method_substitution_subtle_section_wise_rep2 | PASS | Y | Y | [] |  |
| method_substitution_subtle_section_wise_rep3 | PASS | Y | Y | [] |  |

## By dimension (pass/total)

- ablation_context: 3/3 pass
- ablation_full: 3/3 pass
- ablation_markers: 0/3 pass
- method_substitution: 9/9 pass