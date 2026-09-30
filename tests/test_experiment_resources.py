from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.resources import (
    POWER_SOURCE_NOTE,
    CpuTimes,
    ResourceSampler,
    cpu_percent,
    parse_process_cpu_ticks,
    parse_system_cpu_times,
    read_pi_temperature,
    read_process_memory,
)


def process_stat(pid: int, utime: int, stime: int) -> str:
    # Field 3 is state. Ten fields follow before fields 14/15 (utime/stime).
    remaining = ["S"] + ["0"] * 10 + [str(utime), str(stime)]
    return f"{pid} (refound worker (camera)) {' '.join(remaining)}\n"


class ResourceParsingTests(unittest.TestCase):
    def test_system_cpu_parser_and_delta(self) -> None:
        first = parse_system_cpu_times("cpu  100 0 50 850 0 0 0 0 0 0\n")
        second = parse_system_cpu_times("cpu  115 0 60 925 0 0 0 0 0 0\n")

        self.assertEqual(first, CpuTimes(total=1000, idle=850))
        self.assertEqual(second, CpuTimes(total=1100, idle=925))
        self.assertEqual(cpu_percent(first, second), 25.0)
        self.assertIsNone(cpu_percent(second, first))

    def test_process_stat_parser_handles_parentheses_and_spaces(self) -> None:
        self.assertEqual(parse_process_cpu_ticks(process_stat(41, 120, 30)), 150)
        self.assertIsNone(parse_process_cpu_ticks("malformed"))

    def test_memory_and_temperature_parsers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            process_dir = root / "proc" / "41"
            process_dir.mkdir(parents=True)
            (process_dir / "status").write_text(
                "Name:\tpython\nVmHWM:\t30720 kB\nVmRSS:\t20480 kB\n",
                encoding="utf-8",
            )
            zone = root / "sys" / "class" / "thermal" / "thermal_zone0"
            zone.mkdir(parents=True)
            (zone / "type").write_text("cpu-thermal\n", encoding="utf-8")
            (zone / "temp").write_text("48750\n", encoding="utf-8")

            self.assertEqual(read_process_memory(41, root / "proc"), (20.0, 30.0))
            self.assertEqual(
                read_pi_temperature(root / "sys"),
                (48.75, "sysfs:cpu-thermal"),
            )


class ResourceSamplerTests(unittest.TestCase):
    def make_pi_fixture(self, root: Path, pid: int = 41) -> tuple[Path, Path]:
        proc_root = root / "proc"
        sys_root = root / "sys"
        process_dir = proc_root / str(pid)
        process_dir.mkdir(parents=True)
        (proc_root / "device-tree").mkdir()
        (proc_root / "device-tree" / "model").write_bytes(
            b"Raspberry Pi 4 Model B Rev 1.5\x00"
        )
        (proc_root / "stat").write_text(
            "cpu 100 0 50 850 0 0 0 0 0 0\n", encoding="utf-8"
        )
        (proc_root / "loadavg").write_text("0.25 0.50 0.75 1/100 41\n", encoding="utf-8")
        (proc_root / "meminfo").write_text(
            "MemTotal: 2048000 kB\nMemAvailable: 1024000 kB\n", encoding="utf-8"
        )
        (process_dir / "stat").write_text(process_stat(pid, 20, 10), encoding="utf-8")
        (process_dir / "status").write_text(
            "VmRSS: 20480 kB\nVmHWM: 30720 kB\n", encoding="utf-8"
        )
        zone = sys_root / "class" / "thermal" / "thermal_zone0"
        zone.mkdir(parents=True)
        (zone / "type").write_text("cpu-thermal\n", encoding="utf-8")
        (zone / "temp").write_text("50000\n", encoding="utf-8")
        return proc_root, sys_root

    def test_pi_sample_uses_counter_deltas_and_never_infers_power(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            proc_root, sys_root = self.make_pi_fixture(root)
            sampler = ResourceSampler(
                41,
                root,
                proc_root=proc_root,
                sys_root=sys_root,
                clock_ticks_per_second=100,
                cpu_count=4,
                started_monotonic=10.0,
            )

            first = sampler.sample(now_monotonic=10.0, timestamp_utc="2026-01-01T00:00:00Z")
            self.assertIsNone(first.system_cpu_percent)
            self.assertIsNone(first.process_cpu_percent)

            (proc_root / "stat").write_text(
                "cpu 115 0 60 925 0 0 0 0 0 0\n", encoding="utf-8"
            )
            (proc_root / "41" / "stat").write_text(
                process_stat(41, 24, 11), encoding="utf-8"
            )
            second = sampler.sample(
                now_monotonic=11.0,
                timestamp_utc="2026-01-01T00:00:01Z",
            )

            self.assertTrue(second.raspberry_pi)
            self.assertTrue(second.process_alive)
            self.assertEqual(second.system_cpu_percent, 25.0)
            self.assertEqual(second.process_cpu_percent, 5.0)
            self.assertEqual(second.process_cpu_percent_of_device, 1.25)
            self.assertEqual(second.rss_mib, 20.0)
            self.assertEqual(second.peak_rss_mib, 30.0)
            self.assertEqual(second.load_1m, 0.25)
            self.assertEqual(second.memory_available_mib, 1000.0)
            self.assertEqual(second.temperature_c, 50.0)
            self.assertIsNotNone(second.disk_used_percent)
            self.assertIsNone(second.power_w)
            self.assertEqual(second.power_source, POWER_SOURCE_NOTE)

    def test_missing_non_pi_metrics_are_empty_in_csv_row(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            proc_root = root / "missing-proc"
            sys_root = root / "missing-sys"
            sampler = ResourceSampler(
                999,
                root,
                proc_root=proc_root,
                sys_root=sys_root,
                started_monotonic=1.0,
            )

            sample = sampler.sample(now_monotonic=2.0, timestamp_utc="fixed")
            row = sample.to_csv_row()

            self.assertFalse(sample.raspberry_pi)
            self.assertFalse(sample.process_alive)
            self.assertEqual(row["system_cpu_percent"], "")
            self.assertEqual(row["rss_mib"], "")
            self.assertEqual(row["temperature_c"], "")
            self.assertEqual(row["power_w"], "")
            self.assertEqual(row["process_alive"], 0)
            # Disk capacity remains available through the Python standard library.
            self.assertNotEqual(row["disk_free_gib"], "")

    def test_pid_change_resets_only_process_cpu_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            proc_root, sys_root = self.make_pi_fixture(root)
            sampler = ResourceSampler(
                41,
                root,
                proc_root=proc_root,
                sys_root=sys_root,
                clock_ticks_per_second=100,
                started_monotonic=0.0,
            )
            sampler.sample(now_monotonic=1.0, timestamp_utc="first")

            new_process = proc_root / "42"
            new_process.mkdir()
            (new_process / "stat").write_text(process_stat(42, 100, 20), encoding="utf-8")
            (new_process / "status").write_text("VmRSS: 10240 kB\n", encoding="utf-8")
            sampler.set_pid(42)
            sample = sampler.sample(now_monotonic=2.0, timestamp_utc="second")

            self.assertEqual(sample.pid, 42)
            self.assertTrue(sample.process_alive)
            self.assertIsNone(sample.process_cpu_percent)


if __name__ == "__main__":
    unittest.main()
