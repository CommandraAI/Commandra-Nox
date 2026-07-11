from agents.base import Agent


class FrontendAgent(Agent):
    name = "frontend_agent"
    system_prompt = "You are a senior frontend engineer expert in modern component architecture and accessibility."

    def specialty_instruction(self) -> str:
        return (
            "Implement or improve the relevant UI: reusable components, "
            "state management, responsive layout, and accessibility, "
            "consistent with the existing frontend conventions."
        )
