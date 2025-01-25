from wom import Client
import asyncio

username = "R N G"

async def main():
    client = Client()
    player = await client.players.get_player(username)
    print(player)

# Run the async function
asyncio.run(main())
