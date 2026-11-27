import argparse
import json
import socket


def main():
    parser = argparse.ArgumentParser(description="Drive the archive release")
    parser.add_argument("operation")
    parser.add_argument("values", nargs="*")
    args = parser.parse_args()
    request = json.dumps({"op": args.operation, "args": args.values}).encode()
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(27)
        connection.connect("/run/opsd/opsd.sock")
        connection.sendall(request + b"\n")
        with connection.makefile("rb") as stream:
            reply = json.loads(stream.readline(1024 * 1024))
    print(json.dumps(reply, sort_keys=True, indent=2))
    return 0 if reply["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
