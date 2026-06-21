# reskSecure 🔒

**Bitmask-based LLM security firewall.**

A policy-driven `LogitsProcessor` that restricts LLM output based on capability bitmasks. Uses [resklogits](https://github.com/anomalyco/resk-lib) (`VectorizedAhoCorasick`) for GPU-accelerated pattern matching.

## Architecture

```
User request with bitmask ──▶ BitmaskLogitsProcessor
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                  ▼
             PolicyLoader       TrieFactory         ToolGuard
                    │                 │                  │
                    ▼                 ▼                  ▼
             YAML config      VectorizedAhoCorasick   Bitmask check
                                  (resklogits)
```

## Quick Start

```python
from resksecure import BitmaskLogitsProcessor, load_policy, verify_tool_action

# 1. Load policy
policy_set = load_policy("config/policy.yaml")

# 2. Create processor
processor = BitmaskLogitsProcessor(
    mask=7,                      # bitmask from JWT
    model_name="mistralai/Mistral-7B-v0.1",
    tokenizer=tokenizer,
    policy_set=policy_set,
    device="cuda",
)

# 3. Generate
outputs = model.generate(**inputs, logits_processor=[processor])

# 4. Verify tool calls
if has_tool_call(response):
    if not verify_tool_action("send_email", user_mask=7, policy_set=policy_set):
        raise PermissionError("Action not allowed")
```

## Features

- **Dual severity**: `hard` mode (bans tokens completely) and `bias` mode (reduces logits)
- **Strict mode**: forces EOS at the first sign of a banned prefix
- **Hot-reload**: `PolicyWatcher` detects file changes and invalidates the cache
- **Thread-safe cache**: TTL-based, per `(mask, model_name)` entries
- **Tool guard**: post-generation bitmask verification for tool calls
- **GPU-accelerated**: uses `resklogits`' `VectorizedAhoCorasick` for fast pattern matching

## Policy Format

```yaml
version: "0.1.0"
policies:
  - mask: 7            # capabilities bitmask (from JWT)
    name: contributor
    strict: false
    default: true
    rules:
      - phrase: "DROP TABLE"
        mode: hard
      - phrase: "salaries"
        mode: bias
        penalty: -5.0
    tools:
      read_email:
        required_bit: 0
      send_email:
        required_bit: 1
```

## Dependencies

- `resklogits >= 0.1.0`
- `torch >= 2.0.0`
- `transformers >= 4.35.0`
- `pyyaml >= 6.0`
