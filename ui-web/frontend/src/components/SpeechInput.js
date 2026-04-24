import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Speech Input Component
 * Allows human player to input their speech during speaking phase
 */
function SpeechInput({ prompt, onSubmit, disabled }) {
  const { t } = useTranslation();
  const [content, setContent] = useState('');
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

  const handleSubmit = (e) => {
    e.preventDefault();
    if (content.trim() && !disabled) {
      onSubmit(content.trim());
      setContent('');
    }
  };

  if (!prompt) return null;

  return (
    <div className="speech-input">
      <div className="speech-card">
        <h3>{'玩家的发言'}</h3>

        <div className="prompt-info">
          <div className="timer">
            <span className="label">{'剩余时间'}:</span>
            <span className={`time ${timeLeft < 60 ? 'warning' : ''}`}>
              {formatTime(timeLeft)}
            </span>
          </div>
        </div>

        {prompt.completed_speeches?.length > 0 && (
          <div className="previous-speeches">
            <ul>
              {prompt.completed_speeches.map((speech, idx) => (
                <li key={idx}>
                  <span className="speaker">{speech.player}:</span>
                  <span className="content">{speech.content}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder={'输入你的发言...'}
              disabled={disabled || timeLeft === 0}
              rows={4}
              maxLength={200}
              autoFocus
            />
            <div className="char-count">{content.length}/200</div>
          </div>

          <button
            type="submit"
            className="btn-primary"
            disabled={!content.trim() || disabled || timeLeft === 0}
          >
            {disabled ? '已提交': '提交发言'}
          </button>
        </form>

        <div className="speech-tips">
          <p>{'提示：描述不要太明显，否则卧底会猜到词！'}</p>
          <p>{'也不要太模糊，否则会被其他平民怀疑。'}</p>
        </div>
      </div>
    </div>
  );
}

export default SpeechInput;
