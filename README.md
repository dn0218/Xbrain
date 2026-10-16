# Xbrain - 跨学科知识脑图库

一个由 AI 智能体维护的跨学科知识体系脑图库，使用 XMind 格式组织知识。

## 目录结构

```
Xbrain/
├── README.md           # 本说明文件
├── Xbrain.xmind        # 知识体系总览脑图
├── 哲学/哲学.xmind     # 哲学（形而上学/认识论/伦理学/逻辑学/美学/哲学史）
├── 科技/科技.xmind     # 科技（计算机/AI/生物技术/能源材料/航天）
├── 数理化/数理化.xmind # 数学、物理、化学
├── 神学/神学.xmind     # 神学（圣经研究/系统/历史/实践神学/比较宗教）
├── scripts/            # 脑图生成脚本与数据源（JSON）
└── .xbrain/state.json  # 智能体环境状态文件
```

## 知识体系框架

根节点：**我的知识体系**

一级学科节点：
- 哲学
- 科技
- 数理化
- 神学

## 工作流

1. 用户提供学习内容或知识整理需求
2. 智能体通过 XMind 生成/更新对应脑图（.xmind 文件）
3. 每次变更自动执行 `git add` / `git commit` / `git push` 同步到 GitHub

## 版本控制

- 远程仓库：https://github.com/dn0218/Xbrain.git
- 主分支：`main`

## 脑图生成方式

当前通过 `scripts/make_xmind.py` 直接生成 XMind 2020+ 格式（ZIP: content.json + manifest.json + metadata.json）的 .xmind 文件，可在 XMind 中正常打开编辑。XMind MCP（https://app.xmind.com/api/mcp ）完成 OAuth 授权后可切换为 MCP 方式管理。
