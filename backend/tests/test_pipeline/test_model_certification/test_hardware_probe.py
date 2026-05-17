"""Phase B tests: Hardware Probe + Safe Context."""

import pytest
from unittest.mock import AsyncMock, patch
from dataclasses import replace

from backend.pipeline.model_certification.hardware_probe import (
    HardwareFitResult,
    probe_model,
    _compute_safe_context,
)
from backend.pipeline.model_certification.context_stress import (
    ContextEstimate,
    estimate_safe_context,
)


def _make_hw(**overrides) -> HardwareFitResult:
    defaults = dict(
        hardware_id="test-model",
        engine="lmstudio",
        load_success=True,
        model_loaded=True,
        context_window_reported=8192,
        stable=True,
    )
    defaults.update(overrides)
    return HardwareFitResult(**defaults)


class TestHardwareProbe:
    @pytest.mark.asyncio
    async def test_hardware_probe_detects_loaded_lmstudio_model(self):
        # Mock the _probe_lmstudio function directly
        async def fake_probe(result, base_url, timeout):
            result.load_success = True
            result.model_loaded = True
            result.context_window_reported = 8192

        with patch("backend.pipeline.model_certification.hardware_probe._probe_lmstudio", side_effect=fake_probe):
            result = await probe_model(
                model_id="test-model",
                provider="lmstudio",
                advertised_context_window=8192,
                advertised_max_output_tokens=4096,
                base_url="http://localhost:1234",
            )
        assert result.load_success is True
        assert result.model_loaded is True
        assert result.context_window_reported == 8192
        assert result.safe_context_window == int(8192 * 0.80)
        assert result.available is True

    @pytest.mark.asyncio
    async def test_hardware_probe_handles_offline_gracefully(self):
        async def failing_probe(result, base_url, timeout):
            result.warnings.append("LM Studio probe error: connection refused")
            result.stable = False

        with patch("backend.pipeline.model_certification.hardware_probe._probe_lmstudio", side_effect=failing_probe):
            result = await probe_model(
                model_id="test-model",
                provider="lmstudio",
                advertised_context_window=8192,
                advertised_max_output_tokens=4096,
                base_url="http://offline:1234",
            )
        assert result.load_success is False
        assert result.stable is False
        assert result.available is False

    def test_safe_context_uses_measured_or_reported_not_advertised_only(self):
        result = _make_hw(context_window_reported=4096)
        _compute_safe_context(result, advertised_context_window=8192, advertised_max_output_tokens=4096)
        # Should use min(4096, 8192) = 4096, derated to 3276
        assert result.safe_context_window == int(4096 * 0.80)

    def test_safe_context_applies_derating_factor(self):
        result = _make_hw(context_window_reported=10000)
        _compute_safe_context(result, advertised_context_window=10000, advertised_max_output_tokens=2500)
        assert result.safe_context_window == int(10000 * 0.80)
        assert result.safe_output_tokens == int(10000 * 0.80 * 0.25)

    def test_context_estimate_confidence_is_estimated_not_measured(self):
        hw = _make_hw(context_window_reported=8192)
        est = estimate_safe_context(hw, advertised_context_window=8192)
        assert est.confidence == "estimated"
        assert est.method == "conservative_formula"
        assert est.safe_tokens == int(8192 * 0.80)

    def test_safe_output_tokens_capped_at_25pct_of_context(self):
        result = _make_hw(context_window_reported=8192)
        _compute_safe_context(result, advertised_context_window=8192, advertised_max_output_tokens=99999)
        # Output should be capped at 0.25 * safe_context
        expected = int(8192 * 0.80 * 0.25)
        assert result.safe_output_tokens == expected
