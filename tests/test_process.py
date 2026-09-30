import signal
import unittest
from unittest.mock import Mock, call, patch

from ai_topics_codex.process import stop


class ProcessTest(unittest.TestCase):
    def test_reaps_leader_but_still_signals_surviving_group(self):
        events = Mock()
        proc = Mock(pid=123, **{"poll.return_value": 0})
        events.attach_mock(proc, "proc")
        with patch("ai_topics_codex.process.os.killpg") as kill:
            events.attach_mock(kill, "kill")
            stop(proc)
        self.assertEqual(events.mock_calls, [
            call.proc.poll(), call.kill(123, signal.SIGTERM),
            call.proc.wait(timeout=2), call.kill(123, signal.SIGKILL),
        ])

    def test_permission_failure_is_not_hidden(self):
        with patch("ai_topics_codex.process.os.killpg", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                stop(Mock(pid=123))
