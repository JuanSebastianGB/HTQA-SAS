"""Severity classification service using strategy pattern."""

from collections.abc import Sequence
from dataclasses import dataclass

from src.domain.value_objects.severity import Severity


@dataclass(frozen=True)
class SeverityContext:
    """Input context used by severity rules."""

    event_type: str
    metric_value: float
    metadata: dict[str, str]


class SeverityRule:
    """Rule contract for classifying severity without changing classifier internals."""

    def apply(self, context: SeverityContext) -> Severity | None:
        """Return a severity when the rule matches; otherwise None."""
        raise NotImplementedError


class MetricThresholdRule(SeverityRule):
    """Classify by metric thresholds."""

    def apply(self, context: SeverityContext) -> Severity | None:
        if context.metric_value >= 100:
            return Severity.CRITICAL
        if context.metric_value >= 50:
            return Severity.HIGH
        return None


class AvailabilityDownRule(SeverityRule):
    """Classify availability loss: *_down / offline in event_type → CRITICAL."""

    def apply(self, context: SeverityContext) -> Severity | None:
        et = context.event_type.lower()
        if et.endswith("_down") or "offline" in et:
            return Severity.CRITICAL
        return None


class EventTypeKeywordRule(SeverityRule):
    """Classify by event-type keywords."""

    def apply(self, context: SeverityContext) -> Severity | None:
        event_type_lower = context.event_type.lower()
        if "error" in event_type_lower or "failure" in event_type_lower:
            return Severity.HIGH
        if "warning" in event_type_lower or "degraded" in event_type_lower:
            return Severity.MEDIUM
        return None


class MetadataPriorityRule(SeverityRule):
    """Classify by metadata priority hints."""

    def apply(self, context: SeverityContext) -> Severity | None:
        priority = context.metadata.get("priority", "").lower()
        if priority == "critical":
            return Severity.CRITICAL
        if priority == "high":
            return Severity.HIGH
        return None


class SeverityClassifier:
    """Strategy pattern for classifying event severity."""

    def __init__(self, rules: Sequence[SeverityRule] | None = None):
        self._rules = (
            list(rules)
            if rules is not None
            else [
                MetricThresholdRule(),
                AvailabilityDownRule(),
                EventTypeKeywordRule(),
                MetadataPriorityRule(),
            ]
        )

    def classify(self, event_type: str, metric_value: float, metadata: dict[str, str]) -> Severity:
        """Classify severity based on event type and metric value."""
        context = SeverityContext(
            event_type=event_type,
            metric_value=metric_value,
            metadata=metadata,
        )
        for rule in self._rules:
            severity = rule.apply(context)
            if severity is not None:
                return severity

        # Default to low
        return Severity.LOW
