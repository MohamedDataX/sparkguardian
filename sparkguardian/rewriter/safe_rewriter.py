"""Safe source rewriting engine — preserves formatting/comments/imports."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import libcst as cst

from sparkguardian.models.issue import Issue
from sparkguardian.rewriter.diff_generator import unified_diff
from sparkguardian.rewriter.transformer import Repartition1ToCoalesce
from sparkguardian.utils.file_utils import backup_file

_RULE_TRANSFORMERS: dict[str, type[cst.CSTTransformer]] = {
    "CY008": Repartition1ToCoalesce,
}


@dataclass
class RewriteResult:
    filepath: str
    original: str
    modified: str
    applied_rules: list[str] = field(default_factory=list)
    skipped_rules: list[str] = field(default_factory=list)

    @property
    def diff(self) -> str:
        return unified_diff(self.original, self.modified, self.filepath)

    @property
    def changed(self) -> bool:
        return self.original != self.modified


class SafeRewriter:
    def rewrite(
        self,
        filepath: str,
        issues: list[Issue],
        *,
        dry_run: bool = False,
        interactive: bool = False,
        autofix_only: bool = True,
    ) -> RewriteResult:
        source = Path(filepath).read_text(encoding="utf-8")
        result = RewriteResult(filepath=filepath, original=source, modified=source)

        fixable = [i for i in issues if i.autofix_available and i.rule_id in _RULE_TRANSFORMERS]

        for issue in fixable:
            if interactive:
                answer = _prompt_user(issue)
                if not answer:
                    issue_id = issue.rule_id
                    result.skipped_rules.append(issue_id)
                    continue

            transformer_cls = _RULE_TRANSFORMERS[issue.rule_id]
            try:
                tree = cst.parse_module(result.modified)
                new_tree = tree.visit(transformer_cls())
                result.modified = new_tree.code
                result.applied_rules.append(issue.rule_id)
            except Exception:
                result.skipped_rules.append(issue.rule_id)

        if result.changed and not dry_run:
            backup_file(filepath)
            Path(filepath).write_text(result.modified, encoding="utf-8")

        return result


def _prompt_user(issue: Issue) -> bool:
    print(f"\nRule {issue.rule_id} detected.")
    print(f"  {issue.message}")
    print(f"  Suggestion: {issue.suggestion}")
    answer = input("Apply fix? [y/n] ").strip().lower()
    return answer == "y"
