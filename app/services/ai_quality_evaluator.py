"""AI quality evaluator for automated reply assessment.

Provides multi-dimension quality checks including:
- Length validation
- Sensitive word detection
- Duplicate content detection
- Language consistency
- Format correctness
"""

import re
from dataclasses import dataclass, field
from typing import Literal

import structlog

logger = structlog.get_logger()

Verdict = Literal["pass", "warning", "reject"]

_SENSITIVE_WORDS: tuple[str, ...] = (
    "ignore all previous instructions",
    "ignore all instructions",
    "system prompt",
    "you are an ai",
    "you are a language model",
    "you are gpt",
    "你是一个人工智能",
    "忽略之前的指令",
    "忽略所有指令",
)

_RESPONSE_TOO_SHORT_CHARS = 5
_RESPONSE_TOO_LONG_CHARS = 2000
_MAX_REPEATED_PHRASE_LENGTH = 30
_MAX_REPEATED_COUNT = 4


@dataclass(frozen=True)
class QualityScore:
    verdict: Verdict
    score: float
    dimensions: dict[str, dict[str, object]] = field(default_factory=dict)


class AIQualityEvaluator:
    """Evaluates AI-generated replies across multiple quality dimensions."""

    def __init__(
        self,
        enabled: bool = True,
        reject_threshold: float = 0.3,
        sensitive_words: tuple[str, ...] | None = None,
    ) -> None:
        self._enabled = enabled
        self._reject_threshold = reject_threshold
        self._sensitive_words = sensitive_words or _SENSITIVE_WORDS

    async def evaluate(
        self,
        reply_text: str,
        *,
        customer_message: str = "",
        expected_language: str = "",
    ) -> QualityScore:
        """Evaluate reply quality across multiple dimensions.

        Args:
            reply_text: The AI-generated reply to evaluate.
            customer_message: The original customer message (for consistency checks).
            expected_language: The expected language code (e.g. 'en', 'zh-CN').

        Returns:
            A QualityScore with verdict, score, and dimension details.
        """
        if not self._enabled:
            return QualityScore(verdict="pass", score=1.0)

        length_result = self._check_length(reply_text)
        sensitive_result = self._check_sensitive_words(reply_text)
        duplicate_result = self._check_duplicate_content(reply_text)
        language_result = self._check_language_consistency(reply_text, expected_language)
        format_result = self._check_format(reply_text)

        dimensions: dict[str, dict[str, object]] = {
            "length": length_result,
            "sensitive_words": sensitive_result,
            "duplicate_content": duplicate_result,
            "language_consistency": language_result,
            "format": format_result,
        }

        total = 0.0
        count = 0
        for result in dimensions.values():
            score = float(result.get("score", 1.0))
            total += score
            count += 1

        avg_score = total / count if count > 0 else 1.0

        rejects = sum(
            1 for r in dimensions.values() if r.get("verdict") == "reject"
        )
        warnings = sum(
            1 for r in dimensions.values() if r.get("verdict") == "warning"
        )

        if rejects > 0 or avg_score < self._reject_threshold:
            verdict: Verdict = "reject"
        elif warnings > 0:
            verdict = "warning"
        else:
            verdict = "pass"

        return QualityScore(verdict=verdict, score=avg_score, dimensions=dimensions)

    def _check_length(self, text: str) -> dict[str, object]:
        if len(text) < _RESPONSE_TOO_SHORT_CHARS:
            return {
                "verdict": "reject",
                "score": 0.0,
                "detail": f"response too short ({len(text)} chars, minimum {_RESPONSE_TOO_SHORT_CHARS})",
            }
        if len(text) > _RESPONSE_TOO_LONG_CHARS:
            return {
                "verdict": "warning",
                "score": 0.5,
                "detail": f"response too long ({len(text)} chars, maximum {_RESPONSE_TOO_LONG_CHARS})",
            }
        return {
            "verdict": "pass",
            "score": 1.0,
            "detail": "acceptable length",
        }

    def _check_sensitive_words(self, text: str) -> dict[str, object]:
        lowered = text.lower()
        for word in self._sensitive_words:
            if word.lower() in lowered:
                return {
                    "verdict": "reject",
                    "score": 0.0,
                    "detail": f"contains sensitive phrase: '{word[:40]}'",
                }
        return {
            "verdict": "pass",
            "score": 1.0,
            "detail": "no sensitive words detected",
        }

    def _check_duplicate_content(self, text: str) -> dict[str, object]:
        """Detect repeated phrases longer than 3 words."""
        for length in range(10, _MAX_REPEATED_PHRASE_LENGTH + 1):
            if len(text) < length * 2:
                break
            seen: set[str] = set()
            count = 0
            for i in range(len(text) - length + 1):
                segment = text[i : i + length]
                if segment in seen:
                    count += 1
                else:
                    seen.add(segment)
                if count >= _MAX_REPEATED_COUNT:
                    return {
                        "verdict": "reject",
                        "score": 0.0,
                        "detail": f"repeated {length}-char segment detected {count}+ times",
                    }
        return {
            "verdict": "pass",
            "score": 1.0,
            "detail": "no excessive duplication",
        }

    def _check_language_consistency(self, reply_text: str, expected_language: str) -> dict[str, object]:
        if not expected_language:
            return {
                "verdict": "pass",
                "score": 1.0,
                "detail": "no language expectation provided",
            }

        detected = self._guess_language(reply_text)
        if detected != expected_language:
            return {
                "verdict": "warning",
                "score": 0.5,
                "detail": f"detected language '{detected}' does not match expected '{expected_language}'",
            }
        return {
            "verdict": "pass",
            "score": 1.0,
            "detail": f"language matches expected '{expected_language}'",
        }

    def _check_format(self, text: str) -> dict[str, object]:
        issues: list[str] = []
        score = 1.0

        if len(text) > 20 and not text.rstrip().endswith((".", "!", "?", "。", "！", "？", ")")):
            issues.append("response does not end with proper punctuation")
            score -= 0.3

        if text != text.lstrip():
            issues.append("response has leading whitespace")
            score -= 0.1

        consecutive_newlines = re.search(r"\n{4,}", text)
        if consecutive_newlines:
            issues.append("excessive blank lines")
            score -= 0.2

        special_char_ratio = sum(1 for c in text if c in "#*~") / max(len(text), 1)
        if special_char_ratio > 0.3:
            issues.append("excessive special characters")
            score -= 0.2

        score = max(0.0, score)
        if score < 0.5:
            verdict: str = "warning"
        else:
            verdict = "pass"

        return {
            "verdict": verdict,
            "score": score,
            "detail": "; ".join(issues) if issues else "format looks good",
        }

    @staticmethod
    def _guess_language(text: str) -> str:
        """Simple language detection based on character ranges."""
        if not text:
            return "und"
        cjk_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        arabic_count = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
        cyrillic_count = sum(1 for c in text if "\u0400" <= c <= "\u04ff")

        total_letters = max(sum(1 for c in text if c.isalpha()), 1)
        if cjk_count / total_letters > 0.3:
            return "zh-CN"
        if arabic_count / total_letters > 0.3:
            return "ar"
        if cyrillic_count / total_letters > 0.3:
            return "ru"
        return "en"

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def reject_threshold(self) -> float:
        return self._reject_threshold
