import torch
from pathlib import Path
import tempfile

from resksecure.policy_loader import load_policy
from resksecure.bitmask_processor import BitmaskLogitsProcessor


SAMPLE_YAML = """
version: "1.0"
policies:
  - mask: 7
    name: test_policy
    strict: false
    rules:
      - phrase: "DROP"
        mode: hard
      - phrase: "hello"
        mode: bias
        penalty: -5.0
    tools: {}
"""


class FakeTokenizer:
    vocab_size = 1000
    eos_token_id = 0

    def _tokenize(self, text: str) -> list[int]:
        return [ord(ch.lower()) % self.vocab_size for ch in text]

    def __call__(self, texts, add_special_tokens=False, return_attention_mask=False, padding=False, truncation=False):
        if isinstance(texts, str):
            texts = [texts]
        input_ids = [self._tokenize(t) for t in texts]
        return {"input_ids": input_ids}

    def encode(self, text, add_special_tokens=False, **kwargs):
        return {"input_ids": [self._tokenize(text)]}

    def decode(self, ids, skip_special_tokens=True):
        return "".join(chr(i % 128) for i in ids if 32 <= (i % 128) < 127)


class FakeAC:
    """Minimal VectorizedAhoCorasick stand-in for processor tests."""

    def __init__(self, tokenizer, banned_phrases, device="cpu"):
        self.tokenizer = tokenizer
        self.device = device
        self.trie = {}
        self.failure = {}
        self.patterns = []
        self.danger_mask = torch.zeros(tokenizer.vocab_size, dtype=torch.bool)

        for phrase in banned_phrases:
            tokens = tokenizer.encode(phrase, add_special_tokens=False)["input_ids"][0]
            self.patterns.append(tokens)
            for t in tokens:
                if t < tokenizer.vocab_size:
                    self.danger_mask[t] = True

        self._build_trie()

    def _build_trie(self):
        for idx, pattern in enumerate(self.patterns):
            node = 0
            for t in pattern:
                if node not in self.trie:
                    self.trie[node] = {}
                if t not in self.trie[node]:
                    self.trie[node][t] = len(self.trie) + 1
                node = self.trie[node][t]
            if node not in self.failure:
                self.failure[node] = 0

    def step(self, state, token):
        # Follow transition if exists
        while state != 0 and token not in self.trie.get(state, {}):
            state = self.failure.get(state, 0)
        return self.trie.get(state, {}).get(token, 0)

    def has_match(self, state):
        return state in self.failure

    def get_matched_patterns(self, state):
        return [0] if state in self.failure else []


def _load_test_policy():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(SAMPLE_YAML)
        tmp = f.name
    ps = load_policy(tmp)
    Path(tmp).unlink()
    return ps


def test_processor_init():
    ps = _load_test_policy()
    processor = BitmaskLogitsProcessor(
        mask=7,
        model_name="test_model",
        tokenizer=FakeTokenizer(),
        policy_set=ps,
        device="cpu",
    )
    assert processor.mask == 7
    assert processor.model_name == "test_model"
    assert processor.policy is not None
    assert processor.strict is False


def test_processor_unknown_mask():
    ps = _load_test_policy()
    processor = BitmaskLogitsProcessor(
        mask=99,
        model_name="test_model",
        tokenizer=FakeTokenizer(),
        policy_set=ps,
        device="cpu",
    )
    assert processor.policy is None
    assert processor.hard_ac is None
    assert processor.bias_ac is None


def test_processor_reset():
    ps = _load_test_policy()
    processor = BitmaskLogitsProcessor(
        mask=7,
        model_name="test_model",
        tokenizer=FakeTokenizer(),
        policy_set=ps,
        device="cpu",
    )
    processor._hard_state = 42
    processor._bias_state = 42
    processor.reset()
    assert processor._hard_state == 0
    assert processor._bias_state == 0
