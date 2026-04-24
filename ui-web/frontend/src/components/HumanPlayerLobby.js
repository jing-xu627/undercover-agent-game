import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Human Player Lobby
 * Allows players to join a game by entering their player ID
 */
function HumanPlayerLobby({ onJoin, onCreateGame, connectionStatus, error }) {
  const { t } = useTranslation();
  const [playerId, setPlayerId] = useState('');
  const [gameId, setGameId] = useState('');
  const [serverUrl, setServerUrl] = useState('ws://localhost:8124');
  const [apiUrl, setApiUrl] = useState('http://localhost:8124');
  const [mode, setMode] = useState('join'); // 'join' or 'create'
  const [playerCount, setPlayerCount] = useState(6);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (playerId.trim()) {
      if (mode === 'join' && gameId.trim()) {
        onJoin(playerId.trim(), gameId.trim(), serverUrl);
      } else if (mode === 'create') {
        onCreateGame(playerId.trim(), playerCount, apiUrl);
      }
    }
  };

  return (
    <div className="human-player-lobby">
      <div className="lobby-card">
        <h2>{mode === 'join' ? (t('joinGame') || '加入游戏') : (t('createGame') || '创建游戏')}</h2>

        <div className="mode-toggle">
          <button type="button" className={mode === 'join' ? 'active' : ''} onClick={() => setMode('join')}>
            {t('joinExisting') || '加入游戏'}
          </button>
          <button type="button" className={mode === 'create' ? 'active' : ''} onClick={() => setMode('create')}>
            {t('createNew') || '创建游戏'}
          </button>
        </div>

        <p className="lobby-description">
          {mode === 'join'
            ? (t('joinDescription') || '输入游戏ID和您的玩家ID加入游戏。')
            : (t('createDescription') || '创建新游戏并作为人类玩家加入。')}
        </p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="playerId">{t('playerId') || '玩家ID'}</label>
            <input
              type="text"
              id="playerId"
              value={playerId}
              onChange={(e) => setPlayerId(e.target.value)}
              placeholder={t('enterPlayerId') || '输入您的玩家ID'}
              disabled={connectionStatus === 'connecting'}
              autoFocus
            />
          </div>

          {mode === 'join' && (
            <div className="form-group">
              <label htmlFor="gameId">{t('gameId') || '游戏ID'}</label>
              <input
                type="text"
                id="gameId"
                value={gameId}
                onChange={(e) => setGameId(e.target.value)}
                placeholder={t('enterGameId') || '输入游戏ID'}
                disabled={connectionStatus === 'connecting'}
              />
            </div>
          )}

          {mode === 'create' && (
            <div className="form-group">
              <label htmlFor="playerCount">{t('playerCount') || '玩家数量'}</label>
              <input
                type="number"
                id="playerCount"
                value={playerCount}
                onChange={(e) => setPlayerCount(parseInt(e.target.value) || 6)}
                min={3}
                max={8}
                disabled={connectionStatus === 'connecting'}
              />
            </div>
          )}

          {showAdvanced && (
            <>
              <div className="form-group">
                <label htmlFor="serverUrl">{t('serverUrl') || '服务器地址'}</label>
                <input
                  type="text"
                  id="serverUrl"
                  value={serverUrl}
                  onChange={(e) => setServerUrl(e.target.value)}
                  placeholder="ws://localhost:8124"
                  disabled={connectionStatus === 'connecting'}
                />
              </div>
              {mode === 'create' && (
                <div className="form-group">
                  <label htmlFor="apiUrl">{t('apiUrl') || 'API地址'}</label>
                  <input
                    type="text"
                    id="apiUrl"
                    value={apiUrl}
                    onChange={(e) => setApiUrl(e.target.value)}
                    placeholder="http://localhost:8124"
                    disabled={connectionStatus === 'connecting'}
                  />
                </div>
              )}
            </>
          )}

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn-primary"
            disabled={!playerId.trim() || (mode === 'join' && !gameId.trim()) || connectionStatus === 'connecting'}
          >
            {connectionStatus === 'connecting'
              ? (t('connecting') || '连接中...')
              : mode === 'join'
                ? (t('joinGame') || '加入游戏')
                : (t('createGame') || '创建游戏')}
          </button>
        </form>

        <button
          className="btn-link"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          {showAdvanced
            ? (t('hideAdvanced') || '隐藏高级选项')
            : (t('showAdvanced') || '显示高级选项')}
        </button>

        <div className="lobby-info">
          <h4>{t('howToPlay') || '游戏说明'}</h4>
          <ul>
            <li>{t('instruction1') || '连接到游戏后等待游戏开始'}</li>
            <li>{t('instruction2') || '轮到你发言时，输入你的描述'}</li>
            <li>{t('instruction3') || '投票阶段选择你认为的卧底'}</li>
            <li>{t('instruction4') || '观察其他玩家的发言找出卧底'}</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default HumanPlayerLobby;
