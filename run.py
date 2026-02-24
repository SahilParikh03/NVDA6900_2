import threading
import time
import logging
from orchestrator import Orchestrator
from agent1 import start_agent as start_agent1
from agent2 import start_agent as start_agent2
from agent3 import start_agent as start_agent3

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SYSTEM] %(message)s")

def main():
    print("="*50)
    print("🚀 NVDA EARNINGS WAR ROOM: ENGINE START")
    print("="*50)

    # 1. Initialize the CTO
    orch = Orchestrator()

    # 2. Define the threads
    # We pass the queues from the orchestrator instance to the agents
    threads = [
        threading.Thread(target=orch.run, name="CTO-Orchestrator", daemon=True),
        threading.Thread(target=start_agent1, args=("agent1", orch.assignment_queues["agent1"], orch.submission_queue), name="Agent-1", daemon=True),
        threading.Thread(target=start_agent2, args=("agent2", orch.assignment_queues["agent2"], orch.submission_queue), name="Agent-2", daemon=True),
        threading.Thread(target=start_agent3, args=("agent3", orch.assignment_queues["agent3"], orch.submission_queue), name="Agent-3", daemon=True),
    ]

    # 3. Launch all
    for t in threads:
        t.start()
        logging.info(f"Started thread: {t.name}")
        time.sleep(0.5)

    logging.info("System is fully operational. Monitoring for file changes...")

    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping War Room...")

if __name__ == "__main__":
    main()