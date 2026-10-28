import json
import tempfile
import unittest
from pathlib import Path

from ai4science.contracts import (ArtifactReference, EvidenceReference, ExecutionRequest,
    ExecutionResult, ExecutorCapabilities, ResearchTask, UsageMetrics, create_artifact,
    validate_transition, validate_workspace_path)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'paper.txt').write_text('actual evidence', encoding='utf8')
        self.artifact = create_artifact(self.root, 'paper.txt')

    def test_roundtrip_and_validation(self):
        task = ResearchTask('t1', 'Inspect paper', 'literature', input_artifacts=(self.artifact,), output_artifacts=('result.txt',))
        req = ExecutionRequest(task, 'mock')
        req.validate(self.root)
        parsed = ExecutionRequest.from_dict(json.loads(json.dumps(req.to_dict())))
        self.assertEqual(parsed.to_dict(), req.to_dict())
        result = ExecutionResult('t1', 'mock', 'completed', evidence=(EvidenceReference(self.artifact, 'source', 'p. 1'),))
        result.validate(self.root)
        self.assertEqual(ExecutionResult.from_dict(json.loads(json.dumps(result.to_dict()))).to_dict(), result.to_dict())

    def test_reject_invalid_payloads(self):
        for data in ({'schema_version': '1.0', 'task_id':'t', 'objective':' ', 'task_type':'a'},
                     {'schema_version':'2.0', 'task_id':'t', 'objective':'x', 'task_type':'a'},
                     {'task_id':'t', 'objective':'x', 'task_type':'a'},
                     {'schema_version':'1.0', 'task_id':'t', 'objective':'x', 'task_type':'a','extra':1},
                     {'schema_version':'1.0', 'task_id':'t', 'objective':'x', 'task_type':'a','required_capabilities':'read'}):
            with self.subTest(data=data), self.assertRaises(ValueError): ResearchTask.from_dict(data)
        with self.assertRaises(ValueError): ExecutorCapabilities('external', available=True, implemented=False)
        with self.assertRaises(ValueError): ExecutionResult('t', 'mock', 'completed', errors=('failure',))
        with self.assertRaises(ValueError): ExecutionResult('t', 'mock', 'failed', quality_status='passed')
        with self.assertRaises(ValueError): UsageMetrics(input_tokens=10)

    def test_paths_hashes_and_symlinks(self):
        for path in ('../bad', '/etc/passwd', 'C:/bad', 'a/../bad', 'a\\b', 'a//b'):
            with self.subTest(path=path), self.assertRaises(ValueError): validate_workspace_path(self.root, path)
        with tempfile.TemporaryDirectory() as elsewhere:
            (self.root/'link').symlink_to(elsewhere, target_is_directory=True)
            with self.assertRaises(ValueError): validate_workspace_path(self.root, 'link/data.txt')
        (self.root/'paper.txt').write_text('modified')
        with self.assertRaises(ValueError): ResearchTask('t','x','a',input_artifacts=(self.artifact,)).validate(self.root)

    def test_state_and_retry(self):
        validate_transition('pending', 'running')
        validate_transition('running', 'completed')
        with self.assertRaises(ValueError): validate_transition('failed', 'completed')
        task = ResearchTask('t', 'x', 'test')
        with self.assertRaises(ValueError): ExecutionRequest(task, 'mock', attempt=2)
        ExecutionRequest(ResearchTask('t','x','test',idempotency_key='key'), 'mock', attempt=2)


if __name__ == '__main__':
    unittest.main()
