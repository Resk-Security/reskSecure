"""Example: Integration of reskSecure with a HuggingFace model.

Prerequisites:
    pip install resksecure resklogits transformers torch

Run:
    python examples/integration.py
"""

from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from resksecure import (
    BitmaskLogitsProcessor,
    PolicyWatcher,
    load_policy,
    verify_tool_action,
)

POLICY_PATH = Path(__file__).resolve().parent.parent / "src" / "resksecure" / "config" / "example_policy.yaml"
MODEL_NAME = "microsoft/phi-2"  # small model for demo

# --- 1. Load policy ---
policy_set = load_policy(POLICY_PATH)
print(f"Loaded policy v{policy_set.version}: {len(policy_set.policies)} policies")

# --- 2. (Optional) Start hot-reload watcher ---
watcher = PolicyWatcher(POLICY_PATH, interval=5.0, auto_start=True)
print(f"Policy watcher active (check every {watcher._interval}s)")

# --- 3. Load model & tokenizer ---
print(f"Loading model {MODEL_NAME}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
tokenizer.pad_token = tokenizer.eos_token
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)

# --- 4. Create processor for a given bitmask ---
# mask 7 (bits 0,1,2) = contributor rights
USER_MASK = 7
processor = BitmaskLogitsProcessor(
    mask=USER_MASK,
    model_name=MODEL_NAME,
    tokenizer=tokenizer,
    policy_set=policy_set,
    device="cpu",
)

# --- 5. Generate ---
prompt = "Write a SQL query to list all users:"
inputs = tokenizer(prompt, return_tensors="pt")

with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=50,
        logits_processor=[processor],
        pad_token_id=tokenizer.eos_token_id,
    )

response = tokenizer.decode(outputs[0], skip_special_tokens=True)
print(f"\nPrompt: {prompt}")
print(f"Response: {response}")

# --- 6. Verify tool actions ---
tool_checks = [
    ("read_email", "Reading email"),
    ("send_email", "Sending email"),
    ("write_sql", "Writing SQL (not in mask 7)"),
]

for tool_name, description in tool_checks:
    allowed = verify_tool_action(tool_name, USER_MASK, policy_set)
    print(f"  {description}: {'✓ ALLOWED' if allowed else '✗ BLOCKED'}")

# --- 7. Cleanup ---
watcher.stop()
print("\nDone.")
