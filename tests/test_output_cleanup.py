"""Tests for generated output cleanup."""
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from output_cleanup import cleanup_previous_day_outputs


class TestOutputCleanup(unittest.TestCase):
    def test_cleanup_removes_only_previous_day_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            old_file = output_dir / "old.pptx"
            today_file = output_dir / "today.mp4"
            ignored_file = output_dir / "keep.txt"

            old_file.write_text("old")
            today_file.write_text("today")
            ignored_file.write_text("ignored")

            yesterday = datetime.now() - timedelta(days=1)
            old_timestamp = yesterday.timestamp()
            os.utime(old_file, (old_timestamp, old_timestamp))

            with patch("output_cleanup.OUTPUT_CLEANUP_DIRS", [tmpdir]):
                deleted = cleanup_previous_day_outputs(today=date.today())

            self.assertEqual(deleted, 1)
            self.assertFalse(old_file.exists())
            self.assertTrue(today_file.exists())
            self.assertTrue(ignored_file.exists())


if __name__ == "__main__":
    unittest.main()
