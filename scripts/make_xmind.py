# -*- coding: utf-8 -*-
"""Xbrain 脑图生成/更新工具
生成现代 XMind (2020+) 可打开的 .xmind 文件（ZIP: content.json + manifest.json + metadata.json）
用法: python make_xmind.py <输出文件> <根主题> <分支JSON文件>
"""
import json, sys, zipfile, uuid, os

def topic(title, children=None):
    t = {"id": uuid.uuid4().hex, "class": "topic", "title": title}
    if children:
        t["children"] = {"attached": [topic(c, k) if isinstance(c, str) else topic(c.get("title",""), c.get("children")) for c in children for k in [c if isinstance(c, str) else None] if (k is not None or not isinstance(c, str))]}
    return t

def build(title, branches):
    def t(title, children=None):
        node = {"id": uuid.uuid4().hex, "class": "topic", "title": title}
        kids = []
        for c in (children or []):
            if isinstance(c, str):
                kids.append(t(c))
            else:
                kids.append(t(c.get("title", ""), c.get("children")))
        if kids:
            node["children"] = {"attached": kids}
        return node
    sheet = {
        "id": uuid.uuid4().hex,
        "class": "sheet",
        "title": title,
        "rootTopic": t(title, branches),
        "topicPositioning": "fixed"
    }
    return [sheet]

def main():
    out, root_title, json_path = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(json_path, encoding="utf-8") as f:
        branches = json.load(f)
    content = build(root_title, branches)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.json", json.dumps(content, ensure_ascii=False))
        z.writestr("manifest.json", json.dumps({"file-entries": {"content.json": {}}}))
        z.writestr("metadata.json", json.dumps({"creator": {"name": "Xbrain Agent", "version": "1.0"}}))
    print("OK:", out)

if __name__ == "__main__":
    main()
