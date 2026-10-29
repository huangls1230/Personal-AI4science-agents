import json
import tempfile
import unittest
from pathlib import Path

from ai4science.citation_links import (apply_status_transition, get_reading_status,
    link_reading_card, propose_status_transition, save_link_record, _card_frontmatter)
from ai4science.contracts import ExecutionResult, UsageMetrics, create_artifact
from ai4science.reading_output import render_reading_card, save_reading_outputs


class CitationLinkTests(unittest.TestCase):
    def test_custom_yaml_fields_do_not_prevent_reading_managed_identity(self):
        frontmatter = '---\ntags:\n  - custom\nextra:\n  nested: value\nzotero_item_key: "ABCD1234"\ncitekey: null\ndoi: "10.1234/example"\n---\n'
        values = _card_frontmatter(frontmatter)
        self.assertEqual(values['zotero_item_key'], 'ABCD1234')
        self.assertEqual(values['doi'], '10.1234/example')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            _card_frontmatter(frontmatter.replace('citekey: null', 'zotero_item_key: "OTHER123"'))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'source.pdf').write_bytes(b'%PDF-1.4\nexample')
        source = create_artifact(self.root, 'source.pdf')
        usage = UsageMetrics()
        self.reading = {
            'schema_version': '1.0', 'task_id': 'read-1', 'paper_id': source.sha256,
            'zotero_item_key': 'ABCD1234', 'source_document': source.to_dict(),
            'document_hash': source.sha256, 'reading_mode': 'deep',
            'evidence_scope': 'partial_text', 'analysis_status': 'draft',
            'reading_card_path': 'notes/reading_card.md', 'evidence_references': [],
            'limitations': [], 'unresolved_questions': [], 'suggested_next_actions': [],
            'suggested_zotero_status': None, 'usage_metrics': usage.to_dict(),
            'execution': ExecutionResult(task_id='read-1', executor='reading_cli',
                                         status='completed', usage_metrics=usage).to_dict(),
            'citation_handoff': None, 'claim_evidence': [],
        }
        card = render_reading_card({'title': 'Test paper', 'zotero_item_key': 'ABCD1234'},
                                   {'Personal Notes': 'Keep this text'})
        _, self.result_ref = save_reading_outputs(self.root, 'notes', self.reading, card)
        self.reading = json.loads((self.root / self.result_ref['path']).read_text())

    def tearDown(self):
        self.temp.cleanup()

    def test_status_dry_run_preserves_other_tags(self):
        tags = [{'tag': 'personal', 'type': 1}, {'tag': 'research-reading', 'type': 0}]
        plan = propose_status_transition(123, 'ABCD1234', 5, tags, 'research-deepread')
        self.assertEqual(get_reading_status(tags), 'research-reading')
        self.assertEqual(plan['after_tags'], [{'tag': 'personal', 'type': 1}, {'tag': 'research-deepread'}])
        self.assertEqual(tags[1]['tag'], 'research-reading')
        self.assertTrue(plan['requires_user_approval'])
        self.assertFalse(plan['applied'])
        self.assertFalse(plan['identity_scope_complete'])

    def test_status_conflict_and_verified_confirmation(self):
        with self.assertRaisesRegex(ValueError, 'multiple'):
            get_reading_status(['research-unread', 'research-reading'])
        with self.assertRaisesRegex(ValueError, 'confirmation'):
            propose_status_transition('1', 'ABCD1234', 2, [], 'research-verified')
        plan = propose_status_transition('1', 'ABCD1234', 2, [], 'research-verified',
                                         user_understanding_confirmed=True)
        self.assertFalse(plan['applied'])
        self.assertEqual(apply_status_transition(plan, user_approved=True, current_version=2)['status'], 'blocked')

    def test_status_write_unapproved_or_version_conflict_blocked(self):
        plan = propose_status_transition('1', 'ABCD1234', 2, [], 'research-reading')
        self.assertIn('approval', apply_status_transition(plan)['reason'])
        self.assertIn('version', apply_status_transition(plan, user_approved=True, current_version=3)['reason'])
        self.assertIn('not implemented', apply_status_transition(plan, user_approved=True, current_version=2)['reason'])

    def test_reading_link_save_and_no_note_overwrite(self):
        card = self.root / 'notes/reading_card.md'
        before = card.read_bytes()
        mapping = link_reading_card(self.root, self.reading, library_id='42', item_key='ABCD1234')
        self.assertEqual(mapping['reading_card']['path'], 'notes/reading_card.md')
        self.assertEqual(mapping['zotero_library_id'], '42')
        self.assertFalse(mapping['identity_scope_complete'])
        scoped = link_reading_card(self.root, self.reading, library_id='42', item_key='ABCD1234',
                                   library_kind='users', server_id='server-one')
        self.assertTrue(scoped['identity_scope_complete'])
        self.assertEqual(scoped['zotero_library_kind'], 'users')
        self.assertEqual(scoped['zotero_server_id'], 'server-one')
        # A complete target scope does not establish the source card's library.
        for candidate in (mapping, scoped):
            self.assertEqual(candidate['link_status'], 'requires_review')
            self.assertFalse(candidate['source_identity_verified'])
            self.assertIn('does not identify', candidate['link_review_reason'])
        self.assertNotIn('obsidian_note_path', mapping)
        self.assertNotIn('vault_status', mapping)
        ref = save_link_record(self.root, 'notes/link.json', mapping)
        self.assertEqual(json.loads((self.root / ref['path']).read_text()), mapping)
        with self.assertRaises(FileExistsError):
            save_link_record(self.root, 'notes/link.json', mapping)
        self.assertEqual(card.read_bytes(), before)
        with self.assertRaises(ValueError):
            save_link_record(self.root, '../escape.json', mapping)

    def test_link_rejects_mismatched_identity_and_changed_note(self):
        with self.assertRaisesRegex(ValueError, 'item key'):
            link_reading_card(self.root, self.reading, library_id='42', item_key='OTHER123')
        (self.root / 'notes/reading_card.md').write_text('user edited content')
        with self.assertRaisesRegex(ValueError, 'hash'):
            link_reading_card(self.root, self.reading, library_id='42', item_key='ABCD1234')
        self.assertEqual((self.root / 'notes/reading_card.md').read_text(), 'user edited content')


if __name__ == '__main__':
    unittest.main()
