import asyncio
import recommendation_agent

async def test():
    try:
        data = await recommendation_agent.get_recommendations("Chennai", "Tamil Nadu", "India")
        print("Success, locations count:", len(data.get("spots", [])))
        for s in data.get("spots", []):
            print(f"  - {s['name']} | {s['type']} | {s.get('image', '')[:80]}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
