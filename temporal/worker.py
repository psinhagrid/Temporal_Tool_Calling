# worker.py
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
import activities
from workflow import LLMOrchestrationWorkflow

async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="tool-task-queue",  # make sure starter uses the same queue
        workflows=[LLMOrchestrationWorkflow],
        activities=[
            activities.call_llm,
            activities.get_location,
            activities.get_weather,
            activities.get_search_results,
            activities.summarize_page,
            activities.remind_me_my_name,
            activities.get_stock_price,
            activities.compare_stocks,
            activities.tell_joke,
            activities.roll_dice,
            activities.recommend_movie,
        ],
    )

    print("🚀 Worker started, listening on task queue 'tool-task-queue' ...")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
