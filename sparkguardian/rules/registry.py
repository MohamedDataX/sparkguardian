from __future__ import annotations

from sparkguardian.rules.base import BaseRule, RuleConfig


class RuleRegistry:
    _rules: dict[str, type[BaseRule]] = {}

    @classmethod
    def register(cls, rule_cls: type[BaseRule]) -> type[BaseRule]:
        cls._rules[rule_cls.rule_id] = rule_cls
        return rule_cls

    @classmethod
    def get(cls, rule_id: str) -> type[BaseRule] | None:
        return cls._rules.get(rule_id)

    @classmethod
    def all_rule_classes(cls) -> list[type[BaseRule]]:
        return list(cls._rules.values())

    @classmethod
    def build_rules(cls, configs: dict[str, RuleConfig] | None = None) -> list[BaseRule]:
        configs = configs or {}
        rules: list[BaseRule] = []
        for rule_id, rule_cls in cls._rules.items():
            config = configs.get(rule_id, RuleConfig())
            instance = rule_cls(config)
            if instance.enabled:
                rules.append(instance)
        return rules

    @classmethod
    def rule_ids(cls) -> list[str]:
        return list(cls._rules.keys())
