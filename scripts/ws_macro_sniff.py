#!/usr/bin/env python3
"""Canlı WS'den son snapshot macroLevels al."""
import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("pip install websockets")
    sys.exit(1)

URL = "ws://178.105.150.40:8765"


async def main():
    async with websockets.connect(URL, open_timeout=15) as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=20)
        msg = json.loads(raw)
        ml = msg.get("macroLevels")
        print("=== WS ilk mesaj keys ===")
        print(sorted(msg.keys()))
        print("\n=== macroLevels ===")
        if ml is None:
            print("macroLevels: YOK (null/undefined)")
        else:
            filled = [x for x in ml if (x.get("snippet") or "").strip()]
            print(f"count={len(ml)} filled={len(filled)}")
            print(json.dumps(ml, ensure_ascii=False, indent=2))
        if msg.get("error"):
            print("\n=== error ===")
            print(msg["error"])


if __name__ == "__main__":
    asyncio.run(main())
