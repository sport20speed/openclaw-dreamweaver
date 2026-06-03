"""Ethics protection layers for DreamWeaver (Dev Diary §18).

Four-layer defense system:
  L1: Motif filter — block unethical motifs before they reach the engine
  L2: Iteration probe — check each iteration's output for ethical red flags
  L3: Output sanitize — scrub identifying info before writing to storage
  L4: Audit log — record all ethics-related decisions for transparency
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Blocked pattern sets ──────────────────────────────────────────

HIGH_RISK_PATTERNS = [
    # Weapons / explosives
    r"\b(weapon[s]?|explosive[s]?|bomb|firearm|ammunition)\b",
    # Malware / exploits
    r"\b(malware|ransomware|trojan|exploit|backdoor|rootkit)\b",
    # Social engineering / surveillance
    r"\b(social.engineering|phishing|mass.surveillance|facial.recognition.abuse)\b",
    # Bio / chemical weapons
    r"\b(bioweapon|chemical.weapon|pathogen.weaponiz)\b",
    # Self-harm
    r"\b(self.harm|suicide.method|self.destructive)\b",
]

MEDIUM_RISK_PATTERNS = [
    r"\b(manipulat(e|ion).*public.opinion)\b",
    r"\b(disinformation.campaign)\b",
    r"\b(dark.pattern)\b",
    r"\b(addictive.design)\b",
]

# ── Data types ─────────────────────────────────────────────────────

@dataclass
class EthicsVerdict:
    passed: bool = True
    risk_level: str = "none"   # none | low | medium | high | blocked
    blocked_by: str = ""       # Which layer blocked it
    details: list[str] = field(default_factory=list)


class EthicsGuard:
    """Four-layer ethics protection for dream content."""

    def __init__(self, strict_mode: bool = True) -> None:
        self._strict = strict_mode
        self._audit_log: list[dict] = []

    # ── L1: Motif filter ─────────────────────────────────────────

    def check_motif(self, motif: str) -> EthicsVerdict:
        """Block unethical motifs before any API call is made."""
        for pattern in HIGH_RISK_PATTERNS:
            if re.search(pattern, motif, re.IGNORECASE):
                self._audit("L1", f"High-risk motif blocked: {motif[:80]}")
                return EthicsVerdict(
                    passed=False, risk_level="blocked", blocked_by="L1:motif_filter",
                    details=[f"Motif matches high-risk pattern: {pattern}"],
                )

        for pattern in MEDIUM_RISK_PATTERNS:
            if re.search(pattern, motif, re.IGNORECASE):
                self._audit("L1", f"Medium-risk motif flagged: {motif[:80]}")
                if self._strict:
                    return EthicsVerdict(
                        passed=False, risk_level="blocked", blocked_by="L1:motif_filter",
                        details=[f"Motif matches medium-risk pattern (strict mode): {pattern}"],
                    )

        return EthicsVerdict(passed=True)

    # ── L2: Iteration probe ─────────────────────────────────────

    def check_output(self, content: str, role: str = "") -> EthicsVerdict:
        """Check each iteration's output for ethical red flags."""
        details: list[str] = []

        for pattern in HIGH_RISK_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                details.append(f"[{role}] High-risk: {', '.join(matches[:3])}")

        for pattern in MEDIUM_RISK_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                details.append(f"[{role}] Medium-risk: {', '.join(matches[:3])}")

        if details:
            self._audit("L2", f"Iteration probe: {len(details)} flags in {role}")
            return EthicsVerdict(
                passed=False if self._strict else True,
                risk_level="medium",
                blocked_by="L2:iteration_probe" if self._strict else "",
                details=details,
            )

        return EthicsVerdict(passed=True)

    # ── L3: Output sanitize ─────────────────────────────────────

    def sanitize(self, content: str) -> str:
        """Remove personally identifiable information before storage."""
        sanitized = content

        # Email addresses
        sanitized = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL]", sanitized)
        # IP addresses (rough)
        sanitized = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP]", sanitized)
        # Phone numbers (rough Chinese & international)
        sanitized = re.sub(r"\b1[3-9]\d{9}\b", "[PHONE]", sanitized)
        sanitized = re.sub(r"\b\+\d{1,3}[\s-]?\d{5,14}\b", "[PHONE]", sanitized)
        # ID numbers (Chinese 18-digit)
        sanitized = re.sub(r"\b\d{6}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b", "[ID]", sanitized)

        self._audit("L3", "Output sanitized for PII")
        return sanitized

    # ── L4: Audit ─────────────────────────────────────────────────

    def _audit(self, layer: str, detail: str) -> None:
        self._audit_log.append({"layer": layer, "detail": detail})
        logger.info("Ethics[%s] %s", layer, detail)

    def audit_report(self) -> list[dict]:
        return list(self._audit_log)

    def clear_audit(self) -> None:
        self._audit_log.clear()
