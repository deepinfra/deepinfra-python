"""Sandbox quickstart: create, exec, file round-trip, terminate.

Needs DEEPINFRA_API_KEY in the environment.
"""

from deepinfra import Sandbox


def main() -> None:
    with Sandbox.create(plan="small", timeout="10m", tags={"demo": "quickstart"}) as sb:
        print("sandbox:", sb.id, sb.state)

        r = sb.exec("uname", "-a").check()
        print("kernel:", r.stdout.strip())

        r = sb.run_python("print(sum(range(101)))").check()
        print("sum 0..100 =", r.stdout.strip())

        sb.fs.write("/work/hello.txt", "hello from the host\n")
        print("read back:", sb.fs.read("/work/hello.txt").decode().strip())


if __name__ == "__main__":
    main()
