import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import './FloatingTerminal.css';

type HistoryItem = {
  id: number;
  type: 'command' | 'output' | 'error' | 'success' | 'prompt';
  text: string;
};



const PAGES: Record<string, string> = {
  'dashboard': '/dashboard',
  'wallets': '/wallets',
  'past-analyses': '/past-analyses',
  'diagnostics': '/diagnostics',
  'api': '/api',
  'support': '/support',
  'founders': '/founders',
};

export default function FloatingTerminal() {
  const [history, setHistory] = useState<HistoryItem[]>([
    { id: 0, type: 'output', text: 'Welcome to Vault OS v1.0.0.' },
    { id: 1, type: 'output', text: "Type 'help' or 'ls' to list pages." },
    { id: 2, type: 'output', text: "Usage: cd <page>" },
  ]);
  const [input, setInput] = useState('');
  const bodyRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);

  // Scroll to bottom on new history
  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [history]);

  const handleBodyClick = () => inputRef.current?.focus();

  const addLine = (prev: HistoryItem[], type: HistoryItem['type'], text: string): HistoryItem[] => [
    ...prev,
    { id: Date.now() + Math.random(), type, text },
  ];

  const handleCommand = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter') return;
    const cmd = input.trim();
    if (!cmd) return;


    // ── NORMAL MODE ───────────────────────────────────────────
    setHistory((prev) => addLine(prev, 'command', `root@vault:~ $ ${cmd}`));
    setInput('');

    const args = cmd.split(/\s+/);
    const mainCommand = args[0].toLowerCase();

    switch (mainCommand) {
      case 'help':
      case 'ls':
        setHistory((prev) =>
          addLine(prev, 'output',
            `Available pages:\n  ${Object.keys(PAGES).join('\n  ')}\n\nCommands:\n  cd <page>  — navigate (requires password)\n  ls / help  — list pages\n  logout     — sign out\n  clear      — clear terminal`
          )
        );
        break;

      case 'clear':
        setHistory([]);
        return;

      case 'logout':
        setHistory((prev) => addLine(prev, 'output', 'Signing out...'));
        setTimeout(() => {
          logout();
          navigate('/login');
        }, 600);
        break;

      case 'cd':
        if (args.length < 2) {
          setHistory((prev) => addLine(prev, 'error', 'cd: missing argument'));
        } else {
          const target = args[1].toLowerCase();
          if (PAGES[target]) {
            setHistory((prev) =>
              addLine(prev, 'success', `Navigating to ${target}...`)
            );
            setTimeout(() => navigate(PAGES[target]), 400);
          } else {
            setHistory((prev) =>
              addLine(prev, 'error', `cd: no such file or directory: ${target}`)
            );
          }
        }
        break;

      default:
        setHistory((prev) =>
          addLine(prev, 'error', `command not found: ${mainCommand}. Type 'help' for commands.`)
        );
    }
  };



  return (
    <div className="floating-terminal">
      {/* macOS title bar */}
      <div className="terminal-header">
        <div className="mac-controls">
          <div className="mac-btn close" title="Close" />
          <div className="mac-btn minimize" title="Minimize" />
          <div className="mac-btn maximize" title="Maximize" />
        </div>
        <div className="terminal-title">~/vault/terminal</div>
      </div>

      {/* Output history */}
      <div className="terminal-body" ref={bodyRef} onClick={handleBodyClick}>
        <div className="terminal-history">
          {history.map((item) => (
            <div key={item.id} className={`terminal-line ${item.type}`}>
              {item.text.split('\n').map((line, i) => (
                <div key={i}>{line}</div>
              ))}
            </div>
          ))}
        </div>

        {/* Input row */}
        <div className="terminal-input-row">
          <span className="terminal-prompt">root@vault:~ $</span>
          <input
            ref={inputRef}
            type="text"
            className="terminal-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleCommand}
            autoFocus
            spellCheck={false}
            autoComplete="off"
            placeholder="type a command..."
          />
        </div>
      </div>
    </div>
  );
}
