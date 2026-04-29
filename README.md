# Undercover - Multi-Agents Social Deduction Game

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

Undercover is a multi-agent social deduction game built with [LangGraph](https://langchain-ai.github.io/langgraph/). The game features:

- **AI-powered agents** - Each player is controlled by an LLM-based agent with unique personality and strategy
- **Human player support** - Join games through WebSocket connection and play alongside AI agents
- **Real-time gameplay** - WebSocket-based communication for live game updates
- **LangGraph workflow** - Game state machine built with LangGraph for robust agent orchestration

## Architecture

```

┌─────────────────────────────────────────────────────────────────────────────────┐
│                                    API LAYER                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                        FastAPI Server                                     │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐   │  │
│  │  │ REST Routes  │  │  WebSocket   │  │   Game API   │  │  Static     │   │  │
│  │  │ - /games     │  │  Connection  │  │  Endpoints   │  │  Files      │   │  │
│  │  │ - /players   │  │  - Real-time │  │  - Create    │  │             │   │  │
│  │  │ - /config    │  │    updates   │  │  - Join      │  │             │   │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                GAME CORE LAYER                                 │
│  ┌─────────────────────────┐    ┌──────────────────────────────────────────┐   │
│  │   GameManager (Singleton)│   │        LangGraph Workflow                 │   │
│  │  ┌───────────────────┐ │   │  ┌────────┐   ┌────────┐   ┌──────────┐  │   │
│  │  │ - Game Sessions   │ │   │  │ Setup  │──►│ Speech │──►│ Voting   │  │   │
│  │  │ - Player Registry │ │   │  │ Phase  │   │ Phase  │   │ Phase    │  │   │
│  │  │ - State Checkers  │ │   │  └────────┘   └────────┘   └──────────┘  │   │
│  │  │ - WebSocket Msg   │ │   │       │            │            │        │   │
│  │  └───────────────────┘ │   │       ▼            ▼            ▼        │   │
│  │                        │   │  ┌──────────────────────────────────┐   │   │
│  │  ┌───────────────────┐ │   │  │         GameState                 │   │   │
│  │  │   Agent Factory   │ │   │  │  - players, phase, round         │   │   │
│  │  │ - Create AI Agent │─┼─┼─┼┼►│  │  - speeches, votes, eliminated   │   │   │
│  │  │ - Create Human    │ │   │  │  - winner, private states        │   │   │
│  │  │   Agent           │ │   │  └──────────────────────────────────┘   │   │
│  │  └───────────────────┘ │   └──────────────────────────────────────────┘   │
│  └─────────────────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  AGENT LAYER                                   │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────────┐    │
│  │      AI Agent (LLM-based)    │    │         Human Agent (WebSocket)      │    │
│  │  ┌───────────────────────┐  │    │  ┌───────────────────────────────┐  │    │
│  │  │  LangChain/LangGraph  │  │    │  │    WebSocket Message Handler   │  │    │
│  │  │  - System Prompt      │  │    │  │    - Send player messages      │  │    │
│  │  │  - Strategy Prompt    │  │    │  │    - Receive human input         │  │    │
│  │  │  - Memory/Context     │  │    │  │    - Timeout handling            │  │    │
│  │  └───────────────────────┘  │    │  └───────────────────────────────┘  │    │
│  │           │                 │    │            │                      │    │
│  │           ▼                 │    │            ▼                      │    │
│  │  ┌───────────────────────┐  │    │  ┌───────────────────────────────┐  │    │
│  │  │    Agent Tools        │  │    │  │      Game Event Handler        │  │    │
│  │  │  - generate_speech()  │  │    │  │  - on_your_turn()             │  │    │
│  │  │  - cast_vote()        │  │    │  │  - on_vote_requested()        │  │    │
│  │  │  - analyze_players()  │  │    │  │  - on_game_update()            │  │    │
│  │  └───────────────────────┘  │    │  └───────────────────────────────┘  │    │
│  │           │                 │    │                                     │    │
│  │           ▼                 │    │                                     │    │
│  │  ┌───────────────────────┐  │    │                                     │    │
│  │  │   LLM Client (OpenAI)  │  │    │                                     │    │
│  │  │   - GPT-4/GPT-3.5     │  │    │                                     │    │
│  │  │   - Configurable      │  │    │                                     │    │
│  │  └───────────────────────┘  │    │                                     │    │
│  └─────────────────────────────┘    └─────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              INFRASTRUCTURE LAYER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Config     │  │    Logger    │  │   Metrics    │  │  Checkpointer    │  │
│  │  (config.yaml)│  │  (structured)│  │  (game stats)│  │  (state persistence)│  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Game Initialization**: REST API → GameManager creates session → LangGraph workflow initialized
2. **Player Turn**: LangGraph triggers agent → AI generates speech / Human receives WebSocket notification
3. **State Updates**: LangGraph updates GameState → GameManager broadcasts via WebSocket → Client UI updates
4. **Voting Phase**: All agents/humans submit votes → LangGraph tallies → Elimination → Next round or Game End

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
   - Undercover agents win when they equal or more than Civilians

## Configuration

Edit `config.yaml` to customize:

- **Player count**: 4-8 players (mix of AI and human)
- **Vocabulary**: Word pairs for the game
- **Game settings**: Max rounds, player names, etc.

## Technologies

- **Backend**: Python, FastAPI, LangGraph, LangChain
- **Frontend**: React, WebSocket
- **AI Models**: OpenAI GPT (configurable)

## License

[MIT License](LICENSE)

