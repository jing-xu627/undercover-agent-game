import React from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Game Events Component
 * Displays game events like speeches, eliminations, round changes
 */
function GameEvents({ events }) {
  const { t } = useTranslation();

  const formatEvent = (event) => {
    const { type, event_type, data, timestamp } = event;

    switch (event_type || type) {
      case 'speech':
        return {
          icon: '💬',
          className: 'event-speech',
          content: (
            <>
              <strong>{data.player_id || data.player}</strong>
              <span className="event-action">{t('said') || '说'}</span>
              <span className="event-content">"{data.content}"</span>
            </>
          )
        };

      case 'vote_reveal':
        return {
          icon: '🗳️',
          className: 'event-vote',
          content: (
            <>
              <span className="event-action">{t('votingResults') || '投票结果'}:</span>
              {Object.entries(data.votes || {}).map(([voter, target]) => (
                <span key={voter} className="vote-result">
                  {voter} → {target}
                </span>
              ))}
            </>
          )
        };

      case 'elimination':
        return {
          icon: '💀',
          className: 'event-elimination',
          content: (
            <>
              <strong>{data.eliminated_player}</strong>
              <span className="event-action">{t('wasEliminated') || '被淘汰'}</span>
              {data.was_spy !== undefined && (
                <span className={`role-reveal ${data.was_spy ? 'spy' : 'civilian'}`}>
                  {data.was_spy
                    ? (t('wasTheSpy') || '(是卧底!)')
                    : (t('wasCivilian') || '(是平民)')}
                </span>
              )}
            </>
          )
        };

      case 'new_round':
        return {
          icon: '🔄',
          className: 'event-new-round',
          content: (
            <>
              <span className="event-action">{t('newRoundStarted') || '新回合开始'}</span>
              <strong>{t('round') || '回合'} {data.round}</strong>
            </>
          )
        };

      case 'game_end':
        return {
          icon: '🏆',
          className: 'event-game-end',
          content: (
            <>
              <span className="event-action">{t('gameOver') || '游戏结束'}</span>
              <strong className={data.winner === 'spy' ? 'spy-wins' : 'civilians-win'}>
                {data.winner === 'spy'
                  ? (t('spyWins') || '卧底胜利!')
                  : (t('civiliansWin') || '平民胜利!')}
              </strong>
              {data.spy_player && (
                <div className="spy-reveal">
                  <span className="spy-label">{t('theSpyWas') || '卧底是'}:</span>
                  <strong className="spy-name">{data.spy_player}</strong>
                </div>
              )}
              {data.civilian_word && data.spy_word && (
                <div className="words-reveal">
                  <div className="word-reveal-item">
                    <span className="word-label">{t('civilianWord') || '平民词'}:</span>
                    <strong className="word-value civilian">{data.civilian_word}</strong>
                  </div>
                  <div className="word-reveal-item">
                    <span className="word-label">{t('spyWord') || '卧底词'}:</span>
                    <strong className="word-value spy">{data.spy_word}</strong>
                  </div>
                </div>
              )}
            </>
          )
        };

      default:
        return {
          icon: '•',
          className: 'event-generic',
          content: <span>{JSON.stringify(data)}</span>
        };
    }
  };

  if (!events || events.length === 0) {
    return (
      <div className="game-events empty">
        <p>{'等待游戏开始...'}</p>
      </div>
    );
  }

  return (
    <div className="game-events">
      <h4>{t('gameLog') || '游戏日志'}</h4>
      <div className="events-list">
        {events.map((event, index) => {
          const formatted = formatEvent(event);
          const time = event.timestamp
            ? new Date(event.timestamp).toLocaleTimeString()
            : '';

          return (
            <div key={index} className={`event-item ${formatted.className}`}>
              <span className="event-icon">{formatted.icon}</span>
              <span className="event-time">{time}</span>
              <span className="event-body">{formatted.content}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default GameEvents;
