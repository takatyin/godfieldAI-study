import { useEffect, useState, useRef } from 'react';
import './App.css';

type Card = {
  id: number;
  name: string;
  type: string;
  element: string;
  attack_power?: number;
  defense_power?: number;
  price?: number;
  hidden?: boolean;
};

type LegalAction = {
  action_id: number;
  name: string;
  description: string;
};

type EventLogItem = {
  actor: number;
  event_type: number;
  card_id: number;
  card_name?: string;
  target_id: number;
  value: number;
  text: string;
};

type Observation = {
  player_id: number;
  hp_me: number;
  hp_opp: number | string;
  mp_me: number;
  mp_opp: number | string;
  money_me: number;
  money_opp: number | string;
  sickness_me: string;
  sickness_opp: string;
  guardian_me: string;
  guardian_opp: string;
  curses_me: string[];
  curses_opp: string[];
  hand: (Card | null)[];
  staged: Card[];
  opponent_hand: Card[];
  opponent_staged: Card[];
  pending_card: Card | null;
  legal_actions: LegalAction[];
  current_actor_id: number;
  current_phase: string;
  current_turn: number;
  is_done: boolean;
  is_apocalypse: boolean;
  event_log?: EventLogItem[];
  history_count?: number;
};

type ServerMessage = {
  p0_obs: Observation;
  p1_obs: Observation;
  current_actor_id: number;
  ai_enabled: boolean;
};

function App() {
  const [data, setData] = useState<ServerMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const [seed, setSeed] = useState<number>(42);
  const [battleLog, setBattleLog] = useState<EventLogItem[]>([]);
  const [activePopup, setActivePopup] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const logEndRef = useRef<HTMLDivElement | null>(null);

  const connect = () => {
    const ws = new WebSocket('ws://localhost:8000/ws');
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('Connected to server');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const msg: ServerMessage = JSON.parse(event.data);
        setData(msg);

        // Update battle log if p0_obs has event_log
        if (msg.p0_obs && msg.p0_obs.event_log) {
          const logs = msg.p0_obs.event_log;
          setBattleLog(logs);

          // Trigger animation popup for the most recent impactful event
          if (logs.length > 0) {
            const latest = logs[logs.length - 1];
            if (latest.event_type === 7) {
              setActivePopup('MISS!');
            } else if (latest.event_type === 8) {
              setActivePopup(latest.text);
            } else if (latest.event_type === 11 && latest.value >= 10) {
              setActivePopup(`-${latest.value} DAMAGED!`);
            } else if (latest.event_type === 10) {
              setActivePopup('REFLECTED!');
            }
          }
        }
      } catch (e) {
        console.error('Failed to parse websocket message', e);
      }
    };

    ws.onclose = () => {
      console.log('Disconnected, retrying in 2 seconds...');
      setConnected(false);
      setTimeout(connect, 2000);
    };
  };

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [battleLog]);

  useEffect(() => {
    if (activePopup) {
      const timer = setTimeout(() => setActivePopup(null), 1500);
      return () => clearTimeout(timer);
    }
  }, [activePopup]);

  const sendAction = (actionId: number) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'action', action_id: actionId }));
    }
  };

  const resetGame = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const newSeed = Math.floor(Math.random() * 100000);
      setSeed(newSeed);
      wsRef.current.send(JSON.stringify({ type: 'reset', seed: newSeed }));
    }
  };

  const toggleAI = (enabled: boolean) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'toggle_ai', ai_enabled: enabled }));
    }
  };

  if (!connected || !data) {
    return (
      <div style={{
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        background: '#0b0f19',
        color: '#fff',
        fontFamily: 'sans-serif'
      }}>
        <div style={{ fontSize: '1.5rem', fontWeight: 'bold', marginBottom: '16px' }}>
          GodField可視化サーバーに接続中...
        </div>
        <div style={{ color: '#64748b' }}>
          `python visualize_server.py` が起動しているか確認してください。
        </div>
      </div>
    );
  }

  const { p0_obs, p1_obs, current_actor_id, ai_enabled } = data;
  const isGameOver = p0_obs.is_done || p1_obs.is_done;

  const renderCard = (card: Card | null, index: number, isMe: boolean, obs: Observation) => {
    if (!card) {
      return (
        <div key={`empty-${index}`} className="card-item" style={{ opacity: 0.15, borderStyle: 'dashed' }}>
          <div style={{ fontSize: '0.65rem', color: '#94a3b8' }}>Slot {index}</div>
          <div style={{ textAlign: 'center', fontSize: '0.8rem', color: '#475569' }}>空</div>
        </div>
      );
    }

    if (card.hidden) {
      return (
        <div key={`hidden-${index}`} className="card-item hidden-card">
          <div className="card-back-icon">？</div>
          <div className="card-type">未知</div>
        </div>
      );
    }

    // Determine if card is playable
    // Playable if it is this player's turn and the index matches a legal hand selection action
    const legalSelectAction = obs.legal_actions.find(act => act.action_id === index);
    const isPlayable = isMe && current_actor_id === obs.player_id && !!legalSelectAction;

    return (
      <div
        key={`card-${index}-${card.id}`}
        className={`card-item elem-${card.element.toLowerCase()} ${isPlayable ? 'playable' : ''}`}
        onClick={() => isPlayable && sendAction(index)}
        title={isPlayable ? legalSelectAction?.description : ''}
      >
        <div className="card-name">{card.name}</div>
        <div className="card-footer">
          <span className="card-power">
            {card.type === 'weapon' && `攻${card.attack_power}`}
            {card.type === 'defense' && `防${card.defense_power}`}
            {card.type === 'miracle' && `奇`}
            {card.type === 'sundry' && `雑`}
          </span>
          <span className="card-type">
            {card.price}円
          </span>
        </div>
      </div>
    );
  };

  const renderPlayerPanel = (obs: Observation, isMe: boolean) => {
    const isMyTurn = current_actor_id === obs.player_id;
    
    // Categorize legal actions
    const nonCardActions = obs.legal_actions.filter(act => act.action_id >= 18 && act.action_id < 22);
    const numberActions = obs.legal_actions.filter(act => act.action_id >= 22);

    return (
      <div className={`player-column ${isMyTurn ? 'active-turn' : ''}`} style={{ position: 'relative' }}>
        
        {/* Game Over Panel on top of Column */}
        {isGameOver && isMe && (
          <div className="game-over-overlay">
            <div className="game-over-title">
              {(obs.hp_me <= 0 && obs.hp_opp <= 0) ? '引き分け' : (obs.hp_me <= 0 ? '敗 北' : (obs.hp_opp <= 0 ? '勝 利' : '引き分け'))}
            </div>
            <div className="game-over-desc">
              対戦が終了しました。
            </div>
            <button className="control-btn primary" onClick={resetGame}>もう一度遊ぶ</button>
          </div>
        )}

        <div className="player-header">
          <div className="player-name">
            {isMe ? 'あなた (プレイヤー0)' : '相手 (プレイヤー1)'}
            {isMyTurn && <span className="turn-badge">思考中</span>}
          </div>
        </div>

        {/* Stats */}
        <div className="status-panel">
          <div className="status-bar hp">
            <div className="status-label">HP</div>
            <div className="status-value">{obs.hp_me}</div>
          </div>
          <div className="status-bar mp">
            <div className="status-label">MP</div>
            <div className="status-value">{obs.mp_me}</div>
          </div>
          <div className="status-bar money">
            <div className="status-label">所持金</div>
            <div className="status-value">{obs.money_me}円</div>
          </div>
        </div>

        {/* Buffs & Curses */}
        <div className="buffs-curses">
          {obs.guardian_me !== 'なし' && (
            <span className="effect-badge guardian">守護神: {obs.guardian_me}</span>
          )}
          {obs.sickness_me !== 'なし' && (
            <span className="effect-badge sickness">病: {obs.sickness_me}</span>
          )}
          {obs.curses_me.map(c => (
            <span key={c} className="effect-badge curse">災: {c}</span>
          ))}
          {obs.curses_me.length === 0 && obs.sickness_me === 'なし' && obs.guardian_me === 'なし' && (
            <span style={{ fontSize: '0.8rem', color: '#475569' }}>状態異常・守護神なし</span>
          )}
        </div>

        {/* Hand Cards */}
        <div className="hand-container">
          <div className="section-title">手札 ({obs.hand.filter(c => c !== null).length}枚)</div>
          <div className="cards-grid">
            {obs.hand.map((card, idx) => renderCard(card, idx, isMe, obs))}
          </div>
        </div>

        {/* Staged Cards Row */}
        <div className="section-title" style={{ marginTop: '12px' }}>場に出しているカード</div>
        <div className="staged-row">
          {obs.staged.length > 0 ? (
            obs.staged.map((card, idx) => (
              <div key={`staged-${idx}`} className={`staged-card-mini elem-${card.element.toLowerCase()}`}>
                {card.name}
              </div>
            ))
          ) : (
            <div className="staged-placeholder">仮置きしているカードはありません</div>
          )}
        </div>

        {/* Opponent staged view (useful to see what is coming at me) */}
        <div className="section-title" style={{ marginTop: '12px' }}>対戦相手が場に出しているカード</div>
        <div className="staged-row">
          {obs.opponent_staged.length > 0 ? (
            obs.opponent_staged.map((card, idx) => (
              <div key={`opp-staged-${idx}`} className={`staged-card-mini elem-${card.element.toLowerCase()}`}>
                {card.name}
              </div>
            ))
          ) : (
            <div className="staged-placeholder">相手は場にカードを出していません</div>
          )}
        </div>

        {/* Interactive Action Buttons (Pray, Discard, Confirm etc) */}
        {isMyTurn && (isMe || !ai_enabled) && (
          <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div className="section-title">選択可能なアクション</div>
            
            <div className="action-buttons-list">
              {nonCardActions.map(act => {
                let btnClass = 'action-btn';
                if (act.action_id === 20) btnClass += ' pray';
                if (act.action_id === 21) btnClass += ' discard';
                if (act.action_id === 18 || act.action_id === 19) btnClass += ' confirm';

                return (
                  <button
                    key={act.action_id}
                    className={btnClass}
                    onClick={() => sendAction(act.action_id)}
                  >
                    {act.description}
                  </button>
                );
              })}
            </div>

            {numberActions.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div className="section-title" style={{ fontSize: '0.75rem' }}>両替数値の選択</div>
                <div className="number-grid">
                  {numberActions.map(act => (
                    <button
                      key={act.action_id}
                      className="number-btn"
                      onClick={() => sendAction(act.action_id)}
                    >
                      {act.action_id - 22}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // Get active phase details
  const activeObs = current_actor_id === 0 ? p0_obs : p1_obs;

  return (
    <div className="visualizer-root">
      
      {/* Top Header */}
      <header className="app-header">
        <div className="app-title">
          <h1>GodField Visualizer</h1>
          <span>AI Observation & Play Simulator</span>
        </div>
        
        <div className="game-controls">
          <div className="toggle-container">
            <input
              type="checkbox"
              id="aiToggle"
              checked={ai_enabled}
              onChange={(e) => toggleAI(e.target.checked)}
            />
            <label htmlFor="aiToggle" style={{ cursor: 'pointer', fontWeight: 'bold' }}>
              相手(P1)をAI操作にする
            </label>
          </div>
          
          <button className="control-btn" onClick={resetGame}>
            リセット
          </button>
        </div>

        <div className="server-status">
          <span className={`status-indicator ${connected ? 'connected' : ''}`} />
          {connected ? 'サーバー接続中' : 'オフライン'}
        </div>
      </header>

      {/* Main Panel grid */}
      <main className="dashboard-grid">
        
        {/* Player 0 Column */}
        {renderPlayerPanel(p0_obs, true)}

        {/* Center Game info column */}
        <section className="center-column">
          <div className="center-card vs-display">
            <div className="turn-display">ターン</div>
            <div className="turn-number">{p0_obs.current_turn}</div>
            
            <div className="turn-display">フェーズ</div>
            <div className="phase-name">
              {p0_obs.current_phase === 'PHASE_MAIN' && 'メインフェーズ'}
              {p0_obs.current_phase === 'PHASE_DEFENSE' && '防御フェーズ'}
              {p0_obs.current_phase === 'PHASE_MAIN_TARGET_SELECT' && '対象選択'}
              {p0_obs.current_phase === 'PHASE_GUARDIAN' && '守護神判定'}
              {p0_obs.current_phase === 'PHASE_MIRACLE_DEFENSE' && '奇跡防御'}
              {p0_obs.current_phase === 'PHASE_MIRACLE_PLUS' && '奇跡強化'}
              {p0_obs.current_phase === 'PHASE_ATTACK_PLUS' && '攻撃強化'}
              {p0_obs.current_phase === 'PHASE_BUY' && '取引(買い)'}
              {p0_obs.current_phase === 'PHASE_SELL_SELECT' && '取引(売り)'}
              {p0_obs.current_phase === 'PHASE_DISCARD' && '手札整理'}
              {p0_obs.current_phase === 'PHASE_EXCHANGE_HP' && 'HP両替'}
              {p0_obs.current_phase === 'PHASE_EXCHANGE_MP' && 'MP両替'}
              {p0_obs.current_phase === 'PHASE_END' && 'ターン終了処理'}
              {!['PHASE_MAIN', 'PHASE_DEFENSE', 'PHASE_MAIN_TARGET_SELECT', 'PHASE_GUARDIAN', 'PHASE_MIRACLE_DEFENSE', 'PHASE_MIRACLE_PLUS', 'PHASE_ATTACK_PLUS', 'PHASE_BUY', 'PHASE_SELL_SELECT', 'PHASE_DISCARD', 'PHASE_EXCHANGE_HP', 'PHASE_EXCHANGE_MP', 'PHASE_END'].includes(p0_obs.current_phase) && p0_obs.current_phase}
            </div>

            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div className="turn-display" style={{ marginBottom: '8px' }}>手番</div>
              <div style={{
                background: current_actor_id === 0 ? 'linear-gradient(135deg, #3b82f6, #60a5fa)' : 'linear-gradient(135deg, #a855f7, #c084fc)',
                padding: '4px 16px',
                borderRadius: '8px',
                fontWeight: 'bold',
                fontSize: '0.9rem'
              }}>
                P{current_actor_id} {current_actor_id === 0 ? '(あなた)' : '(相手)'}
              </div>
            </div>
          </div>

          {/* Pending card display */}
          <div className="center-card target-display">
            <div className="turn-display">保留中のカード / ターゲット</div>
            {activeObs.pending_card ? (
              <div className="pending-card-wrap">
                <div className={`card-item elem-${activeObs.pending_card.element.toLowerCase()}`}>
                  <div className="card-name">{activeObs.pending_card.name}</div>
                  <div className="card-footer">
                    <span className="card-power">
                      {activeObs.pending_card.type === 'weapon' && `攻${activeObs.pending_card.attack_power}`}
                      {activeObs.pending_card.type === 'defense' && `防${activeObs.pending_card.defense_power}`}
                      {activeObs.pending_card.type === 'miracle' && `奇`}
                      {activeObs.pending_card.type === 'sundry' && `雑`}
                    </span>
                    <span className="card-type">{activeObs.pending_card.price}円</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="pending-desc">保留中のカードはありません</div>
            )}
          </div>
          
          {/* Battle Log panel */}
          <div className="center-card battle-log-card">
            <div className="turn-display">バトルログ</div>
            <div className="battle-log-list">
              {battleLog.length > 0 ? (
                battleLog.map((item, idx) => {
                  let badgeClass = 'log-badge actor-' + item.actor;
                  let itemClass = 'log-item';
                  if (item.event_type === 7) itemClass += ' log-miss';
                  if (item.event_type === 8) itemClass += ' log-sick';
                  if (item.event_type === 11) itemClass += ' log-damage';
                  if (item.event_type === 12) itemClass += ' log-heal';

                  return (
                    <div key={`log-${idx}`} className={itemClass}>
                      <span className={badgeClass}>P{item.actor}</span>
                      <span className="log-text">{item.text}</span>
                    </div>
                  );
                })
              ) : (
                <div className="battle-log-empty">対戦ログはありません</div>
              )}
              <div ref={logEndRef} />
            </div>
          </div>

          {/* Popup Animation Overlay */}
          {activePopup && (
            <div className="event-popup-overlay">
              <div className="event-popup-content">{activePopup}</div>
            </div>
          )}

          <div className="center-card" style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div className="turn-display">ヘルプ＆遊び方</div>
            <div>
              1. 自分の手札から<strong>明るくハイライトされたカード</strong>をクリックすると、場に仮置き（Staging）できます。<br/><br/>
              2. 複数枚を仮置きできる場合、追加で他のハイライトカードを選べます。<br/><br/>
              3. アクション（相手を対象にする、自分を対象にする、確定など）を選択すると、プレイが確定しゲームが進みます。<br/><br/>
              4. 相手をAI操作にしている場合、相手の手番になると自動でプレイを行います。チェックを外すと2人プレイ（手動操作）が可能です。
            </div>
          </div>
        </section>

        {/* Player 1 Column */}
        {renderPlayerPanel(p1_obs, false)}

      </main>
    </div>
  );
}

export default App;
