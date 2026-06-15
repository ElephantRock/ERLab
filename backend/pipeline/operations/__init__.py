"""Operation Executor — authoritative boundary for all model-backed work.

No component outside this package may load, unload, swap, or reconcile
LM Studio models. Stages request operations through the executor and
receive typed results with verifiable receipts.
"""
