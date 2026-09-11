"""Eligibility and dispatch tests with an external codec; no benchmark invocation."""
import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from check_adapter import check
import test_check_adapter
from axis_planner import plan_adapter, dispatch_adapter
from resident_probe import AXES

class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name); self.adapter=self.root/'third_party.sh'; self.work=self.root/'build'
        self.helper=self.root/'helper.txt'; self.helper.write_text('version one')
        text=test_check_adapter.CheckContract.adapter_text(self)
        extra=f'''codec_inputs() {{ echo '["{self.helper}"]'; }}
codec_build() {{ mkdir -p "$HB_CHECK_WORK"; cp /bin/true "$HB_CHECK_WORK/tool"; }}
codec_build_artifacts() {{ printf '["%s/tool"]\\n' "$HB_CHECK_WORK"; }}
'''
        extra+="""codec_configuration() { python3 -c 'import json,os;print(json.dumps({"mode":os.environ.get("HB_TEST_PARAMETER","default")}))'; }
"""
        self.adapter.write_text(text.replace('if [[ "${BASH_SOURCE[0]}" != "$0" ]]',extra+'if [[ "${BASH_SOURCE[0]}" != "$0" ]]'))
        with contextlib.redirect_stdout(io.StringIO()): check(self.adapter,self.work)
    def tearDown(self): self.tmp.cleanup()
    def plan(self,axes=None): return plan_adapter(self.adapter,self.work,axes or sorted(AXES))
    def edit_receipt(self,fn):
        p=self.work/'check.json'; r=json.loads(p.read_text()); fn(r); p.write_text(json.dumps(r))
    def test_nine_axes_and_adapter_owned_reasons(self):
        p=self.plan(); self.assertEqual(len(p['tasks']),9)
        for task in p['tasks']:
            if task['axis']=='decode': self.assertEqual(task['action'],'schedule')
            else:
                self.assertEqual(task['action'],'skip')
                self.assertEqual(task['reason'],'not implemented by this CLI-only fixture')
    def test_supported_dispatch_and_no_unsupported_calls(self):
        p=self.plan(); good=Mock(return_value={'test_only':True}); bad=Mock(side_effect=AssertionError('unsupported handler invoked'))
        rows=dispatch_adapter(p,dict.fromkeys(AXES,bad)|{'decode':good})
        good.assert_called_once(); bad.assert_not_called()
        self.assertEqual(sum(r['value'] is None for r in rows),8)
    def test_missing_backend_blocks_instead_of_fabricating_na(self):
        with self.assertRaisesRegex(ValueError,'backend not connected'): dispatch_adapter(self.plan(),{})
    def test_changed_configuration_rejected_without_source_change(self):
        with patch.dict(os.environ,{'HB_TEST_PARAMETER':'different'}):
            with self.assertRaisesRegex(ValueError,'stale'): self.plan()
    def test_changed_adapter_rejected(self):
        with self.adapter.open('a') as f: f.write('\n# changed\n')
        with self.assertRaisesRegex(ValueError,'stale'): self.plan()
    def test_changed_declared_input_rejected(self):
        self.helper.write_text('version two')
        with self.assertRaisesRegex(ValueError,'stale'): self.plan()
    def test_changed_built_binary_rejected(self):
        with (self.work/'tool').open('ab') as f: f.write(b'changed')
        with self.assertRaisesRegex(ValueError,'stale'): self.plan()
    def test_old_receipt_rejected(self):
        self.edit_receipt(lambda r:r.pop('check_protocol'))
        with self.assertRaisesRegex(ValueError,'predates'): self.plan()
    def test_failed_receipt_rejected(self):
        self.edit_receipt(lambda r:r.update(status='failed'))
        with self.assertRaisesRegex(ValueError,'not successful'): self.plan()
    def test_missing_fixture_evidence_rejected(self):
        self.edit_receipt(lambda r:r.update(cases=[]))
        with self.assertRaisesRegex(ValueError,'incomplete'): self.plan()
    def test_modified_plan_rejected_before_handler(self):
        p=self.plan(); p['tasks'][0]['action']='schedule'; handler=Mock()
        with self.assertRaisesRegex(ValueError,'modified'): dispatch_adapter(p,dict.fromkeys(AXES,handler))
        handler.assert_not_called()
    def test_active_check_blocks_planning(self):
        with (self.work/'check.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError,'in progress'): self.plan()
    def test_unknown_axis_rejected(self):
        with self.assertRaisesRegex(ValueError,'unknown'): self.plan(['made_up'])
    def test_changed_state_during_dispatch_discards_output(self):
        def mutate(_): self.helper.write_text('new version'); return 1
        with self.assertRaisesRegex(ValueError,'stale|changed'):
            dispatch_adapter(self.plan(['decode']),{'decode':mutate})

if __name__=='__main__': unittest.main()
