# starter.py
import asyncio
import uuid
from temporalio.client import Client
from temporalio.api.enums.v1 import WorkflowIdReusePolicy
from workflow import LLMOrchestrationWorkflow

async def main():
    client = await Client.connect("localhost:7233")

    question = input("Ask me something (e.g. 'Tell me a joke, roll d20, and weather in SF'): ")

    # Use same workflow ID so subsequent runs replace the previous active run
    result = await client.execute_workflow(
        LLMOrchestrationWorkflow.run,
        question,
        id="llm-orchestration",  # fixed id
        task_queue="tool-task-queue",
        id_reuse_policy=WorkflowIdReusePolicy.WORKFLOW_ID_REUSE_POLICY_TERMINATE_IF_RUNNING,
    )

    print("Workflow result:\n", result)

if __name__ == "__main__":
    asyncio.run(main())
