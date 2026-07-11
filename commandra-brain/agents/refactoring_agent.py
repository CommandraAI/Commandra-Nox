from agents.base import Agent


class RefactoringAgent(Agent):
    name = "refactoring_agent"
    system_prompt = "You are a refactoring specialist who improves code without changing behavior."

    def specialty_instruction(self) -> str:
        return (
            "Refactor the identified code for readability, naming, and "
            "maintainability -- remove duplication and dead code, split "
            "overly large functions/classes -- without changing observable "
            "behavior."
        )
