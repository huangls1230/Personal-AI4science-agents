import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ai4science.terminology_inventory import count_terms


class TerminologyInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.text = ('# Intro\nAgent agent AgentX.\n'
                     '## 方法\n多智能体 A+B A+B\n'
                     '```text\n# Not a heading\nAgent\n```\n'
                     'Results\n-------\nAgent\n')
        (self.root / 'draft.md').write_text(self.text, encoding='utf-8')

    def test_literal_count_context_and_headings(self):
        result = count_terms(self.root, 'draft.md', ['Agent', 'agent', 'A+B', '多智能体', 'Agent', 'missing'])
        self.assertEqual(result['input']['sha256'], hashlib.sha256(self.text.encode()).hexdigest())
        entries = {entry['term']: entry for entry in result['terms']}
        self.assertEqual(list(entries), ['Agent', 'agent', 'A+B', '多智能体', 'missing'])
        self.assertEqual(entries['Agent']['count'], 4)  # substring in AgentX is intentional
        self.assertEqual([o['line'] for o in entries['Agent']['occurrences']], [2, 2, 7, 11])
        self.assertEqual([o['heading'] for o in entries['Agent']['occurrences']], ['Intro', 'Intro', '方法', 'Results'])
        self.assertEqual(entries['A+B']['count'], 2)
        self.assertEqual([o['column'] for o in entries['A+B']['occurrences']], [6, 10])
        self.assertEqual(entries['多智能体']['occurrences'][0]['context'], '多智能体 A+B A+B')
        self.assertEqual(entries['agent']['count'], 1)
        self.assertEqual(entries['missing']['occurrences'], [])

    def test_nonoverlapping_and_independent_terms(self):
        (self.root / 'draft.md').write_text('aaaa\n', encoding='utf-8')
        entries = count_terms(self.root, 'draft.md', ['aa', 'aaa'])['terms']
        self.assertEqual([entry['count'] for entry in entries], [2, 1])

    def test_invalid_terms(self):
        for terms in ([], [''], ['  '], ['a\nb'], [None], 'Agent'):
            with self.subTest(terms=terms), self.assertRaises(ValueError):
                count_terms(self.root, 'draft.md', terms)

    def test_paths_outside_workspace_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            secret = Path(outside) / 'secret.md'
            secret.write_text('private', encoding='utf-8')
            (self.root / 'escape.md').symlink_to(secret)
            for name in ('../secret.md', str(secret), 'escape.md'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    count_terms(self.root, name, ['private'])

    def test_cli_outputs_json_without_modifying_source(self):
        env = dict(os.environ)
        env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'src')
        result = subprocess.run([sys.executable, '-m', 'ai4science.terminology_inventory',
                                 '--workspace', str(self.root), '--input', 'draft.md',
                                 '--term', 'Agent', '--term', 'A+B'],
                                env=env, text=True, capture_output=True, check=True)
        parsed = json.loads(result.stdout)
        self.assertEqual([x['count'] for x in parsed['terms']], [4, 2])
        self.assertEqual((self.root / 'draft.md').read_text(encoding='utf-8'), self.text)


if __name__ == '__main__':
    unittest.main()
