# -*- coding: utf-8 -*-
"""向 .xmind 或 分支JSON 文件插入分支（按标题路径定位父节点，已存在同名子节点则跳过）

用法:
  python insert_branch.py <file.xmind> <父路径> <branches.json>
  python insert_branch.py <branches.json> <父路径> <branches.json>
父路径: 相对根主题的标题路径，如 "哲学史/中国哲学"；"." 表示根（顶层分支列表）
"""
import json, sys, os, uuid, zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_branches(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def title_of(x):
    return x.get("title") if isinstance(x, dict) else x


def find_child(node, title):
    for k in node.get("children", {}).get("attached", []):
        if k.get("title") == title:
            return k
    return None


def get_attached(node):
    return node.setdefault("children", {}).setdefault("attached", [])


def norm(b):
    """补齐 XMind 必需字段（id/class），保留已有内容"""
    if isinstance(b, str):
        return {"id": uuid.uuid4().hex, "class": "topic", "title": b}
    node = dict(b)
    node.setdefault("id", uuid.uuid4().hex)
    node.setdefault("class", "topic")
    node.setdefault("title", "")
    if "children" in node:
        kids = node["children"]
        if isinstance(kids, list):
            node["children"] = {"attached": [norm(k) for k in kids]}
        else:
            node["children"] = {"attached": [norm(k) for k in kids.get("attached", [])]}
    return node


def walk_path(root, path):
    node = root
    if path in (".", "", "/"):
        return node
    for seg in path.split("/"):
        nxt = find_child(node, seg)
        if nxt is None:
            raise SystemExit(f"[错误] 路径不存在: {seg} (在「{node.get('title')}」下)")
        node = nxt
    return node


def insert_xmind(xmind_path, parent_path, branches):
    with zipfile.ZipFile(xmind_path) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    content = json.loads(entries["content.json"].decode("utf-8"))
    root = content[0]["rootTopic"]
    parent = walk_path(root, parent_path)
    added, skipped = [], []
    for b in branches:
        t = title_of(b)
        if find_child(parent, t) is not None:
            skipped.append(t)
            continue
        get_attached(parent).append(norm(b))
        added.append(t)
    entries["content.json"] = json.dumps(content, ensure_ascii=False).encode("utf-8")
    tmp = xmind_path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n, data in entries.items():
            z.writestr(n, data)
    os.replace(tmp, xmind_path)
    print(f"[OK] {xmind_path} @ {parent_path}  新增: {added}  跳过: {skipped}")


def insert_json(json_path, parent_path, branches):
    top = load_branches(json_path)
    if parent_path in (".", "", "/"):
        parent_list = top
    else:
        cur_list = top
        cur = None
        for seg in parent_path.split("/"):
            found = None
            for x in cur_list:
                if title_of(x) == seg:
                    found = x
                    break
            if found is None:
                raise SystemExit(f"[错误] JSON路径不存在: {seg}")
            cur = found
            cur_list = cur.setdefault("children", [])
        parent_list = cur_list
    added, skipped = [], []
    for b in branches:
        t = title_of(b)
        if any(title_of(x) == t for x in parent_list):
            skipped.append(t)
            continue
        parent_list.append(b)
        added.append(t)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(top, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[OK] {json_path} @ {parent_path}  新增: {added}  跳过: {skipped}")


def main():
    target, parent_path, branch_file = sys.argv[1], sys.argv[2], sys.argv[3]
    branches = load_branches(branch_file)
    if target.lower().endswith(".xmind"):
        insert_xmind(target, parent_path, branches)
    else:
        insert_json(target, parent_path, branches)


if __name__ == "__main__":
    main()
