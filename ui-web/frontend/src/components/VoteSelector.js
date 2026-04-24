import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Vote Selector Component
 * Allows human player to vote for a player to eliminate
 */
function VoteSelector({ prompt, onSubmit, disabled }) {
  const { t } = useTranslation();
  const [selectedTarget, setSelectedTarget] = useState(null);
  const [timeLeft, setTimeLeft] = useState(prompt?.timeout_seconds || 300);

  // Countdown timer
  useEffect(() => {
    if (!prompt || disabled) return;

    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [prompt, disabled]);

  // Format time display
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleSubmit = () => {
    if (selectedTarget && !disabled) {
      onSubmit(selectedTarget);
    }
  };

  if (!prompt) return null;

  const { alive_players = [], suspicions = {} } = prompt;

  return (
    <div className="vote-selector">
      <div className="vote-card">
        <h3>{'投票阶段'}</h3>

        <div className="timer">
          <span className="label">{'剩余时间'}:</span>
          <span className={`time ${timeLeft < 60 ? 'warning' : ''}`}>
            {formatTime(timeLeft)}
          </span>
        </div>

        <p className="vote-instruction">
          {'选择你认为的卧底投票淘汰：'}
        </p>

        <div className="player-list">
          {alive_players.map((playerId) => {
            const suspicion = suspicions[playerId];
            const isSelected = selectedTarget === playerId;

            return (
              <button
                key={playerId}
                className={`player-vote-card ${isSelected ? 'selected' : ''}`}
                onClick={() => !disabled && setSelectedTarget(playerId)}
                disabled={disabled}
              >
                <div className="player-name">{playerId}</div>
                {suspicion && (
                  <div className="suspicion-indicator">
                    <div
                      className="suspicion-bar"
                      style={{
                        width: `${(suspicion.suspicion_level || 0) * 100}%`,
                        backgroundColor: suspicion.is_primary_suspect ? '#e74c3c' : '#f39c12'
                      }}
                    />
                    <span className="suspicion-level">
                      {Math.round((suspicion.suspicion_level || 0) * 100)}%
                    </span>
                  </div>
                )}
                {isSelected && (
                  <div className="selected-indicator">✓</div>
                )}
              </button>
            );
          })}
        </div>

        {selectedTarget && (
          <div className="vote-confirmation">
            <p>
              {'你将投票给'}: <strong>{selectedTarget}</strong>
            </p>
            <button
              className="btn-primary"
              onClick={handleSubmit}
              disabled={disabled || timeLeft === 0}
            >
              {disabled
                ? ('投票已提交')
                : ('确认投票')}
            </button>
          </div>
        )}

        <div className="vote-tips">
          <p>{'提示：观察发言最可疑的玩家'}</p>
          <p>{'卧底通常会给出模糊或不相关的描述'}</p>
        </div>
      </div>
    </div>
  );
}

export default VoteSelector;
