import importlib.util
import sys
import unittest
from pathlib import Path

_ROUTER_PATH = Path(__file__).parents[1] / "services" / "execution" / "router.py"
_SPEC = importlib.util.spec_from_file_location("agent_router", _ROUTER_PATH)
_ROUTER_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _ROUTER_MODULE
_SPEC.loader.exec_module(_ROUTER_MODULE)
AgentProfile, AgentRouter = _ROUTER_MODULE.AgentProfile, _ROUTER_MODULE.AgentRouter


class AgentRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = AgentRouter(top_k=2, threshold=0.29)
        self.agents = [
            AgentProfile("Alice Email", "Search Alice's email and check whether she replied", "email"),
            AgentProfile("Alice Calendar", "Manage Alice's meetings and appointments", "calendar"),
            AgentProfile("Tokyo Hotels", "Find hotels and lodging in Tokyo", "lodging", ("Tokyo",)),
        ]

    def test_exact_and_synonym_match(self):
        result = self.router.route("Did Alice reply?", self.agents)
        self.assertTrue(result.matched)
        self.assertEqual(result.candidates[0].name, "Alice Email")

    def test_entity_collision_prefers_task(self):
        result = self.router.route("Find Alice's latest email", self.agents)
        self.assertEqual(result.candidates[0].name, "Alice Email")

    def test_topic_collision_prefers_hotels(self):
        agents = self.agents + [AgentProfile("Tokyo Flights", "Search flights to Tokyo")]
        result = self.router.route("Find a place to stay in Tokyo", agents)
        self.assertEqual(result.candidates[0].name, "Tokyo Hotels")

    def test_unrelated_query_abstains(self):
        result = self.router.route("Find me a dentist in San Francisco", self.agents)
        self.assertFalse(result.matched)
        self.assertEqual(result.candidates, ())

    def test_top_k_is_bounded(self):
        result = self.router.route("Tokyo hotel booking", self.agents * 5)
        self.assertLessEqual(len(result.candidates), 2)

    def test_empty_and_ambiguous_inputs(self):
        self.assertFalse(self.router.route("anything", []).matched)
        result = self.router.route("Alice", self.agents)
        self.assertLessEqual(len(result.candidates), 2)

    def test_threshold_is_configurable(self):
        strict = AgentRouter(threshold=0.95).route("check Alice's email", self.agents)
        self.assertFalse(strict.matched)

    def test_duplicate_and_irrelevant_profiles_are_safe(self):
        agents = self.agents + [self.agents[0], AgentProfile("Dog Grooming", "Book dog grooming")]
        result = self.router.route("Did Alice reply?", agents)
        self.assertEqual(result.candidates[0].name, "Alice Email")
        self.assertEqual(sum(agent.name == "Alice Email" for agent in result.candidates), 1)
        self.assertLessEqual(len(result.candidates), 2)


if __name__ == "__main__":
    unittest.main()
