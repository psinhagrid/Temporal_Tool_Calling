# workflow.py
from datetime import timedelta
import json
from temporalio import workflow
import activities
import asyncio

@workflow.defn
class LLMOrchestrationWorkflow:
    @workflow.run
    async def run(self, question: str) -> str:
        """
        Orchestration loop:
          - send `messages` to call_llm
          - if the LLM returns tool_use blocks, run the tool activities concurrently
          - feed results back into messages and repeat
        """
        messages = [{"role": "user", "content": question}]
        previous_results = {}

        while True:
            # Ask the planner LLM
            resp = await workflow.execute_activity(
                activities.call_llm,
                messages,
                schedule_to_close_timeout=timedelta(seconds=30),
            )

            content = resp.get("content", []) if isinstance(resp, dict) else []

            # Extract tool calls
            tool_calls = []
            for block in content:
                try:
                    if block.get("type") == "tool_use":
                        tool_calls.append({
                            "id": block.get("id"),
                            "name": block.get("name") or block.get("tool") or block.get("tool_name"),
                            "input": block.get("input") or {},
                            "raw": block,
                        })
                except Exception:
                    continue

            # No tool calls? Return assistant text
            if not tool_calls:
                texts = []
                for block in content:
                    t = block.get("text") or block.get("content") or block.get("message")
                    if isinstance(t, str):
                        texts.append(t)
                    elif isinstance(t, list):
                        for item in t:
                            if isinstance(item, dict) and item.get("type") == "output_text":
                                texts.append(item.get("text", ""))
                return "\n".join(texts) if texts else json.dumps(resp, indent=2)

            # 🔹 Run tools concurrently
            async def run_tool(call):
                name = call.get("name")
                inp = call.get("input", {}) or {}
                result = {"error": f"Unknown tool {name}"}
                try:
                    if name == "get_location":
                        result = await workflow.execute_activity(
                            activities.get_location,
                            schedule_to_close_timeout=timedelta(seconds=20),
                        )
                    elif name == "get_weather":
                        loc = inp.get("location") or previous_results.get("get_location", {}).get("location") or "Unknown"
                        result = await workflow.execute_activity(
                            activities.get_weather,
                            loc,
                            schedule_to_close_timeout=timedelta(seconds=20),
                        )
                    elif name == "get_search_results":
                        result = await workflow.execute_activity(
                            activities.get_search_results,
                            inp.get("query", ""),
                            schedule_to_close_timeout=timedelta(seconds=20),
                        )
                    elif name == "summarize_page":
                        result = await workflow.execute_activity(
                            activities.summarize_page,
                            inp.get("url", ""),
                            schedule_to_close_timeout=timedelta(seconds=20),
                        )
                    elif name == "remind_me_my_name":
                        result = await workflow.execute_activity(
                            activities.remind_me_my_name,
                            schedule_to_close_timeout=timedelta(seconds=10),
                        )
                    elif name == "get_stock_price":
                        result = await workflow.execute_activity(
                            activities.get_stock_price,
                            inp.get("ticker", ""),
                            schedule_to_close_timeout=timedelta(seconds=20),
                        )
                    elif name == "compare_stocks":
                        result = await workflow.execute_activity(
                            activities.compare_stocks,
                            inp.get("ticker1", ""),
                            inp.get("ticker2", ""),
                            schedule_to_close_timeout=timedelta(seconds=20),
                        )
                    elif name == "tell_joke":
                        result = await workflow.execute_activity(
                            activities.tell_joke,
                            schedule_to_close_timeout=timedelta(seconds=10),
                        )
                    elif name == "roll_dice":
                        result = await workflow.execute_activity(
                            activities.roll_dice,
                            int(inp.get("sides", 6)),
                            schedule_to_close_timeout=timedelta(seconds=10),
                        )
                    elif name == "recommend_movie":
                        result = await workflow.execute_activity(
                            activities.recommend_movie,
                            inp.get("genre", ""),
                            schedule_to_close_timeout=timedelta(seconds=15),
                        )
                    elif name == "wait_activity":  # NEW
                        result = await workflow.execute_activity(
                            activities.wait_activity,
                            schedule_to_close_timeout=timedelta(seconds=10),
                        )
                except Exception as e:
                    result = {"error": str(e)}

                previous_results[name] = result
                return {"tool_use_id": call.get("id"), "name": name, "result": result}

            # Gather all tool results concurrently
            tool_results = await asyncio.gather(*(run_tool(call) for call in tool_calls))

            # Feed tool calls/results back into messages for the next LLM iteration
            messages.append({"role": "assistant", "content": json.dumps([c["raw"] for c in tool_calls])})
            messages.append({"role": "user", "content": json.dumps(tool_results)})
