import React, { useEffect, useState, useRef, useCallback } from 'react';
import './App.css';
import LangGraphClient from './LangGraphClient';
import WebSocketClient from './WebSocketClient';
import SpeechInput from './components/SpeechInput';
import VoteSelector from './components/VoteSelector';
import { useTranslation } from 'react-i18next';

function App() {
  const { t, i18n } = useTranslation();
  const [appMode, setAppMode] = useState('spectator'); // 'spectator' or 'human_player'
  const [gameState, setGameState] = useState({
    status: 'loading',
    players: [],
    completed_speeches: [],
    current_votes: {},
    winner: null,
    eliminated_players: [],
    current_round: 1
  });
  const [isGameRunning, setIsGameRunning] = useState(false);
  const [numPlayers, setNumPlayers] = useState(6);
  const [playerCountError, setPlayerCountError] = useState('');

  const langGraphClient = useRef(null);
  const conversationContainerRef = useRef(null);

  // Human player state
  const [wsClient] = useState(() => new WebSocketClient());
  const [humanPlayerId, setHumanPlayerId] = useState(null);
  const [humanGamePhase, setHumanGamePhase] = useState('waiting'); // waiting, speaking, voting, game_over
  const [humanMyWord, setHumanMyWord] = useState(null);
  const [humanIsSpy, setHumanIsSpy] = useState(false);
  const [humanCurrentRound, setHumanCurrentRound] = useState(1);
  const [speechPrompt, setSpeechPrompt] = useState(null);
  const [votePrompt, setVotePrompt] = useState(null);
  const [actionSubmitted, setActionSubmitted] = useState(false);
  const [gameId, setGameId] = useState(null);
  const [finalResult, setFinalResult] = useState(null);

  useEffect(() => {
    langGraphClient.current = new LangGraphClient();
    return () => {
      if (langGraphClient.current) {
        // Cleanup logic can be added here
      }
    };
  }, []);

  useEffect(() => {
    if (conversationContainerRef.current) {
      conversationContainerRef.current.scrollTop = conversationContainerRef.current.scrollHeight;
    }
  }, [gameState.completed_speeches]);

  // WebSocket event handlers for human player
  useEffect(() => {
    const handlePromptSpeak = (data) => {
      console.log('WebSocket: prompt_speak', data);
      setSpeechPrompt(data);
      setVotePrompt(null);
      setActionSubmitted(false);
      setHumanGamePhase('speaking');
      setHumanMyWord(data.my_word);
      setHumanCurrentRound(data.round);
    };

    const handlePromptVote = (data) => {
      console.log('WebSocket: prompt_vote', data);
      setVotePrompt(data);
      setSpeechPrompt(null);
      setActionSubmitted(false);
      setHumanGamePhase('voting');
      setHumanCurrentRound(data.round);
    };

    const handleGameEvent = (data) => {
      console.log('WebSocket: game_event', data);
      switch (data.event_type) {
        case 'new_round':
          setHumanCurrentRound(data.data?.round || humanCurrentRound);
          setHumanGamePhase('waiting');
          break;
        case 'game_end':
          setHumanGamePhase('game_over');
          break;
        case 'speech':
          const speaker = data.data?.player_id || data.data?.player;
          console.log(`Game event: speech from ${speaker}, human is ${humanPlayerId}`);
          if (speaker === humanPlayerId) {
            setHumanGamePhase(prev => prev === 'speaking' ? 'waiting' : prev);
          }
          break;
        default:
          break;
      }
    };

    wsClient.on('prompt_speak', handlePromptSpeak);
    wsClient.on('prompt_vote', handlePromptVote);
    wsClient.on('game_event', handleGameEvent);

    return () => {
      wsClient.off('prompt_speak', handlePromptSpeak);
      wsClient.off('prompt_vote', handlePromptVote);
      wsClient.off('game_event', handleGameEvent);
    };
  }, [wsClient, humanPlayerId, humanCurrentRound, humanGamePhase]);

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      wsClient.disconnect();
    };
  }, [wsClient]);

  const handleSpeechSubmit = useCallback((content) => {
    wsClient.submitSpeech(content);
    setActionSubmitted(true);
  }, [wsClient]);

  const handleVoteSubmit = useCallback((target) => {
    wsClient.submitVote(target);
    setActionSubmitted(true);
  }, [wsClient]);

  const startGame = async () => {
    console.log('=== startGame called ===');
    // alert('startGame called! Check console.');
    try {
      setIsGameRunning(true);

      // Auto-create human player
      const generatedPlayerId = `Player_${Date.now().toString().slice(-5)}`;
      const playerCount = numPlayers;
      const apiUrl = 'http://localhost:8124';
      console.log('Creating game with player:', generatedPlayerId);

      // Create game via REST API
      console.log('Fetching:', `${apiUrl}/games/create`);
      const response = await fetch(`${apiUrl}/games/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          player_count: playerCount,
          human_player_ids: [generatedPlayerId]
        })
      });
      console.log('Create game response:', response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Create game failed:', errorText);
        throw new Error('Failed to create game');
      }

      const data = await response.json();
      console.log('Game created:', data);
      const createdGameId = data.game_id;
      setGameId(createdGameId);
      setHumanPlayerId(generatedPlayerId);

      // Connect to WebSocket FIRST (before starting game)
      // This ensures HumanAgent is connected when speak() is called
      console.log('Connecting WebSocket:', generatedPlayerId, createdGameId);
      await wsClient.connect(generatedPlayerId, createdGameId, `ws://localhost:8124`);
      console.log('WebSocket connected');

      // Start the game (after WebSocket is connected)
      console.log('Starting game:', createdGameId);
      const startResponse = await fetch(`${apiUrl}/games/${createdGameId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      console.log('Start game response:', startResponse.status);
      if (!startResponse.ok) {
        const errorText = await startResponse.text();
        console.error('Start game failed:', errorText);
        throw new Error('Failed to start game');
      }

      // Poll game state instead of using stream
      const pollGameState = async () => {
        console.log('Starting game state polling...');
        let attempts = 0;
        const maxAttempts = 9000; 

        while (attempts < maxAttempts) {
          attempts++;
          try {
            const gameResponse = await fetch(`${apiUrl}/games/${createdGameId}`);
            if (gameResponse.ok) {
              const gameData = await gameResponse.json();
              console.log(`Poll ${attempts}:`, gameData.status, gameData.players);

              // Convert to UI state (using new game_info format)
              const gameInfo = gameData.game_info || {};
              const uiState = {
                status: gameInfo.game_phase || gameData.status,
                players: gameData.players || [],
                current_round: gameInfo.current_round || 1,
                completed_speeches: gameInfo.completed_speeches || [],
                current_votes: gameInfo.current_votes || {},
                winner: gameData.winner,
                eliminated_players: gameInfo.eliminated_players || [],
                your_word: gameInfo.your_word
              };
              setGameState(prev => ({ ...prev, ...uiState }));

              // Check if game finished
              if (gameData.status === 'finished' || gameData.status === 'error') {
                console.log('Game finished, stopping poll');
                // Fetch final result
                try {
                  const finalResponse = await fetch(`${apiUrl}/games/${createdGameId}/final_result`);
                  if (finalResponse.ok) {
                    const finalData = await finalResponse.json();
                    console.log('Final result:', finalData);
                    setFinalResult(finalData);
                  }
                } catch (err) {
                  console.error('Failed to fetch final result:', err);
                }
                break;
              }
            }
          } catch (err) {
            console.error('Poll error:', err);
          }
          await new Promise(r => setTimeout(r, 500));
        }
      };
      pollGameState();
    } catch (error) {
      console.error('Failed to start game:', error);
      setIsGameRunning(false);
      setGameState({
        status: 'error',
        players: [],
        completed_speeches: [],
        current_votes: {},
        winner: null,
        eliminated_players: [],
        current_round: 1
      });
    }
  };

  const restartGame = async () => {
    try {
      // Reset game state to initial loading state
      setGameState({
        status: '游戏初始化中',
        players: [],
        completed_speeches: [],
        current_votes: {},
        winner: null,
        eliminated_players: [],
        current_round: 1
      });

      // Stop the current game and reset backend
      setIsGameRunning(false);
      setFinalResult(null);
      await langGraphClient.current.resetGame();

      // Keep the custom words for the next game
      // The user can now see the start screen with their custom words preserved
    } catch (error) {
      console.error('Failed to restart game:', error);
      setIsGameRunning(false);
    }
  };

  const getPhaseDisplayName = (phase) => {
    const phaseMap = {
      'setup': t('phase_setup'),
      'speaking': t('phase_speaking'),
      'voting': t('phase_voting'),
      'result': t('phase_result')
    };
    return phaseMap[phase] || phase;
  };

  const getPhaseColor = (phase) => {
    const colorMap = {
      'setup': '#95a5a6',
      'speaking': '#38a169',
      'voting': '#e74c3c',
      'result': '#27ae60'
    };
    return colorMap[phase] || '#95a5a6';
  };

  // Helper to reorder players with human player first
  const getOrderedPlayers = () => {
    if (!humanPlayerId) return gameState.players;
    const otherPlayers = gameState.players.filter(p => p !== humanPlayerId);
    return [humanPlayerId, ...otherPlayers];
  };

  // Render human player UI based on phase
  const renderHumanPlayerUI = () => {
    if (!humanPlayerId) return null;
    if (gameState.eliminated_players?.includes(humanPlayerId)) return null;

    switch (humanGamePhase) {
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
        return null;
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <div className="game-header">
          <h1>{t('title')}</h1>
          {isGameRunning && (
            <div className="game-status">
              <div className="round-indicator">
                {t('round_indicator', { round: gameState.current_round || 1 })}
              </div>
              <div className="phase-indicator" style={{ backgroundColor: getPhaseColor(gameState.status) }}>
                {getPhaseDisplayName(gameState.status)}
              </div>
            </div>
          )}
        </div>

        {!isGameRunning && gameState.status === 'loading' && (
          <div className="welcome-screen">
            <div className="welcome-content">
              <h2>{t('welcome_title')}</h2>
              <p>{t('welcome_subtitle')}</p>
              <div className="game-settings">
                <div className="player-count-input">
                  <label htmlFor="player-count"><strong>{t('player_count_info')}</strong></label>
                  <input
                    id="player-count"
                    type="number"
                    min="4"
                    max="8"
                    value={numPlayers}
                    onChange={(e) => {
                      const value = parseInt(e.target.value, 10);
                      if (isNaN(value)) {
                        setNumPlayers('');
                        setPlayerCountError(t('player_count_invalid') || '请输入有效数字');
                      } else if (value < 4 || value > 8) {
                        setNumPlayers(value);
                        setPlayerCountError(t('player_count_range') || '玩家数量必须在4-8之间');
                      } else {
                        setNumPlayers(value);
                        setPlayerCountError('');
                      }
                    }}
                    disabled={isGameRunning}
                  />
                  {playerCountError && <span className="error-message">{playerCountError}</span>}
                </div>
              </div>
              <p>{t('welcome_instruction')}</p>
              <button
                className="welcome-start-button"
                onClick={startGame}
              >
                {t('start_game')}
              </button>
            </div>
          </div>
        )}

      </header>

      {/* Game layout outside header to use full page width */}
      <div className="game-layout" style={{ display: isGameRunning ? 'grid' : 'none' }}>
        <div className="players-panel">
          <h3>{t('players_list_title')}</h3>
          <div className="players-list">
            {getOrderedPlayers().map((playerId, index) => {
              const isEliminated = gameState.eliminated_players.includes(playerId);
              const assignedWord = playerId === humanPlayerId ? gameState.your_word :  t('role_unknown');
              const isHumanPlayer = playerId === humanPlayerId;

              return (
                <div
                  key={playerId}
                  className={`player-item ${isEliminated ? 'eliminated' : ''} ${isHumanPlayer ? 'human-player' : ''}`}
                >
                  <div className="player-avatar">
                    {isHumanPlayer ? '🎮' :
                     isEliminated ? '💀' : '👤'}
                  </div>
                  <div className="player-details">
                    <div className="player-name">
                      {playerId}
                      {isHumanPlayer && <span className="you-badge">{'你'}</span>}
                    </div>
                    {isHumanPlayer && (
                      <div className="player-word">
                        <strong>{t('word_label')}</strong> {assignedWord}
                      </div>
                    )}
                    <div className="player-status">
                      {isEliminated ? t('status_eliminated') : t('status_in_game')}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

        </div>

        <div className="conversation-panel">
          <h3>{t('conversation_history_title')}</h3>

          {/* Chat History - Always visible */}
          <div className="conversation-container" ref={conversationContainerRef}>
            {(() => {
              // Group speeches by round
              const speechesByRound = {};
              gameState.completed_speeches?.forEach(speech => {
                const round = speech.round || 1;
                if (!speechesByRound[round]) speechesByRound[round] = [];
                speechesByRound[round].push(speech);
              });

              const rounds = Object.keys(speechesByRound).sort((a, b) => a - b);

              return rounds.map(round => (
                <div key={round} className="round-section">
                  <div className="round-header">第 {round} 轮</div>
                  {speechesByRound[round].map((speech, idx) => (
                    <div key={idx} className="speech-entry">
                      <div className="speech-header">
                        <span className="speaker-name">{speech.player_id || speech.player}</span>
                      </div>
                      <div className="speech-content">{speech.content}</div>
                    </div>
                  ))}
                  
                </div>
              ));
            })()}
            {(!gameState.completed_speeches || gameState.completed_speeches.length === 0) && (
              <p className="empty-chat-message">{'等待发言...'}</p>
            )}
          </div>
        </div>

        <div className="human-interaction-panel">
          {/* Human player UI (role reveal, speech input, voting, game over) */}
          {humanPlayerId && renderHumanPlayerUI()}

          {/* Show votes after each round's speeches */}
          {gameState.current_votes && Object.keys(gameState.current_votes).length > 0 && (
            <div className="votes-panel">
              <div className="votes-title">{t('voting_results_title')}</div>
              <div className="votes-list">
                {Object.entries(gameState.current_votes).map(([voter, vote]) => (
                  <div key={voter} className="vote-item">
                    <span className="vote-voter">{voter}</span>
                    <span className="vote-arrow">{t('vote_target_label')}</span>
                    <span className="vote-target">{vote.target}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Game End Info Banner */}
          {gameState.status === 'result' && finalResult && (
            <div className="game-end-banner">
              <div className={`winner-announcement ${finalResult.winner === 'spies' ? '卧底胜利' : '平民胜利'}`}>
                {finalResult.winner === 'spies' ? t('spy_wins'): t('civilians_win')}
              </div>
              {finalResult.spies && finalResult.spies.length > 0 && (
                <div className="spy-reveal-info">
                  <span className="spy-reveal-label">卧底是:</span>
                  {finalResult.spies.map((playerName) => (
                    <strong key={playerName} className="spy-reveal-name">
                      {playerName}
                    </strong>
                  ))}
                </div>
              )}
              {finalResult.civilian_word && finalResult.spy_word && (
                <div className="words-reveal-info">
                  <div className="word-reveal-row">
                    <span className="word-reveal-label">{'平民词'}:</span>
                    <strong className="word-reveal-value civilian">{finalResult.civilian_word}</strong>
                  </div>
                  <div className="word-reveal-row">
                    <span className="word-reveal-label">{'卧底词'}:</span>
                    <strong className="word-reveal-value spy">{finalResult.spy_word}</strong>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
