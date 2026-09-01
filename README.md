# reskSecure

> Per-user LLM firewall: unauthorized content becomes physically ungeneratable.

[![PyPI version](https://img.shields.io/pypi/v/resksecure.svg)](https://pypi.org/project/resksecure/)
[![PyPI downloads](https://img.shields.io/pypi/dm/resksecure.svg)](https://pypi.org/project/resksecure/)
[![Python versions](https://img.shields.io/pypi/pyversions/resksecure.svg)](https://pypi.org/project/resksecure/)
[![License](https://img.shields.io/badge/license-RESK-blue)](LICENSE)

## Installation

```bash
pip install resksecure
```

Requires Python ≥ 3.13, PyTorch ≥ 2.0, transformers ≥ 4.35, resklogits ≥ 0.1.0.

## Usage rapide (30 seconds)

Define a policy (`policy.yaml`):

```yaml
version: "1.0"
policies:
  - mask: 7
    name: contributor
    default: true
    rules:
      - { phrase: "DROP TABLE", mode: hard }
      - { phrase: "salaries",   mode: bias, penalty: -5.0 }
    tools:
      send_email: { required_bit: 1 }
      read_sql:   { required_bit: 2 }
```

Enforce it inside generation:

```python
from resksecure import BitmaskLogitsProcessor, load_policy, verify_tool_action

policy = load_policy("policy.yaml")
processor = BitmaskLogitsProcessor(
    mask=7, model_name="mistralai/Mistral-7B-v0.1",
    tokenizer=tokenizer, policy_set=policy, device="cuda",
)
outputs = model.generate(**inputs, logits_processor=[processor])

# Defense-in-depth: verify tool calls against the bitmask
if not verify_tool_action("send_email", user_mask=7, policy_set=policy):
    raise PermissionError("Action not authorized")
```

## Pourquoi reskSecure ?

Prompt filters are jailbreakable; post-generation moderation detects violations **after** the content is already emitted. reskSecure works at the **logits level**: every candidate token is checked against an Aho-Corasick automaton before sampling. If a user's capability bitmask doesn't allow it, the model *cannot* start generating the banned phrase or the disallowed tool call — no prompt engineering can change that.

| | **reskSecure** | Prompt-based filters | Post-generation moderation | Generic policy engines (OPA…) |
|---|---|---|---|---|
| Where it acts | Inside the generation loop | On the prompt | On the finished output | App/API layer |
| Bypassable by prompt injection | ❌ | ✅ | ❌ | ⚠️ if model emits |
| Forbidden content ever emitted | No | Yes | **Yes — first** | Yes |
| Per-user permissions | ✅ capability bitmask | ⚠️ prompt-level | ❌ global policy | ✅ but not generation |
| Tool-call gating at token level | ✅ trigger phrases blocked per bit | ❌ | ❌ | ⚠️ execution-time only |
| Policy hot-reload, no restart | ✅ `PolicyWatcher` | — | — | ✅ |
| What it protects | LLM output itself | LLM input | Nothing retroactively | App resources |

## Documentation

- Policy reference (all fields) — below and in [`config/example_policy.yaml`](src/resksecure/config/example_policy.yaml)
- Examples — [`examples/`](examples/)
- Engine internals — [resklogits](https://github.com/Resk-Security/resk-logits)

### Policy reference

| Field | Type | Description |
|---|---|---|
| `mask` | int | Capability bitmask identifying this policy |
| `name` | string | Human-readable policy name |
| `strict` | bool | Stop generation at the first banned **prefix** |
| `default` | bool | Used when no exact mask matches |
| `rules` | list | Phrase rules: `phrase`, `mode` (`hard` = `-inf`, `bias` = penalty), `penalty` |
| `tools` | dict | Tool name → `required_bit` + optional `trigger_phrases` |

## How it works

```
User request + bitmask (e.g. 7)
   → BitmaskLogitsProcessor intercepts each token prediction
   → Aho-Corasick automaton (resklogits, GPU-accelerated) checks if the token
     starts/completes a banned phrase
   → hard mode: logit = -inf · bias mode: logit += penalty
   → complete match ⇒ EOS forced, generation stops immediately
```

Tool calls are gated at the token level too: without the required bit, the first token of `send_email(` can never be generated.

**Features**: hard/bias severity modes · strict prefix mode · thread-safe (mask, model) automaton cache with TTL · YAML policies with hot-reload · post-generation `verify_tool_action` defense-in-depth · receives a raw integer bitmask (auth/JWT stays in your app).

## Package structure

```
src/resksecure/
  policy_loader.py         YAML parsing, Policy/PolicySet models
  trie_factory.py          Builds VectorizedAhoCorasick from a Policy
  bitmask_processor.py     BitmaskLogitsProcessor
  tool_guard.py            Post-generation tool action verification
  cache.py                 Thread-safe TTL cache for automata
  policy_watcher.py        Hot-reload daemon
```

## Ecosystem

Built on [resklogits](https://github.com/Resk-Security/resk-logits) · pairs with [Resk-LLM](https://github.com/Resk-Security/Resk-LLM) (input-time detection) and [ReskPoints](https://github.com/Resk-Security/ReskPoints) (action logging). The [Resk](https://github.com/Resk-Security/Resk) full-stack app wires all three together.

## License

RESK Software License — commercial use requires a paid license. See [LICENSE](LICENSE) or contact contact@resk.fr.
