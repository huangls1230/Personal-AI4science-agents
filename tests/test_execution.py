import json
import tempfile
import unittest
from pathlib import Path

from ai4science.adapters import ScriptAdapter, MockExecutor, ExternalHarnessAdapter, CodexNativeAdapter
from ai4science.budget import BudgetExceeded, BudgetGuard, BudgetPolicy, UsageRecorder, policy_from_config
from ai4science.context import ContextManifest, ContextSelector
from ai4science.contracts import ExecutionRequest, ExecutorCapabilities, ResearchTask, create_artifact
from ai4science.models import ModelDescriptor, ModelRequest, MockModel
from ai4science.router import RoutingCandidate, candidates_from_config, route


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'input.txt').write_text('science', encoding='utf-8')
        self.ref = create_artifact(self.root, 'input.txt')
        self.task = ResearchTask('task-1', 'Hash verified source', 'sha256', ('sha256',),
                                 'deterministic', 'internal', input_artifacts=(self.ref,))

    def test_script_hash_and_budget_are_applied(self):
        guard = BudgetGuard(BudgetPolicy(max_executions=1, max_tokens=0, max_cost=0))
        adapter = ScriptAdapter(self.root, guard=guard)
        request = ExecutionRequest(self.task, 'script')
        result = adapter.execute(request)
        self.assertEqual(result.status, 'completed')
        self.assertIn(self.ref.sha256, result.summary)
        self.assertEqual(result.evidence[0].artifact.sha256, self.ref.sha256)
        self.assertIsNone(result.usage_metrics.input_tokens)
        self.assertEqual(result.usage_metrics.token_measurement, 'unknown')
        self.assertEqual(result.quality_status, 'not_reviewed')
        self.assertEqual(adapter.execute(request).status, 'blocked')

    def test_tampered_input_and_invalid_operation_fail(self):
        request = ExecutionRequest(self.task, 'script')
        (self.root / 'input.txt').write_text('modified', encoding='utf-8')
        self.assertEqual(ScriptAdapter(self.root).execute(request).status, 'failed')
        invalid = ResearchTask('bad', 'run arbitrary command', 'shell')
        self.assertEqual(ScriptAdapter(self.root).execute(ExecutionRequest(invalid, 'script')).status, 'failed')

    def test_mock_and_unimplemented_adapters(self):
        task = ResearchTask('mock-1', 'offline', 'mock', ('mock',))
        result = MockExecutor(self.root).execute(ExecutionRequest(task, 'mock'))
        self.assertEqual(result.status, 'completed')
        self.assertIsNone(result.usage_metrics.output_tokens)
        for adapter, name in ((ExternalHarnessAdapter(), 'external_harness'), (CodexNativeAdapter(), 'codex_native')):
            self.assertFalse(adapter.capabilities.available)
            self.assertFalse(adapter.capabilities.implemented)
            self.assertEqual(adapter.execute(ExecutionRequest(task, name)).status, 'blocked')

    def test_router_filters_capabilities_permissions_models(self):
        script = RoutingCandidate(ScriptAdapter.capabilities, 'script', token_upper_bound=0, cost_upper_bound=0)
        no_permission = ExecutorCapabilities('denied', ('sha256',), True, True, ('public',))
        unavailable_model = ModelDescriptor('missing', 'provider', None, available=False, implemented=False,
                                            allowed_sensitivities=('internal',))
        external = ExecutorCapabilities('test-external', ('sha256',), True, True, ('internal',), ('missing',))
        choices = [script, RoutingCandidate(no_permission, 'mock'),
                   RoutingCandidate(external, 'external_harness', model_id='missing')]
        decision = route(self.task, choices, [unavailable_model], BudgetPolicy())
        self.assertEqual((decision.status, decision.executor, decision.candidates), ('recommended', 'script', ('script',)))
        self.assertEqual(route(self.task, choices[1:], [unavailable_model], BudgetPolicy()).status, 'blocked')
        self.assertEqual(route(self.task, [script], [], BudgetPolicy(max_tokens=0, max_cost=0)).executor, 'script')

    def test_router_scores_and_budget_filter(self):
        caps_a = ExecutorCapabilities('a', ('mock',), True, True, ('public',))
        caps_b = ExecutorCapabilities('b', ('mock',), True, True, ('public',))
        task = ResearchTask('r', 'rank', 'mock', ('mock',))
        candidates = [RoutingCandidate(caps_a, 'mock', cost_score=0.9, quality_score=1),
                      RoutingCandidate(caps_b, 'mock', cost_score=0.1, quality_score=0.4)]
        self.assertEqual(route(task, candidates, [], BudgetPolicy(), preferences={'cost': 5, 'speed': 0, 'quality': 1}).executor, 'b')
        self.assertEqual(route(task, candidates, [], BudgetPolicy(max_tokens=1)).status, 'blocked')
        self.assertEqual(route(task, candidates, [], BudgetPolicy(max_retries=0, on_exceed='approval_required'), attempt=2).status, 'approval_required')
        parsed = candidates_from_config({'candidates': [{'executor': 'a', 'kind': 'mock'}, {'executor': 'unknown', 'kind': 'mock'}]}, {'a': caps_a})
        self.assertEqual(len(parsed), 1)
        self.assertEqual(policy_from_config({'max_executions': 2}).max_executions, 2)

    def test_budget_limits_retries_concurrency_and_unknown_bounds(self):
        guard = BudgetGuard(BudgetPolicy(max_executions=2, max_retries=1, max_concurrent=1,
                                         max_tokens=10, max_cost=2, on_exceed='approval_required'))
        with self.assertRaises(BudgetExceeded) as e:
            with guard.reserve('t', 1):
                pass
        self.assertEqual(e.exception.disposition, 'approval_required')
        with guard.reserve('t', 1, token_upper_bound=5, cost_upper_bound=1):
            with self.assertRaises(BudgetExceeded):
                with guard.reserve('other', 1, token_upper_bound=0, cost_upper_bound=0):
                    pass
        with guard.reserve('t', 2, token_upper_bound=5, cost_upper_bound=1):
            pass
        with self.assertRaises(BudgetExceeded):
            with guard.reserve('t', 3, token_upper_bound=0, cost_upper_bound=0):
                pass
        calls_guard = BudgetGuard(BudgetPolicy(max_model_calls=0))
        with self.assertRaises(BudgetExceeded):
            with calls_guard.reserve('model-task', 1, model_calls_upper_bound=1):
                pass
        with calls_guard.reserve('model-task', 1, model_calls_upper_bound=0):
            pass
        self.assertEqual(ScriptAdapter(self.root, guard=BudgetGuard(BudgetPolicy(max_model_calls=0))).execute(
            ExecutionRequest(self.task, 'script')).status, 'completed')

    def test_context_selection_and_usage_recording(self):
        selector = ContextSelector(self.root)
        manifest = ContextManifest((self.ref,), 7)
        self.assertEqual(selector.load(manifest, ('input.txt',)), {'input.txt': b'science'})
        with self.assertRaises(ValueError):
            selector.load(manifest, ('../secret',))
        with self.assertRaises(ValueError):
            selector.load(ContextManifest((self.ref,), 6), ('input.txt',))
        recorder = UsageRecorder(self.root)
        result = ScriptAdapter(self.root, recorder=recorder).execute(ExecutionRequest(self.task, 'script'))
        record = json.loads((self.root / 'usage/usage.jsonl').read_text())
        self.assertEqual(record['status'], result.status)
        self.assertIsNone(record['usage_metrics']['input_tokens'])
        with self.assertRaises(ValueError):
            UsageRecorder(self.root, '../outside.jsonl')

    def test_mock_model_unavailable_and_timeout(self):
        unavailable = ModelDescriptor('x', 'mock', None, available=False, implemented=True)
        self.assertEqual(MockModel(unavailable).invoke(ModelRequest('test')).status, 'unavailable')
        self.assertEqual(MockModel().invoke(ModelRequest('test', timeout_seconds=0)).status, 'timeout')
        result = MockModel().invoke(ModelRequest('test'))
        self.assertEqual(result.status, 'completed')
        self.assertEqual(result.usage_metrics.token_measurement, 'unknown')


if __name__ == '__main__':
    unittest.main()

class ProjectConfigurationTests(unittest.TestCase):
    def test_real_config_and_runtime_intersection(self):
        from ai4science.router import project_candidates
        root = Path(__file__).resolve().parents[1]
        def load(name):
            return json.loads((root / 'config' / (name + '.yaml')).read_text(encoding='utf-8'))
        routing, executors, models, budget = [load(x) for x in ('routing', 'executors', 'models', 'budgets')]
        runtime = {'script': ('script', ScriptAdapter.capabilities), 'mock': ('mock', MockExecutor.capabilities)}
        candidates, selected_models = project_candidates(routing, executors, models, runtime,
                                                          {'mock-model': MockModel().descriptor})
        self.assertEqual([x.executor.executor for x in candidates], ['script'])
        self.assertEqual(selected_models, [])
        task = ResearchTask('real', 'hash', 'sha256', ('sha256',), complexity='deterministic')
        self.assertEqual(route(task, candidates, selected_models, policy_from_config(budget),
                               preferences=routing['preferences']).executor, 'script')
        self.assertEqual(route(ResearchTask('other', 'unknown', 'shell'), candidates, selected_models,
                               policy_from_config(budget)).status, 'blocked')
        executors['executors'][0]['enabled'] = False
        self.assertEqual(project_candidates(routing, executors, models, runtime, {})[0], [])
        test_candidates, test_models = project_candidates(routing, load('executors'), models, runtime,
                                                           {'mock-model': MockModel().descriptor}, include_test_only=True)
        self.assertEqual(len(test_candidates), 2)
        self.assertEqual(len(test_models), 1)
