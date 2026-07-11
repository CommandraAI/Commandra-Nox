from agents.base import Agent


class SecurityAgent(Agent):
    name = "security_agent"
    system_prompt = "You are an application security engineer."

    def specialty_instruction(self) -> str:
        return (
            "Analyze the relevant code for SQL injection, XSS, CSRF, SSRF, "
            "path traversal, hardcoded secrets, weak authentication, and "
            "vulnerable dependencies. Propose secure alternatives for each "
            "finding."
        )
