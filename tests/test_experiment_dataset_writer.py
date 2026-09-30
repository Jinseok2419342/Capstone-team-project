from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.csvio import read_episodes, read_events, write_dataset
from experiments.schema import EpisodeRecord


class ExperimentDatasetWriterTests(unittest.TestCase):
    def test_writes_header_only_events_and_refuses_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episodes_path = root / "episodes.csv"
            events_path = root / "events.csv"
            episode = EpisodeRecord(
                run_id="R1",
                episode_id="N1",
                started_at="2026-01-01T00:00:00Z",
                ended_at="2026-01-01T00:00:10Z",
                eligible_monitoring_seconds=10.0,
            )
            write_dataset(episodes_path, events_path, [episode], [])
            self.assertEqual(read_episodes(episodes_path), [episode])
            self.assertEqual(read_events(events_path), [])
            with self.assertRaises(FileExistsError):
                write_dataset(episodes_path, events_path, [episode], [])

    def test_requires_distinct_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.csv"
            with self.assertRaisesRegex(ValueError, "must be different"):
                write_dataset(path, path, [], [])


if __name__ == "__main__":
    unittest.main()
