from __future__ import annotations

from skills.tos_legal_checker.analysis import analyze
from skills.tos_legal_checker.models import (
    TosLegalCheckRequest,
    TosLegalCheckResult,
)


def run_tos_legal_check(request: TosLegalCheckRequest) -> TosLegalCheckResult:
    return analyze(request)
