"""SparkGuardian — PySpark auditing, optimization, and governance framework.

Production-grade static + dynamic analysis with local AI assistance, cost
estimation, longitudinal history, and SARIF v2.1.0 output for CI/CD.

Quick start:
    >>> from sparkguardian.parser.ast_analyzer import ASTAnalyzer
    >>> report = ASTAnalyzer().analyze_file("app.py")
    >>> for issue in report.active_issues:
    ...     print(issue)

CLI usage:
    $ sparkguardian analyze app.py
    $ sparkguardian fix app.py --dry-run
    $ sparkguardian cost app.py --cloud databricks
    $ sparkguardian remediation app.py

Docs: https://github.com/MohamedDataX/sparkguardian
"""
from sparkguardian.constants import APP_NAME, APP_VERSION

__version__ = APP_VERSION
__author__ = "SparkGuardian Contributors"
__license__ = "MIT"
__all__ = ["APP_NAME", "__version__", "__author__", "__license__"]
