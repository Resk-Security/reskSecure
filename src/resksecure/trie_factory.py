from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from resklogits import VectorizedAhoCorasick

from .cache import trie_cache
from .policy_loader import Policy, PolicySet


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
        s = rule.phrase.strip()
        variants = [s]
        if not s.startswith(" "):
            variants.append(" " + s)
        capitalized = s.capitalize()
        if capitalized != s:
            variants.append(capitalized)

        for variant in variants:
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
    if policy is None or not policy.rules:
        result = (None, None, {}, {}, policy)
        trie_cache.set(key, result)
        return result

    hard_phrases = [r.phrase for r in policy.rules if r.mode == "hard"]
    bias_phrases = [r.phrase for r in policy.rules if r.mode == "bias"]

    hard_ac, bias_ac = None, None
    hard_meta, bias_meta = {}, {}

    if hard_phrases:
        hard_ac, hard_meta, _ = build_ac_from_policy(
            Policy(mask=policy.mask, rules=[r for r in policy.rules if r.mode == "hard"]),
            tokenizer,
            device,
        )

    if bias_phrases:
        bias_ac, bias_meta, _ = build_ac_from_policy(
            Policy(mask=policy.mask, rules=[r for r in policy.rules if r.mode == "bias"]),
            tokenizer,
            device,
        )

    result = (hard_ac, bias_ac, hard_meta, bias_meta, policy)
    trie_cache.set(key, result)
    return result
