import { useEffect, useState, useRef } from 'react';

type Player = {
  hp: number;
  mp: number;
  money: number;
  is_fog: number;
  is_dream: number;
  hand: number[];
  active_miracles: number[];
};

type GameState = {
  current_turn: number;
  players: Player[];
};

const CARD_NAMES: Record<number, string> = {
  0: '',
  1: '木の剣',
  2: '革の鎧',
  3: '回復'
};

function App() {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('Connected to visualizer server');
      setLog(prev => [...prev, 'System: Connected to server']);
    };

    ws.onmessage = (event) => {
      try {
        const state = JSON.parse(event.data);
        setGameState(state);
        setLog(prev => [...prev, `Turn ${state.current_turn} State updated.`]);
      } catch (e) {
        console.error('Failed to parse message', e);
      }
    };

    ws.onclose = () => {
      setLog(prev => [...prev, 'System: Disconnected']);
    };

    return () => {
      ws.close();
    };
  }, []);

  const handleStep = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send('step');
    }
  };

  if (!gameState) {
    return <div style={{padding: 20}}>Loading Game State from Server... (Is visualize_server.py running?)</div>;
  }

  const opp = gameState.players[1];
  const me = gameState.players[0];

  const renderCard = (id: number, idx: number) => {
    if (id === 0) return null;
    return <div key={idx} className="card">{CARD_NAMES[id] || `ID:${id}`}</div>;
  };

  return (
    <div className="game-container">
      {/* Opponent Area */}
      <div className="player-area opponent">
        <div>
          <div className="stats">
            Opponent (P2) <br/>
            <span>HP: {opp.hp}</span>
            <span>MP: {opp.mp}</span>
            <span>円: {opp.money}</span>
          </div>
          <div>Active Miracles: {opp.active_miracles.filter(id => id !== 0).map(id => CARD_NAMES[id] || id).join(', ')}</div>
        </div>
      </div>

      {/* Battle Log Area */}
      <div className="battle-log">
        <button className="button-step" onClick={handleStep}>Next Step (Random Actions)</button>
        {log.slice(-10).map((l, i) => <div key={i}>{l}</div>)}
      </div>

      {/* My Area */}
      <div className="player-area me">
        <div>
          <div className="stats">
            You (P1) <br/>
            <span>HP: {me.hp}</span>
            <span>MP: {me.mp}</span>
            <span>円: {me.money}</span>
          </div>
          <div>Active Miracles: {me.active_miracles.filter(id => id !== 0).map(id => CARD_NAMES[id] || id).join(', ')}</div>
          <div className="hand-area">
            {me.hand.map((id, idx) => renderCard(id, idx))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
