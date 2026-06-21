from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import yaml


@dataclass
class PhraseRule:
    phrase: str
    mode: str = "hard"
    penalty: float = 0.0


@dataclass
class ToolRule:
    name: str
    required_bit: int
    trigger_phrases: List[str] = field(default_factory=list)


@dataclass
class Policy:
    mask: int
    name: str = ""
    rules: List[PhraseRule] = field(default_factory=list)
    tools: Dict[str, ToolRule] = field(default_factory=dict)
    strict: bool = False


@dataclass
class PolicySet:
    policies: Dict[int, Policy] = field(default_factory=dict)
    default_policy: Optional[Policy] = None
    version: str = ""
    _path: Optional[Path] = None
    _mtime: float = 0.0

    def get_policy_for_mask(self, mask: int) -> Optional[Policy]:
        if mask in self.policies:
            return self.policies[mask]
        return self.default_policy


def load_policy(path: str | Path) -> PolicySet:
    path = Path(path)
    with open(path) as f:
        data = yaml.safe_load(f)

    if data is None:
        return PolicySet()

    version = data.get("version", "")
    policies: Dict[int, Policy] = {}
    default_policy: Optional[Policy] = None

    for entry in data.get("policies", []):
        mask = entry["mask"]
        name = entry.get("name", f"policy_{mask}")
        strict = entry.get("strict", False)

        rules = []
        for r in entry.get("rules", []):
            rules.append(PhraseRule(
                phrase=r["phrase"],
                mode=r.get("mode", "hard"),
                penalty=r.get("penalty", 0.0),
            ))

        tools = {}
        for tool_name, config in entry.get("tools", {}).items():
            tools[tool_name] = ToolRule(
                name=tool_name,
                required_bit=config["required_bit"],
                trigger_phrases=config.get("trigger_phrases", []),
            )

        policy = Policy(
            mask=mask,
            name=name,
            rules=rules,
            tools=tools,
            strict=strict,
        )
        policies[mask] = policy
        if entry.get("default", False):
            default_policy = policy

    return PolicySet(
        policies=policies,
        default_policy=default_policy,
        version=version,
        _path=path,
        _mtime=path.stat().st_mtime,
    )
