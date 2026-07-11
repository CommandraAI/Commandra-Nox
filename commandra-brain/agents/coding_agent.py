from agents.base import Agent


class CodingAgent(Agent):
    name = "coding_agent"
    system_prompt = "You are an expert software engineer who writes production-ready, idiomatic code."

    def specialty_instruction(self) -> str:
        return (
            "Implement the requested change. Produce complete, runnable code "
            "for every file you touch, each in its own fenced code block "
            "labeled with the file path and language, following the "
            "conventions already present in the repository context."
        )
