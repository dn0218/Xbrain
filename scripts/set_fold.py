# -*- coding: utf-8 -*-
"""设置 .xmind 默认折叠深度：深度 >= min_depth 且有子节点的主题写入 folded=true

用法: python set_fold.py <file.xmind> [min_depth=3]
深度: 根=1, 一级分支=2, 二级分支=3 ...
min_depth=0 全部展开
"""
import json, sys, os, zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    path = sys.argv[1]
    min_depth = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    with zipfile.ZipFile(path) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    content = json.loads(entries["content.json"].decode("utf-8"))
    folded, unfolded = 0, 0

    def walk(t, d):
        nonlocal folded, unfolded
        kids = t.get("children", {}).get("attached", [])
        if kids:
            if min_depth > 0 and d >= min_depth:
                t["folded"] = True
                folded += 1
            else:
                t.pop("folded", None)
                unfolded += 1
            for k in kids:
                walk(k, d + 1)

    for sheet in content:
        walk(sheet["rootTopic"], 1)
    entries["content.json"] = json.dumps(content, ensure_ascii=False).encode("utf-8")
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n, data in entries.items():
            z.writestr(n, data)
    os.replace(tmp, path)
    print(f"[OK] {path}  折叠 {folded} 个分支 (深度>={min_depth}), 展开至深度 {max(min_depth-1, 0)}")


if __name__ == "__main__":
    main()
