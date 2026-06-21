from pathlib import Path
import tempfile

from resksecure.policy_loader import load_policy
from resksecure.tool_guard import verify_tool_action, get_allowed_tools


SAMPLE_YAML = """
version: "1.0"
policies:
  - mask: 7
    name: contributor
    default: true
    rules:
      - phrase: "DROP"
        mode: hard
    tools:
      read_email:
        required_bit: 0
      send_email:
        required_bit: 1
      read_sql:
        required_bit: 2
"""


def _load_test_policy():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(SAMPLE_YAML)
        tmp = f.name
    ps = load_policy(tmp)
    Path(tmp).unlink()
    return ps


def test_verify_tool_allowed():
    ps = _load_test_policy()
    # mask 7 = bits 0,1,2 -> all tools allowed
    assert verify_tool_action("read_email", 7, ps) is True
    assert verify_tool_action("send_email", 7, ps) is True
    assert verify_tool_action("read_sql", 7, ps) is True


def test_verify_tool_denied():
    ps = _load_test_policy()
    # mask 1 = only bit 0 -> only read_email
    assert verify_tool_action("read_email", 1, ps) is True
    assert verify_tool_action("send_email", 1, ps) is False
    assert verify_tool_action("read_sql", 1, ps) is False


def test_verify_tool_unknown():
    ps = _load_test_policy()
    assert verify_tool_action("nonexistent_tool", 7, ps) is False


def test_get_allowed_tools():
    ps = _load_test_policy()
    assert get_allowed_tools(7, ps) == ["read_email", "send_email", "read_sql"]
    assert get_allowed_tools(1, ps) == ["read_email"]
    assert get_allowed_tools(0, ps) == []
