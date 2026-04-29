import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import WebSocketClient from '../WebSocketClient';
import HumanPlayerLobby from './HumanPlayerLobby';
import SpeechInput from './SpeechInput';
import VoteSelector from './VoteSelector';
import GameEvents from './GameEvents';

/**
 * Human Player View
 * Main component for human player gameplay
 * Manages WebSocket connection and game state
 */
function HumanPlayerView() {
  const { t } = useTranslation();
  const [wsClient] = useState(() => new WebSocketClient());

  // Connection state
  const [connectionStatus, setConnectionStatus] = useState('disconnected'); // disconnected, connecting, connected
  const [connectionError, setConnectionError] = useState(null);

  // Game state
  const [playerId, setPlayerId] = useState(null);
  const [gamePhase, setGamePhase] = useState('lobby'); // lobby, waiting, speaking, voting, game_over
  const [myWord, setMyWord] = useState(null);
  const [isSpy, setIsSpy] = useState(false);
  const [currentRound, setCurrentRound] = useState(1);

  // Action prompts
  const [speechPrompt, setSpeechPrompt] = useState(null);
  const [votePrompt, setVotePrompt] = useState(null);
  const [actionSubmitted, setActionSubmitted] = useState(false);

  // Game events
  const [events, setEvents] = useState([]);

  // Setup WebSocket listeners
  useEffect(() => {
    const handleConnected = (data) => {
      setConnectionStatus('connected');
      setConnectionError(null);
      // Don't set phase to waiting yet
    };

    const handleDisconnected = () => {
      setConnectionStatus('disconnected');
      setConnectionError(t('connectionLost') || '连接已断开，请刷新页面重试');
    };

    const handlePromptSpeak = (data) => {
      setSpeechPrompt(data);
      setVotePrompt(null);
      setActionSubmitted(false);
      setGamePhase('speaking');
      setMyWord(data.my_word);
      setCurrentRound(data.round);
    };

    const handlePromptVote = (data) => {
      setVotePrompt(data);
      setSpeechPrompt(null);
      setActionSubmitted(false);
      setGamePhase('voting');
      setCurrentRound(data.round);
    };

    const handleGameEvent = (data) => {
      setEvents(prev => [...prev, data]);

      // Update phase based on event type
      switch (data.event_type) {
        case 'new_round':
          setCurrentRound(data.data?.round || currentRound);
          setGamePhase('waiting');
          break;
        case 'game_end':
          setGamePhase('game_over');
          break;
        case 'speech':
          // Check if it's our speech
          const speaker = data.data?.player_id || data.data?.player;
          if (speaker === playerId && gamePhase === 'speaking') {
            setGamePhase('waiting');
          }
          break;
        default:
          break;
      }
    };

    const handleError = (data) => {
      setConnectionError(data.message);
    };

    wsClient.on('connected', handleConnected);
    wsClient.on('disconnected', handleDisconnected);
    wsClient.on('prompt_speak', handlePromptSpeak);
    wsClient.on('prompt_vote', handlePromptVote);
    wsClient.on('game_event', handleGameEvent);
    wsClient.on('error', handleError);

    return () => {
      wsClient.off('connected', handleConnected);
      wsClient.off('disconnected', handleDisconnected);
      wsClient.off('prompt_speak', handlePromptSpeak);
      wsClient.off('prompt_vote', handlePromptVote);
      wsClient.off('game_event', handleGameEvent);
      wsClient.off('error', handleError);
    };
  }, [wsClient, t, playerId, currentRound, gamePhase]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsClient.disconnect();
    };
  }, [wsClient]);

  // Create game via API
  const handleCreateGame = useCallback(async (playerId, playerCount, apiUrl) => {
    setConnectionStatus('connecting');
    setConnectionError(null);

    try {
      // Create game via REST API
      const response = await fetch(`${apiUrl}/games/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          player_count: playerCount,
          human_player_ids: [playerId]
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create game');
      }

      const data = await response.json();
      const gameId = data.game_id;

      // Now join via WebSocket
      setPlayerId(playerId);
      await wsClient.connect(playerId, gameId, apiUrl.replace('http', 'ws'));
    } catch (err) {
      setConnectionStatus('disconnected');
      setConnectionError(err.message || t('connectionFailed') || '创建游戏失败');
    }
  }, [wsClient, t]);

  // Handle join game
  const handleJoin = useCallback(async (id, gameId, serverUrl) => {
    setPlayerId(id);
    setConnectionStatus('connecting');
    setConnectionError(null);

    try {
      await wsClient.connect(id, gameId, serverUrl);
    } catch (err) {
      setConnectionStatus('disconnected');
      setConnectionError(t('connectionFailed') || '连接失败，请检查服务器地址和玩家ID');
    }
  }, [wsClient, t]);

  // Handle speech submission
  const handleSpeechSubmit = useCallback((content) => {
    wsClient.submitSpeech(content);
    setActionSubmitted(true);
  }, [wsClient]);

  // Handle vote submission
  const handleVoteSubmit = useCallback((target) => {
    wsClient.submitVote(target);
    setActionSubmitted(true);
  }, [wsClient]);

  // Handle role reveal confirmation
  const handleRoleConfirm = useCallback(() => {
    setGamePhase('waiting');
  }, []);

  // Render based on game phase
  const renderContent = () => {
    switch (gamePhase) {
      case 'lobby':
        return (
          <HumanPlayerLobby
            onJoin={handleJoin}
            onCreateGame={handleCreateGame}
            connectionStatus={connectionStatus}
            error={connectionError}
          />
        );

      case 'speaking':
        return (
          <SpeechInput
            prompt={speechPrompt}
            onSubmit={handleSpeechSubmit}
            disabled={actionSubmitted}
          />
        );

      case 'voting':
        return (
          <VoteSelector
            prompt={votePrompt}
            onSubmit={handleVoteSubmit}
            disabled={actionSubmitted}
          />
        );

      case 'waiting':
      case 'game_over':
      default:
        return (
          <div className="waiting-view">
            <div className="waiting-card">
              <h3>
                {gamePhase === 'game_over'
                  ? (t('gameOver') || '游戏结束')
                  : (t('waitingForYourTurn') || '等待你的回合...')}
              </h3>
              {myWord && (
                <div className="word-reminder">
                  <span className="label">{t('yourWord') || '你的词'}:</span>
                  <span className="word">{myWord}</span>
                </div>
              )}
              <div className="round-info">
                {t('round') || '回合'}: {currentRound}
              </div>
            </div>
            <GameEvents events={events} />
          </div>
        );
    }
  };

  return (
    <div className="human-player-view">
      <header className="player-header">
        <h1>{t('whoIsSpy') || '谁是卧底'}</h1>
        <div className="player-info">
          {playerId && (
            <span className="player-id">
              {t('player') || '玩家'}: {playerId}
            </span>
          )}
          <span className={`connection-status ${connectionStatus}`}>
            {connectionStatus === 'connected' && '●'}
            {connectionStatus === 'connecting' && '○'}
            {connectionStatus === 'disconnected' && '○'}
          </span>
        </div>
      </header>

      <main className="player-content">
        {renderContent()}
      </main>
    </div>
  );
}

export default HumanPlayerView;
