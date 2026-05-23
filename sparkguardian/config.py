"""Configuration loader — TOML/YAML project-level + local overrides."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from sparkguardian.models.issue import Severity
from sparkguardian.rules.base import RuleConfig


@dataclass
class GuardianConfig:
    ignore_paths: list[str] = field(default_factory=list)
    rule_configs: dict[str, RuleConfig] = field(default_factory=dict)
    warning_threshold: int = 10
    fail_on_critical: bool = True
    fail_on_high: bool = False

    @classmethod
    def load(cls, config_path: str | None = None) -> GuardianConfig:
        if config_path is None:
            for candidate in (".sparkguardian.toml", ".sparkguardian.yaml", ".sparkguardian.yml"):
                p = Path(candidate)
                if p.exists():
                    config_path = str(p)
                    break

        if config_path is None:
            return cls()

        path = Path(config_path)
        if path.suffix == ".toml":
            return cls._from_toml(path)
        return cls._from_yaml(path)

    @classmethod
    def _from_toml(cls, path: Path) -> GuardianConfig:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls._parse(data)

    @classmethod
    def _from_yaml(cls, path: Path) -> GuardianConfig:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls._parse(data)

    @classmethod
    def _parse(cls, data: dict) -> GuardianConfig:
        # Support [sparkguardian] section or flat top-level keys
        root = data.get("sparkguardian", data)
        cfg = cls()
        cfg.ignore_paths = root.get("ignore_paths", [])
        cfg.warning_threshold = root.get("warning_threshold", 10)
        cfg.fail_on_critical = root.get("fail_on_critical", True)
        cfg.fail_on_high = root.get("fail_on_high", False)

        for rule_id, rule_data in data.get("rules", {}).items():
            severity = None
            if sv := rule_data.get("severity"):
                severity = Severity(sv.upper())
            cfg.rule_configs[rule_id] = RuleConfig(
                enabled=rule_data.get("enabled", True),
                severity=severity,
                threshold=rule_data.get("threshold"),
            )
        return cfg
