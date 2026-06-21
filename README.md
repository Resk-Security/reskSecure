# reskSecure

[![PyPI version](https://img.shields.io/pypi/v/resksecure)](https://pypi.org/project/resksecure/)
[![PyPI downloads](https://img.shields.io/pypi/dm/resksecure)](https://pypi.org/project/resksecure/)
[![Python versions](https://img.shields.io/pypi/pyversions/resksecure)](https://pypi.org/project/resksecure/)
[![License](https://img.shields.io/badge/license-RESK-blue)](LICENSE)

**Bitmask-based LLM security firewall.** A Python package that restricts what a language model can generate based on user permissions encoded as a bitmask. It works by intercepting the model's token predictions and blocking or penalizing disallowed phrases before they appear in the output.

Available on [PyPI](https://pypi.org/project/resksecure/).

Unlike prompt-based filters (which can be jailbroken) or post-generation content moderation (which lets forbidden content leak before detection), reskSecure acts at the logits level -- directly inside the model's generation loop. Each token must pass through the security policy before being emitted.

---

## How it works

```
User request with bitmask (e.g. 7)
    |
    v
BitmaskLogitsProcessor intercepts each token prediction
    |
    v
For every candidate token, the Aho-Corasick automaton (from resklogits)
checks if selecting it would start or complete a banned phrase
    |
    v
Hard-mode phrases: the token's logit is set to -inf (impossible to generate)
Bias-mode phrases: the token's logit is reduced by a configurable penalty
    |
    v
On complete match: EOS token is forced, generation stops immediately
    |
    v
Output response or tool call
```

Tool calls are also blocked at the token level. If the user's bitmask does not
contain the required bit for a tool, that tool's trigger phrases (like
`"send_email("` or `"create_ticket("`) are automatically added to the
hard-mode blocked list. The model can never generate the first token of
a disallowed tool call, regardless of prompt engineering or jailbreak
attempts.

A post-generation check (`verify_tool_action`) is also available as a
defense-in-depth layer, but the primary protection is at the logits level.

---

## Why not just prompt engineering?

- Prompt injections can bypass instruction-based filters
- Post-generation regex or classifier scans catch violations after they appear, but the forbidden content has already been emitted
- Logits-level filtering blocks tokens before they are sampled -- the model never "sees" the banned sequence as a completion candidate

---

## Features

- **Two severity modes**: `hard` blocks tokens completely (-inf logit), `bias` reduces probability by a configurable penalty
- **Strict mode**: forces end-of-sequence as soon as the generated prefix matches the start of a banned phrase, even before the full phrase is formed
- **GPU-accelerated pattern matching**: uses VectorizedAhoCorasick from the resklogits package for fast token scanning
- **Policy system**: YAML configuration associates capability bitmasks with phrase rules and tool permissions
- **Hot-reload**: PolicyWatcher detects file changes and rebuilds the automaton without restarting the server
- **Thread-safe cache**: automata are cached by (mask, model_name) with configurable TTL
- **Tool guard**: post-generation bitmask check for tool call execution
- **No JWT handling**: the package receives a raw integer bitmask; authentication and JWT decoding are handled by the calling application

---

## Requirements

- Python >= 3.13
- PyTorch >= 2.0.0
- transformers >= 4.35.0
- resklogits >= 0.1.0

---

## Installation

```bash
pip install resksecure
```

[![PyPI version](https://img.shields.io/pypi/v/resksecure)](https://pypi.org/project/resksecure/)
[![PyPI downloads](https://img.shields.io/pypi/dm/resksecure)](https://pypi.org/project/resksecure/)

From source:

```bash
git clone https://github.com/Resk-Security/reskSecure.git
cd reskSecure
pip install -e .
```

---

## Quick start

Define a policy file (`policy.yaml`):

```yaml
version: "1.0"
policies:
  - mask: 7
    name: contributor
    strict: false
    default: true
    rules:
      - phrase: "DROP TABLE"
        mode: hard
      - phrase: "DELETE FROM"
        mode: hard
      - phrase: "salaries"
        mode: bias
        penalty: -5.0
    tools:
      read_email:
        required_bit: 0
      send_email:
        required_bit: 1
      read_sql:
        required_bit: 2
```

Use it in your generation pipeline:

```python
from resksecure import BitmaskLogitsProcessor, load_policy, verify_tool_action

policy_set = load_policy("policy.yaml")

processor = BitmaskLogitsProcessor(
    mask=7,
    model_name="mistralai/Mistral-7B-v0.1",
    tokenizer=tokenizer,
    policy_set=policy_set,
    device="cuda",
)

outputs = model.generate(**inputs, logits_processor=[processor])

# Optional: verify tool calls against the bitmask
if has_tool_call(response):
    if not verify_tool_action("send_email", user_mask=7, policy_set=policy_set):
        raise PermissionError("Action not authorized")
```

---

## Policy reference

Policy-level fields:

| Field       | Type    | Description                                              |
|-------------|---------|----------------------------------------------------------|
| `mask`      | int     | Capability bitmask that identifies this policy           |
| `name`      | string  | Human-readable policy name                               |
| `strict`    | bool    | If true, stop generation at the first banned prefix      |
| `default`   | bool    | If true, this policy is used when no exact mask matches  |
| `rules`     | list    | List of phrase rules (see below)                         |
| `tools`     | dict    | Map of tool names to tool rule objects (see below)       |

Phrase rule fields:

| Field     | Type   | Description                                                |
|-----------|--------|------------------------------------------------------------|
| `phrase`  | string | Text pattern to ban or penalize                            |
| `mode`    | string | Either `hard` (block completely) or `bias` (reduce logits) |
| `penalty` | float  | Logit penalty for bias mode (e.g. -5.0)                   |

Tool rule fields:

| Field              | Type     | Description                                                    |
|--------------------|----------|----------------------------------------------------------------|
| `required_bit`     | int      | Bit position that must be set in the user mask to use this tool |
| `trigger_phrases`  | string[] | Phrases that start this tool call (blocked if bit not set)      |

---

## Package structure

```
reskSecure/
  src/resksecure/
    __init__.py              Public exports, version
    policy_loader.py         YAML parsing, Policy/PolicySet models
    trie_factory.py          Builds VectorizedAhoCorasick from a Policy
    bitmask_processor.py     BitmaskLogitsProcessor (LogitsProcessor subclass)
    tool_guard.py            Post-generation tool action verification
    cache.py                 Thread-safe TTL cache for automata
    policy_watcher.py        Hot-reload daemon that watches YAML mtime
    config/example_policy.yaml
  tests/
  examples/
```

---

## License

This software is licensed under the RESK Software License. Commercial use requires a separate paid license. See the [LICENSE](LICENSE) file for details.

For commercial licensing inquiries, contact: contact@resk.fr
