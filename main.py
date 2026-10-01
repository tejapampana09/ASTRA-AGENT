from langchain.agents import create_agent
from langchain.tools import tool

@tool
async def get_weather(location: str) -> str:
    # Placeholder for weather retrieval logic
    return f'Weather in {location} is sunny.'

agent = create_agent([get_weather])
agent.run('London')