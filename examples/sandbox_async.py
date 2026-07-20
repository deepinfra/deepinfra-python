"""Async sandbox usage — e.g. inside an agent loop.

Needs DEEPINFRA_API_KEY in the environment.
"""

import asyncio

from deepinfra import Sandbox


async def main() -> None:
    async with await Sandbox.acreate(plan="small", timeout="5m") as sb:
        r = await sb.aexec("bash", "-c", "echo -n step1 && sleep 1 && echo -n ' step2'")
        print(r.check().stdout)

        r = await sb.arun_python("import platform; print(platform.machine())")
        print("arch:", r.stdout.strip())


if __name__ == "__main__":
    asyncio.run(main())
