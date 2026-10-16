# -*- coding: utf-8 -*-
"""打印 .xmind 主题树: python dump_xmind.py <file.xmind> [max_depth]"""
import json, sys, zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    path = sys.argv[1]
    maxd = int(sys.argv[2]) if len(sys.argv) > 2 else 99
    with zipfile.ZipFile(path) as z:
        content = json.loads(z.read("content.json").decode("utf-8"))
    def w(t, d=0):
        if d > maxd:
            return
        print("  " * d + t.get("title", ""))
        for c in t.get("children", {}).get("attached", []):
            w(c, d + 1)
    for s in content:
        print(f"[sheet] {s.get('title', '')}")
        w(s["rootTopic"])


if __name__ == "__main__":
    main()
