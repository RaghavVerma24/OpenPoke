"""Reproducible routing benchmark: python server/tests/evaluate_router.py"""

import importlib.util
from pathlib import Path
import sys

_ROUTER_PATH = Path(__file__).parents[1] / "services" / "execution" / "router.py"
_SPEC = importlib.util.spec_from_file_location("agent_router", _ROUTER_PATH)
_ROUTER_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _ROUTER_MODULE
_SPEC.loader.exec_module(_ROUTER_MODULE)
AgentProfile, AgentRouter = _ROUTER_MODULE.AgentProfile, _ROUTER_MODULE.AgentRouter


AGENTS = [
    AgentProfile("Alice Email", "Search Alice's email and check whether she replied", "email"),
    AgentProfile("Alice Calendar", "Manage Alice's meetings and appointments", "calendar"),
    AgentProfile("Tokyo Hotels", "Find hotels and lodging in Tokyo", "lodging", ("Tokyo",)),
    AgentProfile("Tokyo Flights", "Search flights and airfare to Tokyo", "travel", ("Tokyo",)),
    AgentProfile("Tokyo Dining", "Find restaurants and dinner reservations in Tokyo", "dining", ("Tokyo",)),
    AgentProfile("Vercel Job", "Track Vercel job offer and recruiting emails", "email", ("Vercel",)),
    AgentProfile("Weekly Reminder", "Create recurring reminders and follow-ups", "reminder"),
    AgentProfile("Grocery List", "Maintain shopping and grocery list", "todo"),
    AgentProfile("Project Launch", "Coordinate project launch tasks and deadlines", "project"),
    AgentProfile("Mom Email", "Search messages and drafts involving Mom", "email"),
]

CASES = [
    ("Did Alice reply?", "Alice Email"),
    ("Check Alice's inbox for her response", "Alice Email"),
    ("Did Alice get back to me by mail?", "Alice Email"),
    ("What did Alice say in her latest message?", "Alice Email"),
    ("Find Alice's email about the proposal", "Alice Email"),
    ("Schedule a meeting with Alice", "Alice Calendar"),
    ("When is my next appointment with Alice?", "Alice Calendar"),
    ("Move Alice's meeting to Friday", "Alice Calendar"),
    ("Book somewhere to stay in Tokyo", "Tokyo Hotels"),
    ("Find a Tokyo hotel for next week", "Tokyo Hotels"),
    ("Compare lodging options in Tokyo", "Tokyo Hotels"),
    ("Look up airfare to Tokyo", "Tokyo Flights"),
    ("Find flights from Toronto to Tokyo", "Tokyo Flights"),
    ("Can you check airline options for Tokyo?", "Tokyo Flights"),
    ("Book dinner in Tokyo", "Tokyo Dining"),
    ("Find a restaurant in Tokyo for tonight", "Tokyo Dining"),
    ("Where should I eat in Tokyo?", "Tokyo Dining"),
    ("Any update on the Vercel offer?", "Vercel Job"),
    ("Check my recruiting email from Vercel", "Vercel Job"),
    ("Did Vercel send the job contract?", "Vercel Job"),
    ("Remind me to call the dentist tomorrow", "Weekly Reminder"),
    ("Set a recurring reminder every Monday", "Weekly Reminder"),
    ("Follow up with me about this next week", "Weekly Reminder"),
    ("Add milk and apples to groceries", "Grocery List"),
    ("Update my shopping list with coffee", "Grocery List"),
    ("What do I need to buy at the store?", "Grocery List"),
    ("Track the launch deadlines for our project", "Project Launch"),
    ("Coordinate tasks for the product launch", "Project Launch"),
    ("What remains before the project goes live?", "Project Launch"),
    ("Did Mom email me back?", "Mom Email"),
    ("Search my messages from Mom", "Mom Email"),
    ("Find the latest mail from Mom", "Mom Email"),
    ("Find me a dentist in San Francisco", None),
    ("What is the weather in Lisbon?", None),
    ("Explain how photosynthesis works", None),
    ("Find a plumber near me", None),
    ("Translate this sentence into French", None),
    ("What is 19 times 23?", None),
    ("Recommend a movie for tonight", None),
    ("Is the local museum open on Sunday?", None),
]


def evaluate():
    router = AgentRouter(top_k=4, threshold=0.29)
    relevant = [case for case in CASES if case[1] is not None]
    no_match = [case for case in CASES if case[1] is None]
    recall1 = recall3 = reciprocal_rank = 0.0
    false_reuse = no_match_correct = 0
    exposed = 0
    candidate_words = 0
    for query, expected in CASES:
        result = router.route(query, AGENTS)
        exposed += len(result.candidates)
        candidate_words += sum(
            len((candidate.name + " " + candidate.description).split())
            for candidate in result.candidates
        )
        if expected:
            names = [candidate.name for candidate in result.candidates]
            if names and names[0] == expected:
                recall1 += 1
            if expected in names[:3]:
                recall3 += 1
            if expected in names:
                reciprocal_rank += 1 / (names.index(expected) + 1)
        elif not result.matched:
            no_match_correct += 1
        else:
            false_reuse += 1

    # Baseline represents the current design: give all roster names to the LLM.
    full_roster_per_query = len(AGENTS)
    mean_exposed = exposed / len(CASES)
    scale = {}
    for size in (10, 50, 100, 500):
        padded = AGENTS + [
            AgentProfile(f"Unrelated Service {index}", f"Handle unrelated category {index}")
            for index in range(size - len(AGENTS))
        ]
        scale_router = AgentRouter(top_k=4, threshold=0.29)
        scale_exposed = sum(len(scale_router.route(query, padded).candidates) for query, _ in CASES)
        scale[size] = {
            "mean_agents_exposed": round(scale_exposed / len(CASES), 2),
            "max_agents_exposed": 4,
        }

    baseline_words = sum(len(agent.name.split()) for agent in AGENTS)
    return {
        "cases": len(CASES),
        "recall_at_1": round(recall1 / len(relevant), 3),
        "recall_at_3": round(recall3 / len(relevant), 3),
        "mrr": round(reciprocal_rank / len(relevant), 3),
        "false_reuse_rate": round(false_reuse / len(no_match), 3),
        "no_match_accuracy": round(no_match_correct / len(no_match), 3),
        "mean_agents_exposed": round(mean_exposed, 2),
        "baseline_agents_exposed": full_roster_per_query,
        "exposure_reduction_percent": round(100 * (1 - mean_exposed / full_roster_per_query), 1),
        "estimated_context_word_reduction_percent": round(
            100 * (1 - candidate_words / (len(CASES) * baseline_words)), 1
        ),
        "scale": scale,
    }


if __name__ == "__main__":
    print(evaluate())
