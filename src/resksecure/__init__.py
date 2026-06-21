"""
reskSecure - Bitmask-based LLM security firewall.

A policy-driven LogitsProcessor that restricts LLM output based on
capability bitmasks. Uses resklogits (VectorizedAhoCorasick) for
GPU-accelerated pattern matching.

Usage::

    from resksecure import (
        BitmaskLogitsProcessor,
        PolicySet,
        load_policy,
        verify_tool_action,
    )

    policy_set = load_policy("config/policy.yaml")
    processor = BitmaskLogitsProcessor(
        mask=7,
        model_name="mistralai/Mistral-7B-v0.1",
        tokenizer=tokenizer,
        policy_set=policy_set,
        device="cuda",
    )
    outputs = model.generate(**inputs, logits_processor=[processor])
"""

from .bitmask_processor import BitmaskLogitsProcessor
from .cache import TrieCache, trie_cache
from .policy_loader import (
    PhraseRule,
    Policy,
    PolicySet,
    ToolRule,
    load_policy,
)
from .policy_watcher import PolicyWatcher
from .tool_guard import get_allowed_tools, verify_tool_action
from .trie_factory import build_ac_from_policy, get_or_build_ac

__version__ = "0.1.0"

__all__ = [
    "BitmaskLogitsProcessor",
    "TrieCache",
    "trie_cache",
    "PhraseRule",
    "Policy",
    "PolicySet",
    "ToolRule",
    "load_policy",
    "PolicyWatcher",
    "get_allowed_tools",
    "verify_tool_action",
    "build_ac_from_policy",
    "get_or_build_ac",
]
