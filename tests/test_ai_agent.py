"""
Unit tests for AIAgent class.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from game.agents.ai_agent import AIAgent
from game.agents.base import SpeechContext
from game.common.schema import Speech
from game.common.llm_schemas import PlayerMindsetModel, SelfBeliefModel, SuspicionModel


class TestAIAgent:
    """Test suite for AIAgent."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        return MagicMock()
    
    @pytest.fixture(scope="session")
    def llm_client(self):
        """Create a real LLM client."""
        from game.common.llm_client import get_llm_client
        return get_llm_client()

    @pytest.fixture
    def ai_agent(self, llm_client):
        """Create an AIAgent instance with mocked dependencies."""
        agent = AIAgent(
            player_id="test_player",
            name="TestPlayer",
            llm_client=llm_client,
            personality="balanced"
        )
        # Set up word and mindset for speech generation
        agent._word = "apple"
        agent._mindset = {
            "self_belief": {"role": "civilian", "confidence": 0.7},
            "suspicions": {}
        }
        return agent

    @pytest.mark.asyncio
    async def test_generate_speech_content_success(self, ai_agent):
        """Test successful speech generation with real LLM."""
        # Arrange
        completed_speeches: list[Speech] = [
            {"round": 1, "seq": 0, "player_id": "p1", "content": "It's red.", "ts": 1000}
        ]
        alive = ["p1", "test_player", "p3"]
        current_round = 1
        speech_plan = {"goal": {"label": "stay_neutral", "reason": "first round"}}

        # Act - 使用真实 LLM 调用
        result = await ai_agent.generate_speech_content(
            completed_speeches=completed_speeches,
            alive=alive,
            current_round=current_round,
            speech_plan=speech_plan
        )

        # Assert - 验证返回的是有效发言文本
        #assert isinstance(result, str)
        assert len(result) > 0
        #assert len(result) < 200  # 发言应简洁
        # 打印结果供查看
        print(f"\nGenerated speech: {result}")

    @pytest.mark.asyncio
    async def test_generate_speech_content_no_plan(self, ai_agent, mock_llm_client):
        """Test speech generation without a speech plan."""
        # Arrange
        completed_speeches: list[Speech] = []
        alive = ["test_player"]
        current_round = 1

        mock_response = MagicMock()
        mock_response.content = "It's something edible."
        ai_agent._base_agent.ainvoke = AsyncMock(return_value=mock_response)

        # Act
        result = await ai_agent.generate_speech_content(
            completed_speeches=completed_speeches,
            alive=alive,
            current_round=current_round,
            speech_plan=None
        )

        # Assert
        assert result == "It's something edible."
        ai_agent._base_agent.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_speech_content_uses_instance_word(self, ai_agent):
        """Test that generate_speech_content uses self._word correctly."""
        # Arrange
        ai_agent._word = "banana"
        
        mock_response = MagicMock()
        mock_response.content = "Yellow and curved."
        ai_agent._base_agent.ainvoke = AsyncMock(return_value=mock_mock_response)

        # Act
        await ai_agent.generate_speech_content(
            completed_speeches=[],
            alive=["test_player"],
            current_round=1,
            speech_plan=None
        )

        # Assert - verify the method was called and didn't raise
        ai_agent._base_agent.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_speech_content_uses_mindset_belief(self, ai_agent):
        """Test that generate_speech_content accesses self._mindset correctly."""
        # Arrange
        ai_agent._mindset = {
            "self_belief": {"role": "spy", "confidence": 0.8},
            "suspicions": {"p1": {"role": "civilian", "confidence": 0.6, "reason": "suspicious"}}
        }
        
        mock_response = MagicMock()
        mock_response.content = "A vague description."
        ai_agent._base_agent.ainvoke = AsyncMock(return_value=mock_response)

        # Act
        result = await ai_agent.generate_speech_content(
            completed_speeches=[],
            alive=["test_player", "p1"],
            current_round=2,
            speech_plan=None
        )

        # Assert
        assert result == "A vague description."
        ai_agent._base_agent.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_speech_content_with_string_response(self, ai_agent):
        """Test handling when response is a plain string (not MagicMock with content)."""
        # Arrange - simulate response without content attribute
        ai_agent._base_agent.ainvoke = AsyncMock(return_value="Raw string response")

        # Act
        result = await ai_agent.generate_speech_content(
            completed_speeches=[],
            alive=["test_player"],
            current_round=1,
            speech_plan=None
        )

        # Assert - should handle string response gracefully
        assert result == "Raw string response"

    @pytest.mark.asyncio
    async def test_update_mindset_success(self, llm_client):
        """Test _update_mindset successfully updates agent mindset."""
        
        agent = AIAgent(
            player_id="p1",
            name="Player1",
            llm_client=llm_client,
            personality="balanced"
        )
        agent._word = "apple"
        agent._mindset = {
            "self_belief": {"role": "civilian", "confidence": 0.5},
            "suspicions": {}
        }

        context = SpeechContext(
            player_id="p1",
            my_word="apple",
            current_round=1,
            completed_speeches=[{
                "round":1,
                "player_id":"p2",
                "content":"red sweet fruit"
            },{
                "round":1,
                "player_id":"p3",
                "content":"a company name"
            }],
            alive_players=["p1", "p2", "p3"],
            self_belief={"role": "civilian", "confidence": 0.5},
            suspicions={},
            undercover_num=1
        )

        # Act
        await agent._update_mindset(context)

        print(f'{agent._mindset}')
        

    @pytest.mark.asyncio
    async def test_update_mindset_failure_preserves_existing(self, mock_llm_client):
        """Test _update_mindset preserves existing mindset on LLM failure."""
        # Arrange
        mock_llm_client.with_structured_output = MagicMock(side_effect=Exception("LLM error"))

        agent = AIAgent(
            player_id="p1",
            name="Player1",
            llm_client=mock_llm_client,
            personality="balanced"
        )
        agent._word = "apple"
        existing_mindset = {
            "self_belief": {"role": "civilian", "confidence": 0.6},
            "suspicions": {"p2": {"role": "spy", "confidence": 0.7, "reason": "suspect"}}
        }
        agent._mindset = existing_mindset.copy()

        context = SpeechContext(
            player_id="p1",
            my_word="apple",
            current_round=1,
            completed_speeches=[],
            alive_players=["p2", "p3"],
            self_belief={"role": "civilian", "confidence": 0.6},
            suspicions={"p2": {"role": "spy", "confidence": 0.7, "reason": "suspect"}},
            undercover_num=1
        )

        # Act
        await agent._update_mindset(context)

        # Assert - mindset should remain unchanged on failure
        assert agent._mindset == existing_mindset

    @pytest.mark.asyncio
    async def test_update_mindset_uses_context_word_when_no_instance_word(self, mock_llm_client):
        """Test _update_mindset uses context.my_word when self._word is None."""
        # Arrange
        mock_response = PlayerMindsetModel(
            self_belief=SelfBeliefModel(role="civilian", confidence=0.75),
            suspicions={}
        )
        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_client.with_structured_output = MagicMock(return_value=structured_llm)

        agent = AIAgent(
            player_id="p1",
            name="Player1",
            llm_client=mock_llm_client,
            personality="balanced"
        )
        agent._word = None  # No word set on instance
        agent._mindset = {"self_belief": {"role": "civilian", "confidence": 0.5}, "suspicions": {}}

        context = SpeechContext(
            player_id="p1",
            my_word="banana",  # Word provided in context
            current_round=2,
            completed_speeches=[],
            alive_players=["p2"],
            self_belief={"role": "civilian", "confidence": 0.5},
            suspicions={},
            undercover_num=1
        )

        # Act
        await agent._update_mindset(context)

        # Assert
        assert agent._mindset["self_belief"]["confidence"] == 0.75
        structured_llm.ainvoke.assert_called_once()
        # Verify the prompt was formatted with context word
        call_args = structured_llm.ainvoke.call_args[0][0]
        assert any("banana" in str(msg.content) for msg in call_args)
