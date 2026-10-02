"""Integration checks for the router-to-Interaction-Agent context boundary."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.agents.interaction_agent.agent import prepare_message_with_history


class FakeRoster:
    def __init__(self, names):
        self.names = names

    def load(self):
        pass

    def get_agents(self):
        return list(self.names)


class FakeLogs:
    def load_recent(self, name, limit=10):
        requests = {
            "Alice Email": "Search Alice's email and check whether she replied.",
            "Alice Calendar": "Manage Alice's meetings and appointments.",
            "Tokyo Hotels": "Find lodging and hotel options in Tokyo.",
            "Dog Grooming": "Book grooming for the family dog.",
        }
        request = requests.get(name, "")
        if not request:
            return []
        return [("agent_request", "2026-10-01 12:00:00", request)]


class AgentContextRoutingTests(unittest.TestCase):
    def make_message(self, query, roster, *, top_k="2"):
        with (
            patch("server.agents.interaction_agent.agent.get_agent_roster", return_value=FakeRoster(roster)),
            patch("server.agents.interaction_agent.agent.get_execution_agent_logs", return_value=FakeLogs()),
            patch.dict(os.environ, {"OPENPOKE_AGENT_ROUTER_TOP_K": top_k}),
        ):
            return prepare_message_with_history(query, "prior conversation")[0]["content"]

    def test_only_relevant_top_k_summaries_reach_interaction_agent(self):
        content = self.make_message(
            "Did Alice reply?",
            ["Alice Email", "Alice Calendar", "Tokyo Hotels", "Dog Grooming"],
            top_k="1",
        )
        active = content.split("<active_agents>\n", 1)[1].split("\n</active_agents>", 1)[0]
        self.assertIn('name="Alice Email"', active)
        self.assertNotIn("Alice Calendar", active)
        self.assertNotIn("Tokyo Hotels", active)
        self.assertNotIn("Dog Grooming", active)
        self.assertIn("<new_user_message>\nDid Alice reply?", content)

    def test_no_match_guidance_is_in_message_and_unrelated_roster_is_hidden(self):
        content = self.make_message(
            "Find me a dentist in San Francisco",
            ["Alice Email", "Tokyo Hotels", "Dog Grooming"],
        )
        self.assertIn("No existing agent appears relevant", content)
        self.assertIn("Create a new agent", content)
        self.assertNotIn('<agent name="', content)

    def test_configured_top_k_is_capped_at_five(self):
        names = [f"Alice Email {number}" for number in range(8)]
        content = self.make_message("Alice email please", names, top_k="500")
        active = content.split("<active_agents>\n", 1)[1].split("\n</active_agents>", 1)[0]
        self.assertLessEqual(active.count("<agent "), 5)


if __name__ == "__main__":
    unittest.main()
