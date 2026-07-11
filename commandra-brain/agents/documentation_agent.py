from agents.base import Agent


class DocumentationAgent(Agent):
    name = "documentation_agent"
    system_prompt = "You are a technical writer who produces clear, accurate developer documentation."

    def specialty_instruction(self) -> str:
        return (
            "Produce clear documentation (README section, docstrings, or "
            "API docs as appropriate) describing the change for future "
            "developers, in Markdown."
        )
