"""Tests for BATCH-190: Notification Gateway.

AIV §13: Tests verify behavior (notifications dispatched, errors handled)."""

import asyncio

from backend.pipeline.notifications.gateway import (
    CompositeNotifier,
    ConsoleNotifier,
    Notification,
    NotificationGateway,
    PipelineEvent,
    create_notifier,
)


class TestNotification:
    """Notification dataclass serializes correctly."""

    def test_01_to_dict(self):
        n = Notification(
            event=PipelineEvent.RUN_COMPLETED,
            run_id="run_123",
            strategy="deep_research",
            domain="MoE Routing",
            message="Pipeline completed: 5 gaps, 2 ideas",
            data={"elapsed_seconds": 900},
        )
        d = n.to_dict()
        assert d["event"] == "run_completed"
        assert d["run_id"] == "run_123"
        assert d["data"]["elapsed_seconds"] == 900

    def test_02_event_enum_values(self):
        assert PipelineEvent.RUN_STARTED.value == "run_started"
        assert PipelineEvent.RUN_FAILED.value == "run_failed"
        assert PipelineEvent.DOOM_DETECTED.value == "doom_detected"


class TestConsoleNotifier:
    """ConsoleNotifier always succeeds."""

    def test_03_always_succeeds(self):
        async def _run():
            notifier = ConsoleNotifier()
            n = Notification(
                event=PipelineEvent.RUN_STARTED,
                run_id="run_1",
                strategy="fast_scan",
                domain="Test",
                message="Started",
            )
            result = await notifier.send(n)
            assert result is True
        asyncio.run(_run())

    def test_04_failure_event_succeeds(self):
        async def _run():
            notifier = ConsoleNotifier()
            n = Notification(
                event=PipelineEvent.RUN_FAILED,
                run_id="run_1",
                strategy="deep_research",
                domain="Test",
                message="Stage gap_analysis failed: timeout",
            )
            result = await notifier.send(n)
            assert result is True
        asyncio.run(_run())


class TestCompositeNotifier:
    """CompositeNotifier dispatches to all notifiers."""

    def test_05_all_succeed(self):
        async def _run():
            notifier = CompositeNotifier([ConsoleNotifier(), ConsoleNotifier()])
            n = Notification(
                event=PipelineEvent.RUN_COMPLETED,
                run_id="run_2",
                strategy="fast_scan",
                domain="AI",
                message="Done",
            )
            result = await notifier.send(n)
            assert result is True
        asyncio.run(_run())

    def test_06_one_fails_still_ok(self):
        """If one notifier fails, composite still returns True if any succeed."""
        async def _run():
            class FailingNotifier(NotificationGateway):
                async def send(self, notification):
                    raise RuntimeError("Failed")

            notifier = CompositeNotifier([FailingNotifier(), ConsoleNotifier()])
            n = Notification(
                event=PipelineEvent.RUN_COMPLETED,
                run_id="run_3",
                strategy="fast_scan",
                domain="AI",
                message="Done",
            )
            result = await notifier.send(n)
            assert result is True
        asyncio.run(_run())


class TestCreateNotifier:
    """Factory creates correct notifier types."""

    def test_07_no_webhook_console_only(self):
        notifier = create_notifier(webhook_url=None)
        assert isinstance(notifier, ConsoleNotifier)

    def test_08_with_webhook_composite(self):
        notifier = create_notifier(webhook_url="https://example.com/webhook")
        assert isinstance(notifier, CompositeNotifier)
