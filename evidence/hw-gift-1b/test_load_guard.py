"""Fabricated process counters only; no host observation or real timing."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('gift1b_load_guard', Path(__file__).with_name('load_guard.py'))
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def process(pid=10, comm='python3', ticks=100, uid=1000):
    return dict(pid=pid, ppid=1, start_ticks=10, uid=uid, comm=comm, state='S', ticks=ticks)


class LoadTests(unittest.TestCase):
    def test_foreign_one_tick_rejects_including_agent(self):
        before = {10: process(comm='2.1.284')}
        after = {10: process(comm='2.1.284', ticks=101)}
        self.assertEqual(len(guard.classify(before, after, set())[0]), 1)

    def test_idle_agent_does_not_make_busy(self):
        before = {10: process(comm='2.1.284')}
        self.assertEqual(guard.classify(before, before, set())[0], [])

    def test_sleeping_compiler_still_makes_busy(self):
        before = {10: process(comm='cc1')}
        self.assertEqual(len(guard.classify(before, before, set())[0]), 1)

    def test_system_ticks_are_recorded_separately(self):
        before = {10: process(comm='sshd', uid=0)}
        after = {10: process(comm='sshd', ticks=101, uid=0)}
        active, system = guard.classify(before, after, set())
        self.assertEqual(active, [])
        self.assertEqual(len(system), 1)

    def test_observer_is_excluded_but_other_pid_is_not(self):
        before = {10: process(), 20: process(pid=20)}
        after = {10: process(ticks=101), 20: process(pid=20, ticks=101)}
        self.assertEqual([p['pid'] for p in guard.classify(before, after, {10})[0]], [20])

    def test_busy_cannot_be_overridden_by_boolean(self):
        receipt = dict(hostname='ace-core', cpu='AMD EPYC 4344P', pinned_core=0,
                       governor='schedutil', interval_ns=2000000000,
                       other_load=dict(busy=False, active_processes=[], inspection_errors=[]))
        guard.require_idle(receipt)
        receipt['other_load']['active_processes'] = [process()]
        with self.assertRaises(guard.BusyHost):
            guard.require_idle(receipt)


if __name__ == '__main__':
    unittest.main()
