# -*- coding: utf-8 -*-
"""设置 .xmind 每个图纸的结构布局（写在 rootTopic.structureClass，XMind 2020+ 生效）

用法: python set_structure.py <file.xmind> [structure]
structure 可用别名:
  tree-right / logic-right → org.xmind.ui.logic.right   (根在左，树状向右，最易读、易折叠)
  tree-left  / logic-left  → org.xmind.ui.logic.left
  map                       → org.xmind.ui.map.unbalanced (默认思维导图)
  其他值原样写入（如 org.xmind.ui.tree.right 等自定义 ID）
缺省为 tree-right
"""
import json, sys, os, zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ALIAS = {
    "tree-right": "org.xmind.ui.logic.right",
    "logic-right": "org.xmind.ui.logic.right",
    "tree-left": "org.xmind.ui.logic.left",
    "logic-left": "org.xmind.ui.logic.left",
    "map": "org.xmind.ui.map.unbalanced",
    "mindmap": "org.xmind.ui.map.unbalanced",
}


def main():
    path = sys.argv[1]
    raw = sys.argv[2] if len(sys.argv) > 2 else "tree-right"
    sc = ALIAS.get(raw.lower(), raw)
    with zipfile.ZipFile(path) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    content = json.loads(entries["content.json"].decode("utf-8"))
    for sheet in content:
        sheet["rootTopic"]["structureClass"] = sc
    entries["content.json"] = json.dumps(content, ensure_ascii=False).encode("utf-8")
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n, data in entries.items():
            z.writestr(n, data)
    os.replace(tmp, path)
    print(f"[OK] {path} -> structureClass = {sc}")


if __name__ == "__main__":
    main()
