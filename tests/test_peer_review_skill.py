"""Offline safety tests of the installed peer-review skill in a simulated project.

Each test copies the installed package to a new temporary .agents/skills layout.
Synthetic local-only intake tests exercise deterministic CLI behavior only; they
are not evidence that a hosted assistant's manuscript processing is local.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


INSTALLED = Path(__file__).resolve().parents[1] / '.agents/skills/peer-review'


class PeerReviewSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='peer-review-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'project'
        self.skill = self.root / '.agents/skills/peer-review'
        self.skill.parent.mkdir(parents=True)
        shutil.copytree(INSTALLED, self.skill, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        self.workspace = self.root / 'workspace'
        self.workspace.mkdir()
        (self.workspace / 'ok.md').write_text('# Synthetic review\n', encoding='utf-8')
        (self.root / 'secret.md').write_text('outside workspace', encoding='utf-8')
        (self.base / 'external.md').write_text('outside project', encoding='utf-8')

    def cli(self, script, *arguments):
        return subprocess.run(
            [sys.executable, str(self.skill / 'scripts' / script), *map(str, arguments)],
            cwd=self.root, capture_output=True, text=True, check=False,
        )

    def synthetic_local_intake(self):
        intake = json.loads((self.skill / 'assets/review_intake_template.json').read_text())
        intake['material']['status'] = 'synthetic'
        intake['authorization'].update(basis='synthetic_training', documented=True,
                                       local_processing_authorized=True)
        intake['reviewer'].update(human_accountable=True, conflict_status='none_identified')
        intake['venue_policy'].update(checked=True, peer_review_model='open')
        intake['handling']['deletion_or_retention_record_planned'] = True
        return intake

    def write_intake(self, name, intake):
        path = self.workspace / name
        path.write_text(json.dumps(intake), encoding='utf-8')
        return path

    def test_workspace_read_and_json_output(self):
        output = self.workspace / 'report.json'
        result = self.cli('lint_review.py', self.workspace / 'ok.md', '-o', output)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        self.assertTrue(output.is_file())
        self.assertIsInstance(json.loads(output.read_text()), dict)
        self.assertEqual((self.workspace / 'ok.md').read_text(), '# Synthetic review\n')

    def test_rejects_outside_and_traversal_inputs(self):
        for path in (self.base / 'external.md', self.root / 'secret.md',
                     'workspace/../secret.md'):
            with self.subTest(path=str(path)):
                result = self.cli('lint_review.py', path)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, '')

    def test_rejects_symlink_and_hardlink_inputs(self):
        parent = self.workspace / 'linked_parent'
        leaf = self.workspace / 'linked.md'
        hard = self.workspace / 'hard.md'
        parent.symlink_to(self.root, target_is_directory=True)
        leaf.symlink_to(self.root / 'secret.md')
        os.link(self.root / 'secret.md', hard)
        for path in (parent / 'secret.md', leaf, hard):
            with self.subTest(path=path):
                result = self.cli('lint_review.py', path)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, '')

    def test_rejects_existing_force_and_unsafe_output(self):
        intake = self.write_intake('intake.json', self.synthetic_local_intake())
        existing = self.workspace / 'existing.json'
        existing.write_text('preserve', encoding='utf-8')
        parent = self.workspace / 'linked_parent'
        parent.symlink_to(self.root, target_is_directory=True)
        leaf = self.workspace / 'linked.json'
        leaf.symlink_to(existing)
        for output, force in ((existing, False), (existing, True),
                              (self.root / 'outside.json', False),
                              (self.base / 'outside.json', False),
                              (parent / 'output.json', False), (leaf, False)):
            with self.subTest(output=output, force=force):
                args = [intake, '-o', output]
                if force:
                    args.append('--force')
                result = self.cli('validate_review_intake.py', *args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(existing.read_text(), 'preserve')
        result = self.cli('validate_review_intake.py', intake, '--force')
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_catalog_asset_with_real_selector(self):
        profile = self.workspace / 'profile.json'
        shutil.copyfile(self.skill / 'assets/study_profile_template.json', profile)
        result = self.cli('select_reporting_guidelines.py', profile)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsInstance(json.loads(result.stdout), dict)

    def test_scaffold_asset_with_synthetic_local_controls(self):
        # Local-only flags here describe only this deterministic CLI test,
        # not the handling of a manuscript by a hosted assistant.
        intake = self.write_intake('intake.json', self.synthetic_local_intake())
        result = self.cli('generate_review_scaffold.py', intake, '-o',
                          self.workspace / 'scaffold.md')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.workspace / 'scaffold.md').read_text().strip())

    def test_non_allowlisted_skill_asset_is_not_a_script_input(self):
        result = self.cli('validate_review_intake.py',
                          self.skill / 'assets/review_intake_template.json')
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_template_is_blocked_and_honest_hosted_use_is_blocked(self):
        template = json.loads((self.skill / 'assets/review_intake_template.json').read_text())
        result = self.cli('validate_review_intake.py', self.write_intake('template.json', template))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'BLOCKED')
        hosted = copy.deepcopy(self.synthetic_local_intake())
        hosted['handling'].update(local_only=False, external_service_use=True)
        hosted['authorization']['external_processing_authorized'] = True
        result = self.cli('validate_review_intake.py', self.write_intake('hosted.json', hosted))
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'BLOCKED')
        self.assertTrue({'LOCAL_ONLY_REQUIRED', 'EXTERNAL_SERVICE_NOT_SUPPORTED'} <=
                        {error['code'] for error in report['errors']})


if __name__ == '__main__':
    unittest.main()
