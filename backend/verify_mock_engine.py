import asyncio
import sys
import os

# Add backend to sys.path
sys.path.append(os.getcwd())

from app.engines.ai import MockProvider, ChatMessage

async def main():
    try:
        print("Initializing MockProvider...")
        p = MockProvider()
        await p.initialize()
        print("MockProvider initialized.")
        
        print("Calling chat()...")
        resp = await p.chat([ChatMessage(role="user", content="hi")])
        print(f"Response: {resp}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
