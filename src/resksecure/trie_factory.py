from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from resklogits import VectorizedAhoCorasick

from .cache import trie_cache
from .policy_loader import Policy, PolicySet, PhraseRule


def _expand_phrases(phrases: List[str]) -> List[str]:
    """Generate variants of each phrase (space-prefixed, capitalized)."""
    expanded: List[str] = []
    for s in phrases:
        s = s.strip()
        expanded.append(s)
        if not s.startswith(" "):
            expanded.append(" " + s)
        capitalized = s.capitalize()
        if capitalized != s:
            expanded.append(capitalized)
    return expanded


def build_ac_from_policy(
    policy: Policy,
    tokenizer,
    device: str = "cuda",
) -> Tuple[Optional[VectorizedAhoCorasick], Dict[int, str], Dict[int, float]]:
    """Build a VectorizedAhoCorasick from a Policy.

    Generates phrase variants (with space prefix, capitalized) to cover
    different tokenization contexts.

    Returns:
        (automaton, pattern_modes, pattern_penalties)
        - automaton: VectorizedAhoCorasick or None if no rules
        - pattern_modes: pattern_index -> 'hard' | 'bias'
        - pattern_penalties: pattern_index -> penalty value
    """
    if not policy.rules:
        return None, {}, {}

    all_phrases: List[str] = []
    pattern_meta: List[Tuple[str, float]] = []

    for rule in policy.rules:
        for variant in _expand_phrases([rule.phrase]):
            all_phrases.append(variant)
            pattern_meta.append((rule.mode, rule.penalty))

    if not all_phrases:
        return None, {}, {}

    ac = VectorizedAhoCorasick(
        tokenizer=tokenizer,
        banned_phrases=all_phrases,
        device=device,
    )

    pattern_modes = {i: meta[0] for i, meta in enumerate(pattern_meta)}
    pattern_penalties = {i: meta[1] for i, meta in enumerate(pattern_meta)}

    return ac, pattern_modes, pattern_penalties


def get_or_build_ac(
    mask: int,
    model_name: str,
    tokenizer,
    policy_set: PolicySet,
    device: str = "cuda",
):
    """Get cached automaton or build it from the policy.

    Also derives tool trigger phrases that should be blocked for this mask.
    If the user's mask does not have the required bit for a tool, that
    tool's trigger phrases are added as hard-mode blocked phrases.

    Returns:
        (hard_ac, bias_ac, hard_meta, bias_meta, policy)
        - hard_ac: VectorizedAhoCorasick or None for hard-mode phrases
        - bias_ac: VectorizedAhoCorasick or None for bias-mode phrases
        - hard_meta: dict pattern_index -> mode
        - bias_meta: dict pattern_index -> penalty
        - policy: the resolved Policy or None
    """
    key = (mask, model_name)
    cached = trie_cache.get(key)
    if cached is not None:
        return cached

    policy = policy_set.get_policy_for_mask(mask)
    if policy is None:
        return (None, None, {}, {}, policy)

    # Collect explicit rules from the policy
    hard_phrases = [r.phrase for r in policy.rules if r.mode == "hard"]
    bias_phrases = [r.phrase for r in policy.rules if r.mode == "bias"]

    # Derive tool trigger phrases for tools the user does NOT have access to.
    # These are added as hard-mode phrases so the model can never generate
    # a disallowed tool call at the token level.
    if policy.tools:
        for tool_name, tool_rule in policy.tools.items():
            has_bit = (mask & (1 << tool_rule.required_bit)) != 0
            if not has_bit and tool_rule.trigger_phrases:
                hard_phrases.extend(tool_rule.trigger_phrases)

    hard_ac, bias_ac = None, None
    hard_meta, bias_meta = {}, {}

    if hard_phrases:
        hard_rules = [PhraseRule(phrase=p, mode="hard") for p in hard_phrases]
        hard_ac, hard_meta, _ = build_ac_from_policy(
            Policy(mask=policy.mask, rules=hard_rules),
            tokenizer,
            device,
        )

    if bias_phrases:
        bias_rules = [PhraseRule(phrase=p, mode="bias", penalty=-5.0) for p in bias_phrases]
        bias_ac, bias_meta, _ = build_ac_from_policy(
            Policy(mask=policy.mask, rules=bias_rules),
            tokenizer,
            device,
        )

    result = (hard_ac, bias_ac, hard_meta, bias_meta, policy)
    trie_cache.set(key, result)
    return result
