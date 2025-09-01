# workflow.py
from datetime import timedelta
import json
from temporalio import workflow
import activities

@workflow.defn
class LLMOrchestrationWorkflow:
    @workflow.run
    async def run(self, question: str) -> str:
        """
        Orchestration loop:
          - send `messages` to call_llm
          - if the LLM returns tool_use blocks, run the tool activities
          - feed results back into messages and repeat
        """
        # initial messages (simple user prompt)
        messages = [{"role": "user", "content": question}]
        previous_results = {}

        while True:
            # Ask the planner LLM (activity runs the real Anthropic client)
            resp = await workflow.execute_activity(
                activities.call_llm,
                messages,
                schedule_to_close_timeout=timedelta(seconds=30),
            )

            # resp is a dict (model_dump). Try to find tool_use blocks in resp['content']
            content = resp.get("content", []) if isinstance(resp, dict) else []
            # content is typically a list of blocks; blocks that request tools usually have type == "tool_use"
            tool_calls = []
            for block in content:
                try:
                    if block.get("type") == "tool_use":
                        # normalize block to a simple dict {id, name, input}
                        tool_calls.append({
                            "id": block.get("id"),
                            "name": block.get("name") or block.get("tool") or block.get("tool_name"),
                            "input": block.get("input") or {},
                            "raw": block,
                        })
                except Exception:
                    continue

            # If no tools requested, return textual assistant result (or full JSON as fallback)
            if not tool_calls:
                # assemble human-readable assistant text from content blocks (best-effort)
                texts = []
                for block in content:
                    # many model dumps include text blocks under 'text' or nested in 'message' like dict
                    if block.get("type") in ("output_text", "message", "text"):
                        # different shapes: prefer 'text', then 'content', then 'message' keys
                        t = block.get("text") or block.get("content") or block.get("message")
                        if isinstance(t, str):
                            texts.append(t)
                        elif isinstance(t, list):
                            # list of inner dicts with 'text'
                            for item in t:
                                if isinstance(item, dict) and item.get("type") == "output_text":
                                    texts.append(item.get("text", ""))
                    else:
                        # fallback: try 'text' key
                        if block.get("text"):
                            texts.append(block.get("text"))
                if texts:
                    return "\n".join(texts)
                # fallback: return full model dump as JSON string
                return json.dumps(resp, indent=2)

            # Run the tools requested (sequentially) and collect results
            tool_results = []
            for call in tool_calls:
                name = call.get("name")
                inp = call.get("input", {}) or {}
                result = {"error": f"Unknown tool {name}"}
                try:
                    if name == "get_location":
                        result = await workflow.execute_activity(activities.get_location, schedule_to_close_timeout=timedelta(seconds=20))
                    elif name == "get_weather":
                        # if location missing, try to use previous get_location result
                        loc = inp.get("location")
                        if not loc:
                            loc = previous_results.get("get_location", {}).get("location")
                        if not loc:
                            loc = "Unknown"
                        result = await workflow.execute_activity(activities.get_weather, loc, schedule_to_close_timeout=timedelta(seconds=20))
                    elif name == "get_search_results":
                        q = inp.get("query", "")
                        result = await workflow.execute_activity(activities.get_search_results, q, schedule_to_close_timeout=timedelta(seconds=20))
                    elif name == "summarize_page":
                        url = inp.get("url", "")
                        result = await workflow.execute_activity(activities.summarize_page, url, schedule_to_close_timeout=timedelta(seconds=20))
                    elif name == "remind_me_my_name":
                        result = await workflow.execute_activity(activities.remind_me_my_name, schedule_to_close_timeout=timedelta(seconds=10))
                    elif name == "get_stock_price":
                        ticker = inp.get("ticker", "")
                        result = await workflow.execute_activity(activities.get_stock_price, ticker, schedule_to_close_timeout=timedelta(seconds=20))
                    elif name == "compare_stocks":
                        t1 = inp.get("ticker1", "")
                        t2 = inp.get("ticker2", "")
                        result = await workflow.execute_activity(activities.compare_stocks, t1, t2, schedule_to_close_timeout=timedelta(seconds=20))
                    elif name == "tell_joke":
                        result = await workflow.execute_activity(activities.tell_joke, schedule_to_close_timeout=timedelta(seconds=10))
                    elif name == "roll_dice":
                        sides = int(inp.get("sides", 6))
                        result = await workflow.execute_activity(activities.roll_dice, sides, schedule_to_close_timeout=timedelta(seconds=10))
                    elif name == "recommend_movie":
                        genre = inp.get("genre", "")
                        result = await workflow.execute_activity(activities.recommend_movie, genre, schedule_to_close_timeout=timedelta(seconds=15))
                    else:
                        result = {"error": f"Unrecognized tool {name}"}
                except Exception as e:
                    result = {"error": str(e)}

                # store per-tool result
                previous_results[name] = result
                tool_results.append({"tool_use_id": call.get("id"), "name": name, "result": result})

            # Feed the tool calls and results back into messages for the next planner call.
            # Instead of using specialized anthropic objects we send textual summaries that the LLM can parse.
            # Assistant message: what tool(s) it requested (as JSON)
            messages.append({"role": "assistant", "content": json.dumps([c["raw"] for c in tool_calls])})

            # User message: the results for each tool (as JSON)
            messages.append({"role": "user", "content": json.dumps(tool_results)})

            # Loop — next call to call_llm will see the tool results and either call more tools or finish.
