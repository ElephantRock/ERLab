"""Persistent agent memory system.

Provides typed storage (semantic, episodic, procedural), quality-gated
extraction, mem0-style consolidation, and OpenNARS temporal decay.
Uses content-addressable JSONL with SHA-256 IDs (Ajnan pattern).
"""
