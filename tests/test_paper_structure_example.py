"""Regression checks for the synthetic structure-review example.

These checks validate the saved artifacts, not scientific correctness or the
actual origin of the claimed execution mode.
"""
import hashlib
import json
import re
import unittest
from pathlib import Path

from ai4science.contracts import ExecutionRequest
from ai4science.paper_structure_validation import validate_structure_run


ROOT = Path(__file__).resolve().parents[1] / 'workspace'
FIXTURE = ROOT / 'paper-structure-v0.1-fixture'
RUN = FIXTURE / 'run-01'
SOURCE = FIXTURE / 'manuscript.md'
EXPECTED_SOURCE_HASH = 'd492389a525752fc3b5aa0dc3e42dac3f92d69be71c87c2a02d6d8c458480845'


class SyntheticStructureExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = ExecutionRequest.from_dict(json.loads((RUN / 'execution_request.json').read_text(encoding='utf-8')))
        cls.plan = json.loads((RUN / 'restructuring_plan.json').read_text(encoding='utf-8'))
        cls.report = (RUN / 'structure_report.md').read_text(encoding='utf-8')
        cls.argument_map = (RUN / 'argument_map.md').read_text(encoding='utf-8')

    def test_request_hash_and_three_outputs(self):
        before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        self.assertEqual(EXPECTED_SOURCE_HASH, before)
        self.request.validate(ROOT)
        self.assertEqual(1, len(self.request.task.input_artifacts))
        self.assertEqual(EXPECTED_SOURCE_HASH, self.request.task.input_artifacts[0].sha256)
        self.assertEqual(self.request.task.task_id, self.plan['task_id'])
        self.assertEqual({'structure_report.md', 'argument_map.md', 'restructuring_plan.json'},
                         {Path(path).name for path in self.request.task.output_artifacts})
        for path in self.request.task.output_artifacts:
            self.assertTrue((ROOT / path).is_file())
            self.assertGreater((ROOT / path).stat().st_size, 0)
        errors = validate_structure_run(ROOT, self.request.task.input_artifacts[0].path,
                                        'paper-structure-v0.1-fixture/run-01/restructuring_plan.json')
        self.assertEqual([], errors)
        self.assertEqual(before, hashlib.sha256(SOURCE.read_bytes()).hexdigest())

    def test_every_body_paragraph_has_all_six_review_dimensions(self):
        lines = SOURCE.read_text(encoding='utf-8').splitlines()
        # A prose block is a consecutive run of nonblank, non-heading lines.
        paragraphs = []
        for number, line in enumerate(lines, 1):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            if number > 1 and lines[number - 2].strip() and not lines[number - 2].lstrip().startswith('#'):
                paragraphs[-1] = (paragraphs[-1][0], number)
            else:
                paragraphs.append((number, number))
        self.assertEqual(12, len(paragraphs))
        paragraph_section = self.report.split('## 段落审查', 1)[1].split('## 按优先级', 1)[0]
        rows = {}
        for line in paragraph_section.splitlines():
            if not line.startswith('|'):
                continue
            cells = [cell.strip() for cell in line.strip('|').split('|')]
            match = re.search(r'第\s*(\d+)\s*行', cells[0])
            if not match:
                continue
            number = int(match.group(1))
            self.assertNotIn(number, rows)
            self.assertEqual(8, len(cells), f'paragraph {number} should have location, six dimensions, and action')
            self.assertTrue(all(cells[1:7]), f'paragraph {number} has an empty review dimension')
            self.assertTrue(cells[7], f'paragraph {number} has no action')
            rows[number] = cells
        self.assertEqual({start for start, _ in paragraphs}, set(rows))
        self.assertTrue(all(start == end for start, end in paragraphs), 'fixture paragraph parser expects one-line prose blocks')

    def test_expected_findings_and_approval(self):
        by_line = {f['location']['start_line']: f for f in self.plan['findings']}
        for line in (11, 15, 19, 23, 25, 27, 31, 39):
            with self.subTest(line=line):
                self.assertIn(line, by_line)
                self.assertTrue(by_line[line]['recommendation'].strip())
        for line in (25, 27):
            self.assertEqual('merge', by_line[line]['action'])
        for line in (31, 39):
            self.assertIs(by_line[line]['may_change_scientific_meaning'], True)
            self.assertIs(by_line[line]['author_approval_required'], True)
        self.assertEqual('keep', by_line[35]['action'])
        for finding in self.plan['findings']:
            self.assertRegex(self.report, rf'\b{re.escape(finding["id"])}\b')
        self.assertTrue(self.argument_map.strip())


if __name__ == '__main__':
    unittest.main()
