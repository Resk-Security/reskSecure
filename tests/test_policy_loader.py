from pathlib import Path
import tempfile

from resksecure.policy_loader import load_policy


SAMPLE_YAML = """
version: "1.0"
policies:
  - mask: 7
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
"""


def test_load_policy():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(SAMPLE_YAML)
        tmp = f.name
    try:
        policy_set = load_policy(tmp)
        assert policy_set.version == "1.0"
        assert 7 in policy_set.policies
        policy = policy_set.get_policy_for_mask(7)
        assert policy is not None
        assert policy.name == "contributor"
        assert len(policy.rules) == 2
        assert policy.rules[0].phrase == "DROP TABLE"
        assert policy.rules[0].mode == "hard"
        assert policy.rules[1].phrase == "salaries"
        assert policy.rules[1].mode == "bias"
        assert policy.rules[1].penalty == -5.0
        assert "read_email" in policy.tools
        assert policy.tools["read_email"].required_bit == 0
        assert policy.tools["send_email"].required_bit == 1
    finally:
        Path(tmp).unlink()


def test_default_policy():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(SAMPLE_YAML)
        tmp = f.name
    try:
        policy_set = load_policy(tmp)
        assert policy_set.default_policy is not None
        assert policy_set.default_policy.mask == 7
    finally:
        Path(tmp).unlink()


def test_policy_not_found():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(SAMPLE_YAML)
        tmp = f.name
    try:
        policy_set = load_policy(tmp)
        policy = policy_set.get_policy_for_mask(99)
        assert policy is policy_set.default_policy
    finally:
        Path(tmp).unlink()


def test_empty_yaml():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("")
        tmp = f.name
    try:
        policy_set = load_policy(tmp)
        assert len(policy_set.policies) == 0
        assert policy_set.get_policy_for_mask(0) is None
    finally:
        Path(tmp).unlink()
