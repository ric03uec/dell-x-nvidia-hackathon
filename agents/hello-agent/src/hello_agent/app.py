"""hello-agent's HTTP surface. `just new <name>` copies this project."""

from agentkit import create_app

app = create_app("hello-agent")


@app.get("/greet/{who}")
def greet(who: str) -> dict[str, str]:
    """Agent-specific routes go here. Anything worth sharing belongs in agentkit."""
    return {"greeting": f"hello, {who}"}
