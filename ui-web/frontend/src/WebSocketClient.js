/**
 * WebSocket Client for Human Player
 * Connects to the backend WebSocket server for real-time game interaction
 */

class WebSocketClient {
  constructor() {
    this.ws = null;
    this.playerId = null;
    this.connected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.listeners = {};
  }

  /**
   * Connect to WebSocket server
   * @param {string} playerId - The player ID assigned by backend
   * @param {string} serverUrl - WebSocket server URL (optional)
   */
  connect(playerId, gameId = null, serverUrl = null) {
    this.playerId = playerId;
    this.gameId = gameId || 'default';
    const wsUrl = serverUrl || process.env.REACT_APP_WS_URL || 'ws://localhost:8124';
    const fullUrl = `${wsUrl}/ws/play/${this.gameId}/${playerId}`;

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(fullUrl);

        this.ws.onopen = () => {
          console.log(`WebSocket connected for player ${playerId}`);
          this.connected = true;
          this.reconnectAttempts = 0;
          this._startPingInterval();
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('WebSocket received:', data);
            this._handleMessage(data);
          } catch (err) {
            console.error('Failed to parse WebSocket message:', err);
          }
        };

        this.ws.onclose = () => {
          console.log('WebSocket closed');
          this.connected = false;
          this._stopPingInterval();
          this._emit('disconnected', {});
          this._attemptReconnect();
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this._emit('error', { message: 'Connection error' });
          reject(error);
        };
      } catch (err) {
        reject(err);
      }
    });
  }

  /**
   * Disconnect from server
   */
  disconnect() {
    this._stopPingInterval();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
  }

  /**
   * Submit speech
   * @param {string} content - Speech content
   */
  submitSpeech(content) {
    this._send({
      type: 'speak',
      content: content
    });
  }

  /**
   * Submit vote
   * @param {string} target - Target player ID to vote for
   */
  submitVote(target) {
    this._send({
      type: 'vote',
      target: target
    });
  }

  /**
   * Add event listener
   * @param {string} event - Event type: 'connected', 'prompt_speak', 'prompt_vote', 'game_event', 'error', 'disconnected'
   * @param {function} callback - Event handler
   */
  on(event, callback) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
  }

  /**
   * Remove event listener
   */
  off(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    }
  }

  /**
   * Handle incoming message
   */
  _handleMessage(data) {
    const { type } = data;

    switch (type) {
      case 'connected':
        this._emit('connected', data);
        break;
      case 'prompt_speak':
        this._emit('prompt_speak', data);
        break;
      case 'prompt_vote':
        this._emit('prompt_vote', data);
        break;
      case 'game_event':
        this._emit('game_event', data);
        break;
      case 'ack':
        this._emit('ack', data);
        break;
      case 'error':
        this._emit('error', data);
        break;
      default:
        console.log('Unknown message type:', type);
    }
  }

  /**
   * Emit event to listeners
   */
  _emit(event, data) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(callback => {
        try {
          callback(data);
        } catch (err) {
          console.error('Error in event listener:', err);
        }
      });
    }
  }

  /**
   * Send message to server
   */
  _send(data) {
    if (this.ws && this.connected) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.error('WebSocket not connected');
    }
  }

  /**
   * Start ping interval to keep connection alive
   */
  _startPingInterval() {
    this.pingInterval = setInterval(() => {
      if (this.connected) {
        this._send({ type: 'ping' });
      }
    }, 30000); // Ping every 30 seconds
  }

  /**
   * Stop ping interval
   */
  _stopPingInterval() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  /**
   * Attempt to reconnect
   */
  _attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached');
      this._emit('error', { message: 'Connection lost. Please refresh the page.' });
      return;
    }

    this.reconnectAttempts++;
    console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);

    setTimeout(() => {
      if (this.playerId) {
        this.connect(this.playerId).catch(() => {
          // Reconnect failed, will try again
        });
      }
    }, 2000 * this.reconnectAttempts); // Exponential backoff
  }
}

export default WebSocketClient;
