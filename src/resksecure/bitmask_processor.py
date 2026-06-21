from __future__ import annotations
from typing import Dict, Optional

import torch
from resklogits import VectorizedAhoCorasick
from transformers import LogitsProcessor

from .policy_loader import Policy, PolicySet
from .trie_factory import get_or_build_ac


class BitmaskLogitsProcessor(LogitsProcessor):
    """LogitsProcessor that applies bitmask-based policy filtering.

    Uses VectorizedAhoCorasick from resklogits to detect and block
    or penalize banned phrases during token generation.

    Two severity modes:
    - ``hard``: banned phrase tokens get logit = -inf (impossible to generate)
    - ``bias``:  banned phrase tokens get logit -= penalty (unlikely but not impossible)

    Strict mode: forces EOS as soon as a banned pattern prefix is detected.

    Usage::

        processor = BitmaskLogitsProcessor(
            mask=7,
            model_name="mistralai/Mistral-7B-v0.1",
            tokenizer=tokenizer,
            policy_set=policy_set,
            device="cuda",
        )
        outputs = model.generate(**inputs, logits_processor=[processor])
    """

    def __init__(
        self,
        mask: int,
        model_name: str,
        tokenizer,
        policy_set: PolicySet,
        device: str = "cuda",
    ):
        super().__init__()
        self.mask = mask
        self.model_name = model_name
        self.tokenizer = tokenizer
        self.device = device
        self.strict: bool = False

        hard_ac, bias_ac, hard_meta, bias_meta, policy = get_or_build_ac(
            mask, model_name, tokenizer, policy_set, device,
        )

        self.hard_ac: Optional[VectorizedAhoCorasick] = hard_ac
        self.hard_modes: Dict[int, str] = hard_meta
        self.bias_ac: Optional[VectorizedAhoCorasick] = bias_ac
        self.bias_penalties: Dict[int, float] = {
            pid: penalty for pid, penalty in bias_meta.items()
        }
        self.policy: Optional[Policy] = policy
        self.strict = policy.strict if policy else False

        self._hard_state: int = 0
        self._bias_state: int = 0

    def __call__(
        self,
        input_ids: torch.LongTensor,
        scores: torch.FloatTensor,
    ) -> torch.FloatTensor:
        if input_ids.shape[0] != 1:
            raise NotImplementedError("Batch size > 1 not supported")

        if input_ids.shape[1] > 0:
            last_token = int(input_ids[0, -1].item())
            if self.hard_ac is not None:
                self._hard_state = self.hard_ac.step(self._hard_state, last_token)
            if self.bias_ac is not None:
                self._bias_state = self.bias_ac.step(self._bias_state, last_token)

        # Hard mode: effectively ban dangerous tokens (-1e9 ≈ -inf in fp32)
        if self.hard_ac is not None and self.hard_ac.danger_mask.any():
            scores[0, self.hard_ac.danger_mask] = torch.where(
                scores[0, self.hard_ac.danger_mask] > -1e9,
                torch.tensor(-1e9, device=scores.device),
                scores[0, self.hard_ac.danger_mask],
            )

        # Bias mode: apply configured penalty to dangerous tokens
        if self.bias_ac is not None and self.bias_ac.danger_mask.any():
            penalty = self._get_bias_penalty()
            if penalty != 0.0:
                scores[0, self.bias_ac.danger_mask] += penalty

        # Hard mode complete match: force EOS immediately
        if self.hard_ac is not None and self.hard_ac.has_match(self._hard_state):
            scores[0, :] = -float("inf")
            eos_id = self.tokenizer.eos_token_id
            if eos_id is not None:
                scores[0, eos_id] = 0.0
            return scores

        # Strict mode: force EOS when on a path that leads to a hard match
        if self.strict and self.hard_ac is not None:
            if self._is_on_path_to_hard_match():
                scores[0, :] = -float("inf")
                eos_id = self.tokenizer.eos_token_id
                if eos_id is not None:
                    scores[0, eos_id] = 0.0

        return scores

    def _get_bias_penalty(self) -> float:
        """Get the bias penalty for currently matched patterns."""
        if self.bias_ac is None:
            return 0.0
        if not self.bias_ac.has_match(self._bias_state):
            return 0.0
        matched = self.bias_ac.get_matched_patterns(self._bias_state)
        penalty = 0.0
        for pid in matched:
            p = self.bias_penalties.get(pid, 0.0)
            if p < penalty:
                penalty = p
        return penalty

    def _is_on_path_to_hard_match(self) -> bool:
        """Check if current AC state could reach a match in one step."""
        if self.hard_ac is None:
            return False
        state = self._hard_state
        if state == 0:
            return False
        for token, _child_state in self.hard_ac.trie.get(state, {}).items():
            next_state = self.hard_ac.step(state, token)
            if self.hard_ac.has_match(next_state):
                return True
        current = state
        visited = set()
        while current in self.hard_ac.failure and current not in visited:
            visited.add(current)
            current = self.hard_ac.failure[current]
            for token, _child_state in self.hard_ac.trie.get(current, {}).items():
                next_state = self.hard_ac.step(current, token)
                if self.hard_ac.has_match(next_state):
                    return True
        return False

    def reset(self) -> None:
        self._hard_state = 0
        self._bias_state = 0
