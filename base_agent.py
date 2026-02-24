import os
import re
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# (Imports same as before)

class BaseEngineeringAgent:
    def __init__(self, agent_id, model="anthropic/claude-4.6-sonnet"):
        self.agent_id = agent_id
        self.model = model

    def think_and_code(self, task):
        # We now use the 'full_spec' injected by the Orchestrator
        system_prompt = f"You are {self.agent_id}, a Senior Engineer. Follow the provided Technical Spec exactly."
        user_prompt = f"""
        TASK: {task['desc']}
        FILES: {task['files']}
        TECHNICAL SPEC:
        {task.get('full_spec', 'See source_of_truth.md')}
        
        {f"FIX FEEDBACK: {task.get('feedback')}" if task.get('feedback') else ""}
        
        Return code in '### filename' format.
        """
        response = client.chat.completions.create(model=self.model, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}])
        return response.choices[0].message.content

    # (_write_to_disk and execute_loop remain the same, 
    # but now use the updated 'think_and_code' that accepts the full 'task' dict)