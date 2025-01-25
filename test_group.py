import asyncio

import wom


async def main() -> None:
    # Instantiate the client
    client = wom.Client()

    # Start the client
    await client.start()

    # You can also alter some client properties after instantiation
    client.set_api_base_url("https://api.wiseoldman.net/v2")


    # Make requests with the client
    result = await client.groups.get_details(2300)

    if result.is_ok:
        # The result is ok, so we can unwrap here
        details = result.unwrap()
        print(details.group)
        print(details.memberships)
    else:
        # Lets see what went wrong
        print(f"Error: {result.unwrap_err()}")

    # Close the client
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
