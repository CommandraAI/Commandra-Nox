from agents.base import Agent


class PlannerAgent(Agent):
    name = "planner_agent"
    system_prompt = "You are a senior software architect who designs implementations before code is written."

    def specialty_instruction(self) -> str:
        return (
            "Design the implementation: list exactly which files will be created "
            "or modified and what changes each needs, in dependency order."
        )
