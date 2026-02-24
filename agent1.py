from base_agent import BaseEngineeringAgent

# This allows run.py to pass the queues into the agent
def start_agent(agent_id, assign_q, submit_q):
    agent = BaseEngineeringAgent(agent_id=agent_id)
    agent.execute_loop(assign_q, submit_q)

if __name__ == "__main__":
    # For manual testing only
    print("Agent1 manual start requires queues. Use run.py instead.")