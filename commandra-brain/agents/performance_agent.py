from agents.base import Agent


class PerformanceAgent(Agent):
    name = "performance_agent"
    system_prompt = "You are a performance engineer focused on measurable improvements."

    def specialty_instruction(self) -> str:
        return (
            "Identify performance bottlenecks (CPU, memory, database, "
            "network, bundle size, rendering) in the relevant code and "
            "propose concrete, low-risk optimizations."
        )
