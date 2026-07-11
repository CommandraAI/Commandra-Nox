from agents.base import Agent


class BackendAgent(Agent):
    name = "backend_agent"
    system_prompt = "You are a senior backend engineer expert in API design and data layers."

    def specialty_instruction(self) -> str:
        return (
            "Implement or improve the relevant backend logic: API routes, "
            "validation, database access, error handling, and logging, "
            "consistent with the existing backend conventions."
        )
