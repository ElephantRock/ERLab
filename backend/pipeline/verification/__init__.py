"""Verification subsystem for proposal quality assurance."""
from backend.pipeline.verification.pipeline_evaluator import (
    PipelineEvaluationReport,
    PipelineEvaluator,
)
from backend.pipeline.verification.proposal_deepener import DeepenedProposal, ProposalDeepener
from backend.pipeline.verification.reference_verifier import ReferenceVerifier, VerificationReport

__all__ = [
    "ReferenceVerifier", "VerificationReport",
    "ProposalDeepener", "DeepenedProposal",
    "PipelineEvaluator", "PipelineEvaluationReport",
]
