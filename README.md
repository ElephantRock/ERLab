# Elephant Rock Research

AI/NLP Research Idea Generation Platform.

## Quick Start

```bash
cp .env.example .env   # Add your API keys
pip install -e ".[dev]"

# Search literature
erock search "chain-of-thought reasoning"

# Run full pipeline
erock generate --domain "AI/NLP" --rounds 2 --ideas 3

# Check novelty of an idea
erock novelty-check "Apply diffusion models to automated theorem proving"
```

## Architecture

9-stage pipeline: Literature Discovery → PDF Ingestion → Knowledge Base → Gap Analysis → Idea Generation (multi-agent) → Novelty Check → Feasibility Score → Proposal Synthesis → Export

See [CLAUDE.md](CLAUDE.md) for development guidelines.
