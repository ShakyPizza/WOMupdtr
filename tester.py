from wom import client



client = wom.Client(user_agent="@jonxslays")

async def main():
    await client.start()

    result = await client.players.update_player("jonxslays")

    if result.is_ok:
        print(result.unwrap())
    else:
        print(result.unwrap_err())

    await client.close()

import asyncio
asyncio.run(main())