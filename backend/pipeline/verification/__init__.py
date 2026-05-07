"""Verification subsystem for proposal quality assurance."""
from backend.pipeline.verification.reference_verifier import ReferenceVerifier, VerificationReport
from backend.pipeline.verification.proposal_deepener import ProposalDeepener, DeepenedProposal
from backend.pipeline.verification.pipeline_evaluator import PipelineEvaluator, PipelineEvaluationReport

__all__ = [
    "ReferenceVerifier", "VerificationReport",
    "ProposalDeepener", "DeepenedProposal",
    "PipelineEvaluator", "PipelineEvaluationReport",
]
