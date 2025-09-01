# activities.py
import os
import json
import asyncio
import random
from temporalio import activity

# Use the same TOOL schema you used with Claude earlier (kept here for completeness)
TOOLS = [
    {
    "name": "wait_activity",
    "description": "Waits 5 seconds and returns status",
    "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_location",
        "description": "Get current location",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_weather",
        "description": "Get weather",
        "input_schema": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"],
        },
    },
    {
        "name": "get_search_results",
        "description": "We Do a web search",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "summarize_page",
        "description": "Summarize the contents from the URL",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "remind_me_my_name",
        "description": "This will help me remember my name",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_stock_price",
        "description": "Get the current stock price for a given ticker symbol",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    },
    {
        "name": "compare_stocks",
        "description": "Compare the stock prices of two ticker symbols",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker1": {"type": "string"},
                "ticker2": {"type": "string"},
            },
            "required": ["ticker1", "ticker2"],
        },
    },
    {
        "name": "tell_joke",
        "description": "This tells me a random joke and makes me laugh",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "roll_dice",
        "description": "Roll a dice with a specified number of sides, helps me play games",
        "input_schema": {
            "type": "object",
            "properties": {"sides": {"type": "integer"}},
            "required": ["sides"],
        },
    },
    {
        "name": "recommend_movie",
        "description": "Tells me a movie recommendation based on my preferences",
        "input_schema": {
            "type": "object",
            "properties": {"genre": {"type": "string"}},
            "required": ["genre"],
        },
    },
]

# default model (use the same you were using)
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# --- Planner / LLM activity ---
@activity.defn
async def call_llm(messages: list) -> dict:
    """
    Calls the Anthropic Claude client with the provided `messages`.
    messages: list[dict] where each dict is {"role": "...", "content": "..."}.
    This activity sends `TOOLS` so the model can emit tool_use blocks.
    Returns: the model response as a plain dict (model_dump) so workflow can inspect it.
    """
    # lazy import to avoid sandbox issues when workflow module is validated
    import dotenv
    dotenv.load_dotenv()
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    # convert messages to the shape expected by client.messages.create
    # We pass content as simple strings. Subsequent tool results will also be strings
    # (the workflow will put structured JSON into the 'content' text).
    # Run the blocking client call off the event loop.
    def sync_call():
        return client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
            tools=TOOLS,
            messages=messages,
            max_tokens=512,
        )

    resp = await asyncio.to_thread(sync_call)
    # model_dump is serializable and safe to return
    return resp.model_dump()


# --- Tool activities (all async) ---
@activity.defn
async def get_location() -> dict:
    # dummy / local implementation
    await asyncio.sleep(0.1)
    return {"location": "Bangalore, India", "source": "dummy"}


@activity.defn
async def get_weather(location: str) -> dict:
    await asyncio.sleep(0.1)
    return {
        "location": location,
        "temperature": "28°C",
        "condition": "Partly Cloudy",
        "source": "dummy",
    }

@activity.defn
async def wait_activity() -> dict:
    # Wait 5 seconds
    await asyncio.sleep(5)
    return {"status": "done", "waited": 5}


@activity.defn
async def get_search_results(query: str) -> dict:
    await asyncio.sleep(0.1)
    return {
        "query": query,
        "results": [
            "https://example.com/ai_agents",
            "https://example.com/llm_tools",
        ],
    }


@activity.defn
async def summarize_page(url: str) -> dict:
    await asyncio.sleep(0.1)
    return {"url": url, "summary": f"This is a short summary of {url}"}


@activity.defn
async def remind_me_my_name() -> dict:
    await asyncio.sleep(0.05)
    return {"name": "Your name is Prakhar", "source": "dummy"}


@activity.defn
async def get_stock_price(ticker: str) -> dict:
    await asyncio.sleep(0.05)
    prices = {"NVDA": 122.50, "AAPL": 185.30, "GOOGL": 140.75}
    return {
        "ticker": ticker,
        "price": prices.get(ticker.upper(), 100.00),
        "currency": "USD",
        "source": "dummy",
    }


@activity.defn
async def compare_stocks(ticker1: str, ticker2: str) -> dict:
    await asyncio.sleep(0.05)
    p1 = await get_stock_price.__wrapped__(ticker1) if hasattr(get_stock_price, "__wrapped__") else await get_stock_price(ticker1)
    p2 = await get_stock_price.__wrapped__(ticker2) if hasattr(get_stock_price, "__wrapped__") else await get_stock_price(ticker2)
    # p1/p2 might be dicts, ensure numeric
    price1 = p1.get("price") if isinstance(p1, dict) else p1
    price2 = p2.get("price") if isinstance(p2, dict) else p2
    diff = price1 - price2
    comparison = (
        f"{ticker1} is higher than {ticker2} by {abs(diff):.2f} USD"
        if diff > 0
        else f"{ticker2} is higher than {ticker1} by {abs(diff):.2f} USD"
        if diff < 0
        else f"{ticker1} and {ticker2} have the same price"
    )
    return {"ticker1": p1, "ticker2": p2, "comparison": comparison, "source": "dummy"}


@activity.defn
async def tell_joke() -> dict:
    await asyncio.sleep(0.05)
    jokes = [
        "Why don’t scientists trust atoms? Because they make up everything!",
        "Why did the math book look sad? Because it had too many problems.",
        "Why can’t your nose be 12 inches long? Because then it would be a foot!",
    ]
    return {"joke": random.choice(jokes), "source": "dummy"}


@activity.defn
async def roll_dice(sides: int = 6) -> dict:
    await asyncio.sleep(0.05)
    if sides < 2:
        return {"error": "Dice must have at least 2 sides."}
    return {"sides": sides, "result": random.randint(1, sides), "source": "dummy"}


@activity.defn
async def recommend_movie(genre: str) -> dict:
    await asyncio.sleep(0.05)
    recommendations = {
        "action": ["Mad Max: Fury Road", "John Wick", "Die Hard"],
        "comedy": ["Superbad", "Step Brothers", "The Hangover"],
        "drama": ["The Shawshank Redemption", "Forrest Gump", "Fight Club"],
        "sci-fi": ["Inception", "The Matrix", "Interstellar"],
        "romance": ["The Notebook", "Pride and Prejudice", "La La Land"],
    }
    movies = recommendations.get(genre.lower(), ["No recommendations available for this genre."])
    return {"genre": genre, "recommendation": random.choice(movies), "source": "dummy"}
