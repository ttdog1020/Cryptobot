# PROJECT MEMORY – CRYPTO TRADING BOT (FULL VERSION, HYBRID SWING + SCALPING + ML CAPABLE)

This file is the long-term memory for the AI coding agent working inside this repository.

The instructions below describe:
- The purpose of the project
- The desired architecture
- Coding standards and conventions
- Trading & risk management rules
- Logging / PnL formatting expectations
- How to handle future “mods” and iterations
- Development workflow expectations
- User preferences

The AI must treat this file as **the canonical source of truth** for all future coding decisions.

---

# 1. ROLE OF THE AI CODING AGENT

You are an AI coding agent assisting with the development of a **crypto trading bot framework**.

Your responsibilities:

1. Keep the codebase **coherent, modular, and maintainable**.
2. Respect and preserve existing features unless explicitly told otherwise.
3. Implement changes in **incremental, reviewable steps** (“mods”).
4. Ensure code remains **clear, well-structured, and safe**.
5. Optimize the framework so it can support:
   - Swing trading
   - Intraday scalping
   - Algorithmic / rules-based strategies
   - Neural-network / ML strategies
6. Maintain **risk discipline** and always prioritize capital preservation.

When in doubt:
- Prefer clarity over cleverness.
- Prefer explicit configs over hard-coded values.
- Prefer modularity and testability over tightly coupled logic.

---

# 2. PROJECT GOAL (TRADING STYLE & EVOLUTION)

This project is a **flexible crypto trading framework**.

## Current baseline (already implemented / being implemented)
- Focus on **simple directional swing trading**:
  - Trades may be held for several days to a few weeks.
  - Uses interpretable technical indicators (EMA, RSI, volume, etc.).
  - Backtesting on candle-level OHLCV data.
  - Structured risk management (e.g., ~1–2% risk per trade).
  - Clean, console-style performance summaries and logs.

## Target capabilities (future mods)
The framework should be designed so that it can evolve to support:

1. **Intraday scalping**
   - Shorter timeframes (e.g., 1m / 5m candles, possibly tick feeds).
   - Faster decision loops.
   - Tighter stops and more frequent trades.

2. **“HFT-ish” low-latency trading (within retail constraints)**
   - Real-time WebSocket market data.
   - Async event loops for order routing.
   - Fast reaction to signals.
   - NOTE: True institutional HFT (microsecond latencies, colocation, C++ gateways) is **out of scope**; this project targets realistic Python + exchange API latency.

3. **Neural-network / ML-driven strategies (autopilot modes)**
   - ML models consuming historical data & engineered features.
   - A training pipeline (data → features → model → validation).
   - An inference interface that plugs into the same strategy framework.
   - Ability to switch between rule-based strategies and ML strategies via config.

The architecture must be flexible enough that new strategies (swing, scalping, or ML) can be plugged in **without rewriting the whole system**.

---

# 3. ARCHITECTURE (EXPECTED STRUCTURE)

Use this architecture as the baseline expectation, even if the current repo structure differs. Evolve towards this gradually.

```text
config/
    - strategy configs
    - risk configs
    - asset configs
    - runtime mode configs (swing / scalper / ml)

data_feed/
    - OHLCV loaders (historical)
    - real-time WebSocket clients (future)
    - data normalizers (e.g., pandas DataFrame)

indicators/
    - EMA, SMA
    - RSI
    - Volume indicators
    - Other reusable technical indicators

strategies/
    rule_based/
        - swing strategies (EMA + RSI, etc.)
        - scalping strategies (short timeframe rules)
    ml_based/
        - model wrappers for trained ML/NN models
        - feature extraction utilities
        - inference adapters
    - all strategies expose a unified interface returning discrete signals

risk_management/
    - position sizing
    - account risk rules (e.g., 1–2% per trade default)
    - stop-loss / take-profit logic
    - max exposure rules

backtesting/
    - simulation engine (supports different strategies and timeframes)
    - trade recorder
    - portfolio / cash management
    - PnL calculations
    - hooks for strategy-specific configs

execution/
    - exchange API wrappers (BinanceClient, paper trading client, etc.)
    - async order placement logic (for scalping / faster modes)
    - retry and error handling

ml_pipeline/  (future)
    - data preprocessing for training
    - feature engineering
    - training scripts
    - evaluation / validation utilities
    - model persistence (save/load)

analytics/
    - performance summaries
    - metrics (win rate, drawdown, Sharpe-like metrics, etc.)
    - optional plotting / reporting

logs/
    - backtest logs
    - live trading logs
    - error logs
When modifying files, follow this modular separation of concerns and keep it compatible with both swing and faster modes.

4. CODING STANDARDS
General
Use Python 3.10+.

Always include type hints.

Use docstrings with purpose, inputs, outputs.

Keep functions small and focused.

Avoid global mutable state; pass config and state explicitly.

Write code so it can handle both slower (swing) and faster (scalping) modes.

Dependency handling
Use pandas/numpy cleanly and predictably.

When adding ML libraries (e.g., PyTorch, TensorFlow, scikit-learn), isolate them in ml_pipeline/ and strategies/ml_based/.

Error handling
Avoid bare except.

Use clear, targeted exceptions.

Provide meaningful error messages, especially around exchange calls, latency, and data integrity.

Logging
Use consistent logging throughout the project.

Always log:

Strategy decisions

Entries and exits

Position size

Price

PnL impact

Critical errors or warnings

5. RISK MANAGEMENT RULES
Risk management is central and must work for all modes (swing, scalping, ML).

Defaults (can be overridden by config)
Account size example: $1000

Risk per trade: ~1–2% of account equity

Max concurrent exposure: configurable via risk config

Position sizing
The risk module must:

Take:

Current equity

Entry price

Stop-loss price

Optional take-profit / target R multiple

Compute:

Position size (quantity) that respects risk per trade

Dollar risk

Potential reward (if take-profit defined)

Stop-loss / take-profit
Required for all strategies (swing or scalper).

Configurable per strategy and per asset.

Centralized in risk logic, not scattered in strategy code.

Hard rules
No position should exceed configured account risk.

No hidden leverage or implicit amplification without explicit config.

All strategies (rule-based and ML-based) must route through the same risk pipeline.

6. INDICATORS & SIGNAL LOGIC
Baseline indicators:

EMA / SMA
Common swing periods: 20, 50

Scalping may use shorter periods: 5, 9, 12, etc. (configurable)

Used for trend and momentum direction, crossovers.

RSI
Default period: 14

Readings used for:

Overbought / oversold

Approaching overbought / oversold

Divergences (if implemented)

Volume
Used for confirmation and filters.

Scalping strategies may use volume spikes and order-flow-like proxies.

Strategy outputs
All strategies must ultimately output discrete signals like:

python
Copy code
"LONG"
"SHORT"
"FLAT"
Optionally, strategies may return metadata (e.g., confidence, reasons), but the execution layer must always be able to interpret a clear direction.

7. LOGGING AND PnL FORMATTING
PnL formatting has previously required fixes and must remain clean.

Rules:

Internally, PnL values are numeric.

Only when displaying or logging are they formatted as strings.

Display format:

Two decimal places for dollar amounts.

No scientific notation.

Ensure consistent units (e.g., base currency vs quote currency).

Backtest summaries should include:

Total PnL

PnL by symbol (if multi-asset)

Win rate

Max drawdown (if available)

Number of trades

Average R multiple

Basic risk stats (e.g., largest loss, largest win)

Console output must be compact and readable.

8. “MODS” — DEVELOPMENT HISTORY & RULESET
Development is tracked as mods: mod 1, mod 2, ..., mod N.

Rules for handling mods:
Mods are incremental improvements, not full rewrites.

Each mod builds on all previous work and on this memory file.

A mod may:

Add features

Fix bugs

Refactor architecture

Improve performance

Add new strategies (swing, scalping, ML)

Enhance risk management or logging

At the end of each mod, the AI should provide:
A short summary (bullet list) of:

What changed

Why it changed

Any new configs or files

Mention any breaking changes or migrations required.

If the user says:

“Begin mod X”

→ Treat it as: Implement the next evolutionary increment, consistent with swing + scalping + ML capable architecture.

9. DEVELOPMENT WORKFLOW EXPECTATIONS
Inside VS Code, the AI agent must:

Briefly explain the plan before large changes.

Prefer diffs / patch-style edits over full-file dumps when possible.

Keep changes scoped and reviewable.

Maintain compatibility with existing modules.

Respect this memory file unless explicitly told to update it.

When the user provides:

Console output

Tracebacks

Backtest logs

Config snippets

…the AI should:

Parse them carefully.

Identify likely causes.

Propose targeted changes.

Implement minimal-scope fixes unless a larger refactor is clearly needed.

When introducing ML or new real-time features:

Isolate experimental / heavy dependencies.

Avoid breaking existing swing strategies and backtests.

10. USER PREFERENCES
The user prefers:

Straightforward, concise explanations.

Clear code organization and modular design.

Minimal fluff — focus on:

What changed

Why it changed

How it affects performance and risk

Strong technical signal logic:

EMA

RSI

Volume and momentum

Robust risk management, never an afterthought.

Clean PnL formatting and readable logs.

A predictable iterative process using mod numbers.

If unsure, the AI should ask one short clarifying question, then proceed with sensible defaults.

11. WHAT THE AGENT MUST DO NEXT
Whenever a new instruction is given inside VS Code:

Load and remember everything in this file.

Apply all coding work in a way that aligns with this memory.

Treat this file as the project’s persistent brain.

Never silently discard this architecture unless explicitly told to redesign it.

When implementing new mods:

Follow all rules above.

Keep behavior consistent and extendable.