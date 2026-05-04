# Research Proposal Generation Patterns: Reference Repo Analysis

Analysis of 6 reference repos for patterns to fix "Synthesis failed" stubs in proposal pipelines.

---

## 1. MULTI-SECTION GENERATION: Ensuring ALL Sections Are Fully Written

### Pattern A: Section-by-Section Sequential Generation (AI-Scientist v1)

**File:** `C:\Next AI\ref\AI-Scientist-main\ai_scientist\perform_writeup.py`

The most battle-tested pattern. Each section is generated independently, with its own prompt + refinement pass:

```python
def perform_writeup(idea, folder_name, coder, cite_client, cite_model, ...):
    # Step 1: Title + Abstract
    coder_out = coder.run(abstract_prompt)
    coder_out = coder.run(refinement_prompt.format(section="Abstract"))

    # Step 2: Core sections one-by-one
    for section in ["Introduction", "Background", "Method",
                     "Experimental Setup", "Results", "Conclusion"]:
        coder_out = coder.run(section_prompt)
        coder_out = coder.run(refinement_prompt.format(section=section))

    # Step 3: Related Work (separate because it needs citation search)
    coder_out = coder.run(section_prompt)  # sketch first
    for _ in range(num_cite_rounds):       # then add citations
        ...
    coder_out = coder.run(refinement_prompt.format(section="Related Work"))

    # Step 4: SECOND REFINEMENT LOOP over ALL sections
    for section in ["Abstract", "Related Work", "Introduction",
                     "Background", "Method", "Experimental Setup",
                     "Results", "Conclusion"]:
        coder_out = coder.run(second_refinement_prompt.format(section=section, ...))
```

**Key insights:**
- Each section gets TWO passes: initial generation + refinement
- A complete second pass refines everything in context of the full paper
- The refinement prompt explicitly says: **"Make this complete in this pass, do not leave any placeholders"**
- Section-specific tips guide each generation (see `per_section_tips` dict)

### Pattern B: Template-Based Section Composition (AI-Researcher)

**Files:**
- `C:\Next AI\ref\AI-Researcher-main\paper_agent\writing.py`
- `C:\Next AI\ref\AI-Researcher-main\paper_agent\section_composer.py`
- `C:\Next AI\ref\AI-Researcher-main\paper_agent\methodology_composing_using_template.py`

Each section follows a strict 4-step pipeline within an abstract class:

```python
class SectionComposer(ABC):
    async def compose_section(self, ...) -> str:
        # Step 1: Iterative structure generation (N iterations)
        structure = ""
        for iteration in range(self.structure_iterations):
            structure = await self.generate_or_revise_structure(
                content, structure, iteration + 1)

        # Step 2: Detailize subsections (per-subsection generation)
        subsections = [line.split('{')[1].split('}')[0]
                    for line in structure.split('\n')
                    if line.strip().startswith('\\subsection')]

        subsection_contents = {}
        for subsection in subsections:
            text = ''
            text = await self.detailize_subsection(structure, text, content, subsection)
            # Also process agent files one-by-one for additional content
            for agent_file in agent_files:
                text = await self.detailize_subsection(structure, text, agent_content, subsection)
            subsection_contents[subsection] = text

        # Step 3: Fuse all subsections
        fused = await self.fuse_subsections(structure, subsection_contents)

        # Step 4: Final writing checklist (validation pass)
        final = await self.final_writing_checklist(fused)

        # Save to file
        with open(output_path, 'w') as f:
            f.write(final)
```

**Writing orchestration (writing.py):**
```python
async def writing(research_field, instance_id):
    await methodology_composing(research_field, instance_id)
    await related_work_composing(research_field, instance_id)
    await experiments_composing(research_field, instance_id)
    await introduction_composing(research_field, instance_id)
    await conclusion_composing(research_field, instance_id)
    await abstract_composing(research_field, instance_id)  # LAST - uses all other sections
```

**Key insight:** Abstract is generated LAST, after all other sections exist, so it can read them as input content.

### Pattern C: Whole-Paper Generation + Reflection (AI-Scientist v2)

**File:** `C:\Next AI\ref\AI-Scientist-v2-main\ai_scientist\perform_writeup.py`

Instead of section-by-section, v2 generates the ENTIRE paper in one shot, then iteratively reflects:

```python
def perform_writeup(base_folder, ..., n_writeup_reflections=3, page_limit=8):
    # Step 1: One-shot full paper generation
    combined_prompt = writeup_prompt.format(
        idea_text=idea_text,
        summaries=combined_summaries_str,
        aggregator_code=aggregator_code,
        plot_list=", ".join(plot_names),
        latex_writeup=writeup_text,         # current template
        plot_descriptions=plot_descriptions_str,
    )
    response, msg_history = get_response_from_llm(
        msg=combined_prompt, client=big_client, model=big_client_model,
        system_message=writeup_system_message_template.format(page_limit=page_limit),
    )

    # Extract LaTeX from response
    latex_code_match = re.search(r"```latex(.*?)```", response, re.DOTALL)
    if not latex_code_match:
        return False  # HARD FAIL - no valid output
    updated_latex_code = latex_code_match.group(1).strip()
    with open(writeup_file, "w") as f:
        f.write(updated_latex_code)

    # Step 2: N reflection loops
    for i in range(n_writeup_reflections):
        # Compile, check figures, check page limit
        compile_latex(latex_folder, ...)
        check_output = os.popen(f"chktex {writeup_file} -q -n2 -n24 -n13 -n1").read()

        reflection_prompt = f"""...check for issues...
Return the entire file in full, with no unfilled placeholders!
This must be an acceptable complete LaTeX writeup.
If you believe you are done, simply say: "I am done"."""

        reflection_response, msg_history = get_response_from_llm(
            msg=reflection_prompt, msg_history=msg_history, ...
        )

        if "I am done" in reflection_response:
            break

        # Extract updated LaTeX, with cleanup
        reflection_code_match = re.search(r"```latex(.*?)```", reflection_response, re.DOTALL)
        if reflection_code_match:
            reflected_latex_code = reflection_code_match.group(1).strip()
            # Post-processing cleanup
            cleanup_map = {"</end": r"\\end", "</begin": r"\\begin", "'": "'"}
            for bad_str, repl_str in cleanup_map.items():
                final_text = final_text.replace(bad_str, repl_str)
            final_text = re.sub(r"(\d+(?:\.\d+)?)%", r"\1\\%", final_text)
```

**Key insight:** Uses `msg_history` to maintain conversation context across reflections — the LLM sees its previous output and iteratively improves it.

---

## 2. FAILURE HANDLING: Retry, Fallback, and Graceful Degradation

### Pattern A: Exponential Backoff on Rate Limits (AI-Scientist v1 & v2)

**File:** `C:\Next AI\ref\AI-Scientist-main\ai_scientist\llm.py`

```python
@backoff.on_exception(backoff.expo, (openai.RateLimitError, openai.APITimeoutError))
def get_response_from_llm(msg, client, model, system_message, ...):
    ...
```

v2 extends this with more exception types:

**File:** `C:\Next AI\ref\AI-Scientist-v2-main\ai_scientist\llm.py`

```python
@backoff.on_exception(
    backoff.expo,
    (openai.RateLimitError, openai.APITimeoutError,
     openai.InternalServerError, anthropic.RateLimitError),
)
def get_response_from_llm(prompt, client, model, ...):
```

### Pattern B: Predicate-Based Backoff with Retry (AI-Scientist-v2 backend)

**File:** `C:\Next AI\ref\AI-Scientist-v2-main\ai_scientist\treesearch\backend\utils.py`

```python
@backoff.on_predicate(wait_gen=backoff.expo, max_value=60, factor=1.5)
def backoff_create(create_fn, retry_exceptions, *args, **kwargs):
    try:
        return create_fn(*args, **kwargs)
    except retry_exceptions as e:
        logger.info(f"Backoff exception: {e}")
        return False  # Returning False triggers the predicate retry
```

### Pattern C: Manual Retry with Sleep (AI-Researcher GPTClient)

**File:** `C:\Next AI\ref\AI-Researcher-main\benchmark_collection\utils\openai_utils.py`

```python
class GPTClient:
    @backoff.on_exception(
        backoff.expo,
        (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError),
        base=2, factor=3, max_tries=5
    )
    async def _get_response(self, messages, temperature, max_tokens):
        try:
            completion = await self.client.chat.completions.create(
                model=self.model, messages=messages,
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"Error in API call: {str(e)}")
            raise

    async def chat(self, prompt, ...):
        for attempt in range(3):  # 3 manual retries
            try:
                return await self._get_response(messages, temperature, max_tokens)
            except (openai.APIConnectionError, openai.APITimeoutError) as e:
                if attempt == 2:
                    print(f"Final attempt failed: {str(e)}")
                    return None  # Graceful: returns None, doesn't crash
                await asyncio.sleep(5 * (attempt + 1))
            except Exception as e:
                print(f"Unexpected error: {str(e)}")
                return None
```

### Pattern D: Try-Except with Continue (Citation Loops)

**File:** `C:\Next AI\ref\AI-Scientist-v2-main\ai_scientist\perform_writeup.py`

```python
for round_idx in range(num_cite_rounds):
    try:
        # ... citation logic ...
    except Exception:
        print("EXCEPTION in perform_writeup (citation round):")
        print(traceback.format_exc())
        continue  # Skip failed round, continue to next
```

### Pattern E: DSPy Refine — Reward-Based Retry with Feedback

**File:** `C:\Next AI\ref\dspy-main\dspy\predict\refine.py`

```python
class Refine(Module):
    def forward(self, **kwargs):
        best_pred, best_reward = None, -float("inf")
        advice = None

        for idx, rid in enumerate(rollout_ids):
            try:
                if not advice:
                    outputs = mod(**kwargs)
                else:
                    # Inject advice from previous failed attempt into next try
                    inputs["hint_"] = advice.get(signature_name, "N/A")
                
                reward = self.reward_fn(kwargs, outputs)
                
                if reward > best_reward:
                    best_reward, best_pred = reward, outputs
                
                if reward >= self.threshold:
                    break  # Good enough, stop

                # Generate feedback for next attempt
                advice = dspy.Predict(OfferFeedback)(...).advice

            except Exception as e:
                print(f"Refine: Attempt failed with rollout id {rid}: {e}")
                if idx > self.fail_count:
                    raise e
                self.fail_count -= 1

        return best_pred  # Always returns best found, even if not perfect
```

**Key pattern:** On failure, generates specific advice about *what went wrong* and feeds it back to the next attempt.

---

## 3. VALIDATION: Ensuring Completeness Before Accepting

### Pattern A: LaTeX Compilation as Validation (All AI-Scientist variants)

**File:** `C:\Next AI\ref\AI-Scientist-main\ai_scientist\perform_writeup.py`

```python
def generate_latex(coder, folder_name, pdf_file, timeout=30, num_error_corrections=5):
    # Check references exist
    cites = re.findall(r"\\cite[a-z]*{([^}]*)}", tex_text)
    for cite in cites:
        if cite not in bib_text:
            coder.run(f"Reference {cite} not found...")  # Auto-fix

    # Check figures exist
    referenced_figs = re.findall(r"\\includegraphics.*?{(.*?)}", tex_text)
    for figure in referenced_figs:
        if figure not in all_figs:
            coder.run(f"Image {figure} not found...")  # Auto-fix

    # Remove duplicates (figures, section headers)
    # ...

    # Iteratively fix LaTeX bugs (up to num_error_corrections)
    for i in range(num_error_corrections):
        check_output = os.popen(f"chktex {writeup_file} -q -n2 -n24 -n13 -n1").read()
        if check_output:
            coder.run(f"Please fix the following LaTeX errors...")
        else:
            break  # All clean
```

### Pattern B: Reflection Loop with "I am done" Sentinel (v2 & ICBINB)

```python
for i in range(n_writeup_reflections):
    reflection_prompt = """...
Return the entire file in full, with no unfilled placeholders!
If you believe you are done, simply say: "I am done"."""

    reflection_response, msg_history = get_response_from_llm(...)
    
    if "I am done" in reflection_response:
        break
```

### Pattern C: Post-Processing Cleanup of Common LLM Artifacts (v2 & ICBINB)

```python
# Fix common LLM LaTeX mistakes
cleanup_map = {
    "</end": r"\\end",       # HTML-style closing
    "</begin": r"\\begin",   # HTML-style closing
    "'": "'",               # Smart quotes
}
for bad_str, repl_str in cleanup_map.items():
    final_text = final_text.replace(bad_str, repl_str)

# Escape bare percentages
final_text = re.sub(r"(\d+(?:\.\d+)?)%", r"\1\\%", final_text)
```

### Pattern D: LaTeX Backtick Cleanup (AI-Researcher)

**File:** `C:\Next AI\ref\AI-Researcher-main\paper_agent\writing_fix.py`

```python
def clean_tex_file(filepath):
    """Remove ``` markers that LLMs often wrap around LaTeX output"""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    while lines and '```' in lines[0]:
        lines.pop(0)    # Remove leading ```
    while lines and '```' in lines[-1]:
        lines.pop(-1)   # Remove trailing ```
    
    with open(filepath, 'w') as f:
        f.writelines(lines)
```

### Pattern E: Checkpoint-Based Resumability (AI-Researcher + ICBINB)

```python
class SectionComposer:
    def save_checkpoint(self, target_paper, step, data):
        checkpoint_file = os.path.join(checkpoint_dir, f"{step}.json")
        with open(checkpoint_file, 'w') as f:
            json.dump(data, f, indent=2)

    def load_checkpoint(self, target_paper, step):
        if os.path.exists(checkpoint_file):
            with open(checkpoint_file, 'r') as f:
                return json.load(f)
        return None

    async def compose_section(self, ...):
        structure_checkpoint = self.load_checkpoint(target_paper, "structure")
        if structure_checkpoint:
            structure = structure_checkpoint["final_structure"]  # Resume from checkpoint
        else:
            # Generate from scratch
```

---

## 4. MAX_TOKENS HANDLING: Avoiding Truncation

### Pattern A: Section-by-Section Generation (Primary Strategy)

All repos that generate long documents use section-by-section to avoid max_tokens limits. No repo attempts to generate a 10+ page document in a single LLM call with max_tokens control.

**AI-Scientist v1** generates each section as a separate `coder.run()` call.
**AI-Researcher** generates each subsection independently, then fuses.

### Pattern B: Dynamic Token Budget Calculation (autoresearcher)

**File:** `C:\Next AI\ref\autoresearcher-main\autoresearcher\workflows\literature_review\combine_answers.py`

```python
from autoresearcher.utils.count_tokens import count_tokens

def combine_answers(answers, research_question, ...):
    answer_list = "\n\n".join(answers)
    prompt = literature_review_prompt.format(...)
    
    input_tokens = count_tokens(prompt)
    remaining_tokens = 4080 - input_tokens  # Fixed model limit minus input
    max_tokens = max(remaining_tokens, 0)    # Never negative
    
    literature_review = openai_call(
        prompt, max_tokens=max_tokens
    )
```

### Pattern C: Fixed MAX_NUM_TOKENS with Backoff (AI-Scientist)

**File:** `C:\Next AI\ref\AI-Scientist-main\ai_scientist\llm.py`

```python
MAX_NUM_TOKENS = 4096

@backoff.on_exception(backoff.expo, ...)
def get_response_from_llm(msg, client, model, ...):
    response = client.chat.completions.create(
        model=model,
        messages=[...],
        max_tokens=MAX_NUM_TOKENS,  # Fixed limit
    )
```

### Pattern D: Default max_tokens in Backend (AI-Scientist-v2)

**File:** `C:\Next AI\ref\AI-Scientist-v2-main\ai_scientist\treesearch\backend\backend_anthropic.py`

```python
def query(system_message, user_message, **model_kwargs):
    filtered_kwargs = select_values(notnone, model_kwargs)
    if "max_tokens" not in filtered_kwargs:
        filtered_kwargs["max_tokens"] = 8192  # Sensible default
```

---

## 5. PROMPT ENGINEERING PATTERNS for Research Proposals

### Pattern A: Per-Section Tips Dictionary (AI-Scientist v1)

```python
per_section_tips = {
    "Abstract": """
- TL;DR of the paper
- What are we trying to do and why is it relevant?
- Why is this hard?
- How do we solve it (i.e. our contribution!)
- How do we verify that we solved it (e.g. Experiments and results)
Please make sure the abstract reads smoothly and is well-motivated.
This should be one continuous paragraph with no breaks between the lines.
""",
    "Introduction": """
- Longer version of the Abstract, i.e. of the entire paper
- ...
- New trend: specifically list your contributions as bullet points
- Extra space? Future work!
""",
    "Method": """
- What we do. Why we do it. All described using the general Formalism
  introduced in the Problem Setting and building on top of the concepts /
  foundations introduced in Background.
""",
    # ... etc for each section
}
```

### Pattern B: Error Checklist in Refinement Prompts (AI-Scientist v1)

```python
error_list = """
- Unenclosed math symbols
- Only reference figures that exist in our directory
- LaTeX syntax errors
- Numerical results that do not come from explicit experiments and logs
- Repeatedly defined figure labels
- References to papers that are not in the .bib file
- Unnecessary verbosity or repetition, unclear text
- Results or insights in notes.txt that have not yet been included
- Any relevant figures that have not yet been included in the text
- Closing any \\begin{figure} with \\end{figure}
- Duplicate headers
- Unescaped symbols
- Incorrect closing of environments
"""

refinement_prompt = """Make this complete in this pass, do not leave any placeholders.
Pay particular attention to fixing any errors such as:
""" + error_list
```

### Pattern C: System Message with Detailed Section Guidelines (AI-Scientist v2)

```python
writeup_system_message_template = """You are an ambitious AI researcher...
Ensure that the paper is scientifically accurate, objective, and truthful.

Here are some tips for each section of the paper:

- **Title**: catchy and informative, under 2 lines
- **Abstract**: TL;DR, one continuous paragraph
- **Introduction**: Longer version of Abstract, summarize contributions
- **Related Work**: Compare and contrast
- **Background**: Present foundational concepts
- **Method**: Clearly detail what you propose and why
- **Experimental Setup**: Explain how you tested
- **Experiments**: Present results truthfully
- **Conclusion**: Summarize, highlight strengths/findings, future directions
- **Appendix**: Supplementary material

Ensure you are always writing good compilable LaTeX code. Common mistakes:
- LaTeX syntax errors
- Duplicate figure labels or references
- Unescaped special characters: & % $ # _ {{ }} ~ ^ \\
- Proper table/figure closure
- Do not hallucinate new citations or any results not in the logs.
"""
```

### Pattern D: Writing Checklist for Final Validation (AI-Researcher)

**File:** `C:\Next AI\ref\AI-Researcher-main\paper_agent\methodology_composing_using_template.py`

```python
async def final_writing_checklist(self, methodology_text):
    prompt = f"""Review and revise the methodology section:

CHECKLIST FOR REVISION:

1. ACADEMIC WRITING STYLE:
   - Remove any markdown-style formatting
   - Use formal academic language

2. MATHEMATICAL FORMULATION:
   - Verify correctness of all equations
   - Ensure consistent variable naming

3. ACADEMIC WRITING WITH MATH:
   - Ensure important modules are described with math equations
   - Avoid too simple math in non-inline equations

4. CONTENT FOCUS:
   - Reduce explanations of commonly known concepts
   - Concentrate on novel contributions

5. SECTION TITLES:
   - Replace generic titles with context-specific ones
   - e.g. "Embedding Layer" → "Context-Aware Knowledge Graph Embedding"

Output the revised section. Reply your latex without any additional explanations."""
```

### Pattern E: Structure → Subsection → Fuse → Validate Pipeline (AI-Researcher)

```python
# Step 1: Generate STRUCTURE first (outline with comments)
# Step 2: For each subsection in structure, generate DETAILED content
# Step 3: FUSE subsections together preserving content exactly
# Step 4: Run final_writing_checklist for quality validation

# The fuse prompt explicitly says:
"""Combine the following subsections into a complete section.
The content of each subsection MUST BE PRESERVED EXACTLY as provided.
STRICT CONTENT PRESERVATION:
- Keep ALL content within each subsection exactly as provided
- Maintain all LaTeX commands, equations, and formatting
- Preserve all citations and references"""
```

---

## SUMMARY: What Your Pipeline Needs

Based on these patterns, to fix "Synthesis failed" stubs:

| Problem | Solution | Source Pattern |
|---------|----------|---------------|
| Truncated sections due to max_tokens | **Generate section-by-section, not whole-document** | AI-Scientist v1, AI-Researcher |
| Missing sections | **Define required sections upfront, iterate over them** | AI-Scientist v1 (for loop over section names) |
| Incomplete content | **Refinement pass per section: "do not leave any placeholders"** | AI-Scientist v1/v2 refinement prompts |
| LLM API failures | **`@backoff.on_exception(backoff.expo, ...)`** | All repos |
| No fallback on failure | **Try/except + continue + checkpoint resumption** | AI-Researcher, ICBINB |
| LLM returns wrapped code | **Strip ``` markers in post-processing** | AI-Researcher writing_fix.py |
| LLM outputs HTML-style LaTeX | **Post-processing cleanup map** | AI-Scientist v2 |
| Can't tell if output is good | **Validation prompt: "I am done" sentinel** | AI-Scientist v2 |
| Structure→content gap | **Generate outline first, then fill in subsection-by-subsection** | AI-Researcher |
| Abstract/Conclusion too vague | **Generate AFTER all other sections, using them as input** | AI-Researcher writing.py |
| Token budget unknown | **Count input tokens, set max_tokens = limit - input** | autoresearcher |
