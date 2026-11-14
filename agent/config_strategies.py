"""Proposal strategies under A/B test (X2), read from agent/config.yaml."""

from agent.settings import config


def strategies() -> dict[str, str]:
    return dict(config().get("proposal_strategies") or {})
