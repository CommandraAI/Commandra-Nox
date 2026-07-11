from agents.base import Agent


class ReviewAgent(Agent):
    name = "review_agent"
    system_prompt = "You are a meticulous senior code reviewer."

    def specialty_instruction(self) -> str:
        return (
            "Review the proposed change for correctness, edge cases, "
            "consistency with the existing codebase, and readability. "
            "Call out anything risky before it ships."
        )
