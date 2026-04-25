# Undercover - Multi-Agents Social Deduction Game

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

基于 LangGraph 的多智能体社交推理游戏，支持 AI 玩家与真人玩家共同参与。

[English](#overview) | [中文](#项目概述)

---

## Overview

Undercover is a multi-agent social deduction game built with [LangGraph](https://langchain-ai.github.io/langgraph/). The game features:

- **AI-powered agents** - Each player is controlled by an LLM-based agent with unique personality and strategy
- **Human player support** - Join games through WebSocket connection and play alongside AI agents
- **Real-time gameplay** - WebSocket-based communication for live game updates
- **LangGraph workflow** - Game state machine built with LangGraph for robust agent orchestration

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   React UI      │◄────┤  FastAPI Server  │◄────┤  LangGraph      │
│   (Frontend)    │     │  (WebSocket/REST)│     │  (Game Engine)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  AI/Human Agents │
                        └──────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+ (for frontend)
- OpenAI API key

### Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd undercover
```

2. **Set up Python environment**

```bash
uv sync
```

3. **Configure environment**

```bash
cp .env.template .env
# Edit .env and add your OpenAI API key
```

4. **Run the server**

```bash
python server.py
```

The server will start at `http://localhost:8124`.

### Frontend Development

```bash
cd ui-web/frontend
npm install
npm start
```

The frontend will be available at `http://localhost:3000`.

## Game Rules

1. **Roles**: Players are assigned as either Civilians or Undercover agents
2. **Words**: Civilians receive one word; Undercover agents receive a similar but different word
3. **Rounds**: Players take turns describing their word without revealing it directly
4. **Voting**: After each round, players vote to eliminate who they suspect is the Undercover agent
5. **Winning**:
   - Civilians win when all Undercover agents are eliminated
   - Undercover agents win when they equal or outnumber Civilians

## Configuration

Edit `config.yaml` to customize:

- **Player count**: 4-8 players (mix of AI and human)
- **Vocabulary**: Word pairs for the game
- **Game settings**: Max rounds, player names, etc.

```yaml
game:
  player_count: 6
  vocabulary:
    - ["Shakespeare", "Dumas"]
    - ["Sun", "Moon"]
```

## Technologies

- **Backend**: Python, FastAPI, LangGraph, LangChain
- **Frontend**: React, WebSocket
- **AI Models**: OpenAI GPT (configurable)

## License

[MIT License](LICENSE)

---

## 项目概述

Undercover 是一个基于 [LangGraph](https://langchain-ai.github.io/langgraph/) 构建的多智能体社交推理游戏，支持 AI 玩家与真人玩家共同参与。

## 核心特性

- **AI 驱动的智能体** - 每个玩家由基于 LLM 的智能体控制，拥有独特的个性和策略
- **真人玩家支持** - 通过 WebSocket 连接加入游戏，与 AI 智能体一起游戏
- **实时游戏** - 基于 WebSocket 的通信，提供实时游戏更新
- **LangGraph 工作流** - 使用 LangGraph 构建的游戏状态机，实现可靠的智能体编排

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+（前端需要）
- OpenAI API 密钥

### 安装步骤

```bash
# 克隆仓库
git clone <repository-url>
cd undercover

# 安装依赖
uv sync

# 配置环境
cp .env.template .env
# 编辑 .env 文件，添加 OpenAI API 密钥

# 启动服务器
python server.py
```

### 前端开发

```bash
cd ui-web/frontend
npm install
npm start
```

访问 `http://localhost:3000`。

## 游戏规则

1. **角色分配**：玩家被分配为平民或卧底
2. **词语分发**：平民获得一个词语；卧底获得相似但不同的词语
3. **轮流描述**：玩家轮流描述自己的词语，不能直接说出
4. **投票淘汰**：每轮结束后，玩家投票淘汰怀疑的卧底
5. **获胜条件**：
   - 平民淘汰所有卧底获胜
   - 卧底人数等于或多于平民时获胜

## 技术栈

- **后端**: Python, FastAPI, LangGraph, LangChain
- **前端**: React, WebSocket
- **AI 模型**: OpenAI GPT（可配置）

## 许可证

[MIT 许可证](LICENSE)
