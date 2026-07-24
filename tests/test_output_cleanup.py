"""Tests for generated output cleanup."""
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app.services.generation.cleanup_service import cleanup_old_generation_artifacts, cleanup_previous_day_outputs
from wsgi import create_app, db
from app.models import GenerationHistory


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

            with patch("app.services.generation.cleanup_service.OUTPUT_CLEANUP_DIRS", [tmpdir]):
                deleted = cleanup_previous_day_outputs(today=date.today())

            self.assertEqual(deleted, 1)
            self.assertFalse(old_file.exists())
            self.assertTrue(today_file.exists())
            self.assertTrue(ignored_file.exists())

    def test_cleanup_removes_old_generation_history_and_files(self):
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        try:
            app = create_app({
                'TESTING': True,
                'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
            })
            with app.app_context():
                db.create_all()
                with tempfile.TemporaryDirectory() as tmpdir:
                    output_dir = Path(tmpdir)
                    old_file = output_dir / "old.mp4"
                    recent_file = output_dir / "recent.mp4"
                    old_file.write_text("old")
                    recent_file.write_text("recent")

                    db.session.add(GenerationHistory(
                        filename="old.mp4",
                        product_count=1,
                        generated_at=datetime.utcnow() - timedelta(days=10),
                        file_path=str(old_file),
                        status="success",
                    ))
                    db.session.add(GenerationHistory(
                        filename="recent.mp4",
                        product_count=1,
                        generated_at=datetime.utcnow(),
                        file_path=str(recent_file),
                        status="success",
                    ))
                    db.session.commit()

                    with patch("app.services.generation.cleanup_service.OUTPUT_CLEANUP_DIRS", [tmpdir]):
                        summary = cleanup_old_generation_artifacts(days=7)

                    self.assertEqual(summary["deleted_history_rows"], 1)
                    self.assertFalse(old_file.exists())
                    self.assertTrue(recent_file.exists())
                    self.assertIsNone(GenerationHistory.query.filter_by(filename="old.mp4").first())
                    self.assertIsNotNone(GenerationHistory.query.filter_by(filename="recent.mp4").first())
        finally:
            os.close(db_fd)
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
