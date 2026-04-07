"""Tests for severity classification rules."""

import pytest

from src.application.services.severity_classifier import (
    AvailabilityDownRule,
    SeverityClassifier,
    SeverityContext,
)
from src.domain.value_objects.severity import Severity


class TestAvailabilityDownRule:
    """Reference payload and homologous event types map to CRITICAL."""

    @pytest.mark.parametrize(
        ("event_type",),
        [
            ("device_down",),
            ("link_down",),
            ("interface_down",),
            ("host_offline",),
        ],
    )
    def test_critical_for_down_or_offline(self, event_type: str) -> None:
        rule = AvailabilityDownRule()
        ctx = SeverityContext(
            event_type=event_type,
            metric_value=0.0,
            metadata={},
        )
        assert rule.apply(ctx) == Severity.CRITICAL

    def test_no_match_for_unrelated_type(self) -> None:
        rule = AvailabilityDownRule()
        ctx = SeverityContext(
            event_type="temperature_high",
            metric_value=0.0,
            metadata={},
        )
        assert rule.apply(ctx) is None


class TestSeverityClassifierIntegration:
    """Default rule chain aligns reference payload with CRITICAL."""

    def test_reference_payload_device_down_is_critical(self) -> None:
        classifier = SeverityClassifier()
        severity = classifier.classify(
            event_type="device_down",
            metric_value=0.0,
            metadata={"site": "Bogotá", "ip": "10.0.2.15"},
        )
        assert severity == Severity.CRITICAL

    def test_metric_threshold_still_first(self) -> None:
        classifier = SeverityClassifier()
        severity = classifier.classify(
            event_type="heartbeat_ok",
            metric_value=100.0,
            metadata={},
        )
        assert severity == Severity.CRITICAL
