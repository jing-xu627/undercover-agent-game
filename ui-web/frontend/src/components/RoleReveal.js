import React from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Role Reveal Component
 * Displays the player's assigned word and role information
 */
function RoleReveal({ word, isSpy, round, onConfirm }) {
  const { t } = useTranslation();

  return (
    <div className="role-reveal">
      <div className="role-card">
        <h2>{t('yourRole') || '你的身份'}</h2>

        <div className={`role-badge ${isSpy ? 'spy' : 'civilian'}`}>
          {isSpy
            ? (t('youAreSpy') || '你是卧底！')
            : (t('youAreCivilian') || '你是平民')}
        </div>

        <div className="word-display">
          <label>{t('yourWord') || '你的词'}</label>
          <div className="word">{word}</div>
        </div>

        <div className="role-instructions">
          {isSpy ? (
            <>
              <p>{t('spyInstruction1') || '你是卧底！你不知道平民的词是什么。'}</p>
              <p>{t('spyInstruction2') || '通过听其他人的描述来猜测平民的词。'}</p>
              <p>{t('spyInstruction3') || '描述时要小心，不要暴露你是卧底！'}</p>
            </>
          ) : (
            <>
              <p>{t('civilianInstruction1') || '你是平民。你的目标是找出卧底。'}</p>
              <p>{t('civilianInstruction2') || '描述你的词时要清晰，但也要小心卧底在听。'}</p>
              <p>{t('civilianInstruction3') || '观察谁的发言最可疑！'}</p>
            </>
          )}
        </div>

        <div className="round-info">
          {t('round') || '回合'}: {round}
        </div>

        <button className="btn-primary" onClick={onConfirm}>
          {t('iUnderstand') || '明白了'}
        </button>
      </div>
    </div>
  );
}

export default RoleReveal;
