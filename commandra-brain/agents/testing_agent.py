from agents.base import Agent


class TestingAgent(Agent):
    name = "testing_agent"
    system_prompt = "You are a test engineer who writes thorough, maintainable automated tests."

    def specialty_instruction(self) -> str:
        return (
            "Write unit/integration tests covering the new or changed "
            "behavior, including edge cases and failure modes, using the "
            "testing framework already used in this repository."
        )
