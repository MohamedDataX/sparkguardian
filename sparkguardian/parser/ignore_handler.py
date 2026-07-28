"""Suppression of findings via ``# cy:ignore`` comments.

Two forms are supported, same idea as flake8's noqa:

    df.collect()                    # cy:ignore CY001
    # cy:ignore-start CY004,CY005
    ...
    # cy:ignore-end CY004,CY005

Suppressed issues are marked IGNORED rather than dropped, so reports can still
show how much noise a codebase is silencing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sparkguardian.models.issue import Issue, IssueStatus

# The rule-id group is deliberately loose ([\w,\s]+) so "CY001, CY002" with any
# spacing works; the ids get split and stripped below.
_INLINE_PATTERN = re.compile(r"#\s*cy:ignore\s+([\w,\s]+)")
_BLOCK_START_PATTERN = re.compile(r"#\s*cy:ignore-start\s+([\w,\s]+)")
_BLOCK_END_PATTERN = re.compile(r"#\s*cy:ignore-end\s+([\w,\s]+)")


@dataclass
class IgnoreDirective:
    rule_ids: set[str]
    line: int
    is_block: bool = False
    end_line: int = -1


def parse_ignore_directives(source: str) -> list[IgnoreDirective]:
    directives: list[IgnoreDirective] = []
    # Tracks blocks opened but not yet closed, keyed per rule id. Each rule is
    # tracked separately so a block can cover CY004 and CY005 and close them on
    # different lines.
    active_blocks: dict[str, int] = {}

    for lineno, line in enumerate(source.splitlines(), start=1):
        if m := _INLINE_PATTERN.search(line):
            ids = {r.strip() for r in m.group(1).split(",")}
            directives.append(IgnoreDirective(rule_ids=ids, line=lineno, is_block=False))

        if m := _BLOCK_START_PATTERN.search(line):
            for rule_id in (r.strip() for r in m.group(1).split(",")):
                active_blocks[rule_id] = lineno

        if m := _BLOCK_END_PATTERN.search(line):
            for rule_id in (r.strip() for r in m.group(1).split(",")):
                if rule_id in active_blocks:
                    start = active_blocks.pop(rule_id)
                    directives.append(
                        IgnoreDirective(
                            rule_ids={rule_id},
                            line=start,
                            is_block=True,
                            end_line=lineno,
                        )
                    )

    # Blocks left open at EOF are simply dropped: a start with no end is more
    # likely a typo than an intent to silence the rest of the file.
    return directives


def apply_ignores(issues: list[Issue], directives: list[IgnoreDirective]) -> list[Issue]:
    """Mark issues covered by a directive as IGNORED. Mutates in place."""
    for issue in issues:
        line = issue.location.line
        for directive in directives:
            rule_matches = issue.rule_id in directive.rule_ids
            if not rule_matches:
                continue
            # Inline directives only cover their own line; blocks cover the
            # whole range, endpoints included.
            if not directive.is_block and directive.line == line:
                issue.status = IssueStatus.IGNORED
                issue.ignore_reason = f"cy:ignore on line {directive.line}"
            elif directive.is_block and directive.line <= line <= directive.end_line:
                issue.status = IssueStatus.IGNORED
                issue.ignore_reason = (
                    f"cy:ignore-start block lines {directive.line}-{directive.end_line}"
                )
    return issues
