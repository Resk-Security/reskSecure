from __future__ import annotations
from .policy_loader import PolicySet


def verify_tool_action(
    tool_name: str,
    user_mask: int,
    policy_set: PolicySet,
) -> bool:
    """Check whether a tool action is allowed for the given user mask.

    Looks up the tool's required bit from the policy matching *user_mask*,
    then checks if that bit is set in the mask.

    Returns:
        True if the tool is allowed, False otherwise.
    """
    policy = policy_set.get_policy_for_mask(user_mask)
    if policy is None:
        return False
    tool_rule = policy.tools.get(tool_name)
    if tool_rule is None:
        return False
    required_bit = tool_rule.required_bit
    return (user_mask & (1 << required_bit)) != 0


def get_allowed_tools(
    user_mask: int,
    policy_set: PolicySet,
) -> list[str]:
    """Return the list of tool names the user mask permits."""
    policy = policy_set.get_policy_for_mask(user_mask)
    if policy is None:
        return []
    return [
        name
        for name, rule in policy.tools.items()
        if (user_mask & (1 << rule.required_bit)) != 0
    ]
