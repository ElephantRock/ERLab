# Paper Revision Plan: v2

## Changes Based on Autoresearch Study + DeepSeek Critique

### 1. Add Section 2.9: The Karpathy Loop as Meta-Architecture
- Autoresearch (Karpathy's original) is itself a self-improvement system
- Core loop: Modify → Verify → Keep/Discard → Repeat
- 7 universal principles: Constraint=Enabler, Strategy≠Tactics, Mechanical Metrics, Fast Verification, Iteration Cost→Behavior, Git as Memory, Honest Limitations
- Claude Autoresearch generalizes this to any domain with 10 subcommands
- The autoresearch loop IS a form of evolutionary optimization applied to code
- Key insight: self-improvement at the CODE level (not just prompt/output level)
- This is an 8th system that was missing from the original analysis

### 2. Add Missing Systems (DeepSeek §2.2)
- STaR (Self-Taught Reasoner) — bootstrapping reasoning via rationale generation
- Quiet-STaR — internal rationales at every token
- SPIN (Self-Play Fine-Tuning) — model vs its own previous iteration
- Constitutional AI self-play dynamics

### 3. Deepen R-Zero Analysis (DeepSeek §2.1)
- Self-play is more general than math reasoning
- Connection to multi-agent gap (0.95) is stronger than acknowledged
- SPIN, Constitutional AI, XLand connections
- Revise Section 7.1 to be more nuanced

### 4. Add AutoML/DARTS Connection for ADAS (DeepSeek §2.4)
- Differentiable architecture search could reduce ADAS search cost
- Continuous relaxation techniques for textual/architectural spaces
- Weight-sharing methods

### 5. Add "Improvement Per Token" Metric (DeepSeek §2.3)
- The design space table needs a cost-effectiveness dimension
- Reflexion/Self-Refine have low improvement ceilings despite high scalability
- EvoPrompt's sample inefficiency

### 6. Reorder Research Directions (DeepSeek §3)
- Direction 2 (Benchmarks) should be #1 — instrumentation gap
- Add Direction 6: Self-Improving Reward/Critique Functions
- Note on PC-LLM-Swarm: lighter-weight alternatives to predictive coding

### 7. Add Architecture Stack Components (DeepSeek §5)
- Critic updater (recursive self-improvement)
- Diversity mechanism (MAP-Elites with behavioral descriptors)

### 8. Methodology Caveats (DeepSeek §4)
- Echo chamber risk in Ideator-Critic-Refiner loop
- Confidence scores as ordinal indicators, not probabilities

### 9. Updated Design Space Table
- Add columns: Improvement Ceiling, Sample Efficiency, Cost per Improvement Unit

### 10. Revise References
- Add STaR, Quiet-STaR, SPIN, Constitutional AI, DARTS, MAP-Elites references
- Add Karpathy autoresearch reference
