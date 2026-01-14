"""Alert Formatting Module Documentation

This module provides formatters to convert trade_intelligence.TradeSignal objects
into human-readable formats suitable for Discord, dashboards, email notifications,
and other alerting systems.

## Overview

The alert_formatting module is designed to:
- Convert TradeSignal objects to multiple output formats (text, markdown, Discord)
- Rank and sort signals by various criteria (conviction, agreement, regime, risk)
- Generate Discord embeds with rich formatting and color coding
- Provide configurable thresholds and alerts
- Support batch processing of multiple signals
- Enable filtering and grouping of signals

## Components

### 1. Signal Formatters (signal_formatter.py)

#### AlertFormatter (Abstract Base Class)
Base class for all formatters with common utilities.

**Methods:**
- `format_signal(signal)` - Format single signal
- `format_signals(signals)` - Format multiple signals
- `_format_conviction(conviction)` - Format conviction with symbol
- `_format_risk_flags(signal)` - Format risk flags as text
- `_format_agreement(signal)` - Format agreement metrics

#### TextAlertFormatter
Plain text formatter for simple output.

**Usage:**
```python
from alert_formatting import TextAlertFormatter
from trade_intelligence import SignalEngine

# Generate signals
engine = SignalEngine()
signals = engine.generate_signal_batch(
    strategy_outputs=[...],
    symbols=['BTCUSDT', 'ETHUSDT'],
    ...
)

# Format as plain text
formatter = TextAlertFormatter()
for signal in signals:
    print(formatter.format_signal(signal))
```

**Output Example:**
```
============================================================
BUY SIGNAL: BTCUSDT (1h)
============================================================
Direction: LONG
Conviction: █████ 0.85 (VERY_HIGH)
Regime: TRENDING
Agreement: 3 strategies, 100.0% agreement
Risk Status: No Risks Detected
Strategies: EMA_RSI, MACD, Bollinger
Signal Time: 2025-01-14T12:00:00Z
Rationale: EMA crossover confirmed by RSI + MACD confluence
============================================================
```

#### MarkdownAlertFormatter
Markdown formatter for rich text formatting.

**Usage:**
```python
from alert_formatting import MarkdownAlertFormatter

formatter = MarkdownAlertFormatter()
markdown_text = formatter.format_signals(signals)
print(markdown_text)
```

**Output Features:**
- Markdown headers (#, ##)
- Bold formatting (**text**)
- Blockquotes (> text) for rationale
- Inline code blocks for strategy names
- Separator lines (---) between signals

### 2. Discord Formatter (discord_formatter.py)

#### DiscordAlertFormatter
Discord-specific formatter with rich embeds and mentions.

**Configuration:**
```python
from alert_formatting import DiscordAlertFormatter
from alert_formatting.discord_formatter import DiscordConfig

config = DiscordConfig(
    color_long=0x00FF00,           # Green
    color_short=0xFF0000,          # Red
    color_flat=0x808080,           # Gray
    mention_on_long="<@&ROLE_ID>", # Mention on LONG signals
    mention_on_short="<@&ROLE_ID>",# Mention on SHORT signals
    mention_on_high_conviction="<@USER_ID>",  # Mention on high conviction
    conviction_threshold_alert=0.6,  # Only alert if conviction >= 0.6
    use_embeds=True,
    include_footer=True,
    include_timestamp=True
)

formatter = DiscordAlertFormatter(config)
```

**Text Message Format:**
```python
# Format as plain message
message = formatter.format_signal(signal)
# Output:
# 🟢 LONG BTCUSDT/1h
# Conviction: █████ 0.85 (VERY_HIGH)
# Regime: TRENDING
# Risk: No Risks Detected
```

**Discord Embed Format:**
```python
# Format as Discord embed (for discord.py library)
embed = formatter.format_as_embed(signal)
# Returns JSON dict compatible with discord.Embed()

# For batch processing
embeds = formatter.format_embeds_batch(signals)
# Returns list of embed dicts
```

**Alert Trigger Logic:**
```python
# Check if signal should trigger alert
if formatter.should_alert(signal):
    # Send to Discord
    await channel.send(embed=discord.Embed.from_dict(embed))
```

### 3. Ranking Engine (ranking_engine.py)

#### RankingEngine
Sort and rank signals by multiple criteria.

**Sorting Criteria (SortCriteria enum):**
- `CONVICTION_DESC` - Highest conviction first (default for alerts)
- `CONVICTION_ASC` - Lowest conviction first
- `AGREEMENT_DESC` - Highest agreement first
- `AGREEMENT_ASC` - Lowest agreement first
- `REGIME_TREND` - Trending signals first (best regime for trading)
- `RISK_ASC` - Lowest risk first (fewest risk flags)
- `COMBINED` - Custom weighted combination (default for general use)

**Configuration:**
```python
from alert_formatting import RankingEngine, RankingConfig
from alert_formatting.ranking_engine import SortCriteria

config = RankingConfig(
    primary_sort=SortCriteria.COMBINED,  # Main sorting method
    conviction_weight=0.5,                # Conviction importance (0-1)
    agreement_weight=0.3,                 # Agreement importance
    regime_weight=0.2,                    # Regime importance
    risk_penalty_per_flag=0.1,           # Penalty for each risk flag
    min_conviction=0.6,                   # Filter: minimum conviction
    direction_filter=SignalDirection.LONG,# Filter: specific direction
    exclude_high_risk=False               # Filter: exclude signals with risk flags
)

engine = RankingEngine(config)
```

**Usage Examples:**

```python
# Sort all signals by combined score
ranked = engine.rank_signals(signals)

# Get top 5 signals
top_5 = engine.get_top_signals(signals, n=5)

# Group by direction
by_direction = engine.group_by_direction(signals)
longs = by_direction[SignalDirection.LONG]
shorts = by_direction[SignalDirection.SHORT]

# Group by symbol
by_symbol = engine.group_by_symbol(signals)
btc_signals = by_symbol['BTCUSDT']

# Get summary statistics
summary = engine.get_signal_summary(signals)
print(f"Total signals: {summary['total']}")
print(f"Average conviction: {summary['avg_conviction']:.3f}")
print(f"High conviction count: {summary['high_conviction_count']}")
print(f"High risk count: {summary['high_risk_count']}")
```

**Filtering Examples:**
```python
# Only high-confidence signals
config = RankingConfig(min_conviction=0.7)
engine = RankingEngine(config)
high_confidence = engine.rank_signals(all_signals)

# Only BUY signals
from trade_intelligence import SignalDirection
config = RankingConfig(direction_filter=SignalDirection.LONG)
engine = RankingEngine(config)
buy_signals = engine.rank_signals(all_signals)

# Exclude risky signals
config = RankingConfig(exclude_high_risk=True)
engine = RankingEngine(config)
safe_signals = engine.rank_signals(all_signals)
```

## Complete Integration Example

```python
from alert_formatting import (
    TextAlertFormatter, MarkdownAlertFormatter,
    DiscordAlertFormatter, RankingEngine, RankingConfig
)
from alert_formatting.discord_formatter import DiscordConfig
from alert_formatting.ranking_engine import SortCriteria
from trade_intelligence import SignalEngine

# Step 1: Generate trade signals
signal_engine = SignalEngine()
signal_engine.register_strategy('ema_rsi', format_type='TradeIntent')
signal_engine.register_strategy('macd', format_type='SignalDict')

signals = signal_engine.generate_signal_batch(
    strategy_outputs={
        'BTCUSDT': {
            'ema_rsi': {'signal': 'LONG', 'metadata': {}},
            'macd': {'signal': 'LONG'}
        },
        'ETHUSDT': {
            'ema_rsi': {'signal': 'FLAT'},
            'macd': {'signal': 'SHORT'}
        }
    },
    symbols=['BTCUSDT', 'ETHUSDT'],
    timeframe='1h',
    regime='TRENDING',
    volatility_percentile=45,
    equity=10000,
    peak_equity=10500,
    win_rate=0.55
)

# Step 2: Rank and filter signals
rank_config = RankingConfig(
    primary_sort=SortCriteria.COMBINED,
    min_conviction=0.6,
    exclude_high_risk=False
)
ranker = RankingEngine(rank_config)
ranked_signals = ranker.rank_signals(signals)
top_signals = ranker.get_top_signals(ranked_signals, n=5)

# Step 3: Format for different outputs

# Text output
text_formatter = TextAlertFormatter()
print(text_formatter.format_signals(top_signals))

# Markdown output
md_formatter = MarkdownAlertFormatter()
markdown_report = md_formatter.format_signals(top_signals)

# Discord embeds (for bot integration)
discord_config = DiscordConfig(
    mention_on_long="<@&123456>",
    conviction_threshold_alert=0.6
)
discord_formatter = DiscordAlertFormatter(discord_config)
embeds = discord_formatter.format_embeds_batch(top_signals)

# Send high-conviction signals
for signal in signals:
    if discord_formatter.should_alert(signal):
        embed_dict = discord_formatter.format_as_embed(signal)
        # Send via discord.py: await channel.send(embed=discord.Embed.from_dict(embed_dict))

# Step 4: Generate summary
summary = ranker.get_signal_summary(signals)
print(f"Generated {summary['total']} signals: "
      f"{summary['long_count']} LONG, "
      f"{summary['short_count']} SHORT, "
      f"{summary['flat_count']} FLAT")
```

## Configuration

### FormatterConfig (Base)
```python
@dataclass
class FormatterConfig:
    # Direction display
    direction_symbols: dict = {
        'LONG': 'BUY',
        'SHORT': 'SELL',
        'FLAT': 'HOLD'
    }
    
    # Confidence symbols (ASCII bars)
    confidence_symbols: dict = {
        'VERY_HIGH': '█████',
        'HIGH': '████ ',
        'MEDIUM': '███  ',
        'LOW': '██   ',
        'VERY_LOW': '█    '
    }
    
    # Include optional fields
    include_metadata: bool = True
    include_risk_flags: bool = True
    include_strategy_names: bool = True
    include_timestamp: bool = True
    
    # Decimal places for numeric values
    decimal_places: int = 3
    
    # Text wrapping width
    line_width: int = 100
```

### DiscordConfig (Extends FormatterConfig)
```python
@dataclass
class DiscordConfig(FormatterConfig):
    # Embed colors
    color_long: int = 0x00FF00      # Green
    color_short: int = 0xFF0000     # Red
    color_flat: int = 0x808080      # Gray
    
    # Role/user mentions
    mention_on_long: Optional[str] = None          # e.g., "<@&ROLE_ID>"
    mention_on_short: Optional[str] = None         # e.g., "<@&ROLE_ID>"
    mention_on_high_conviction: Optional[str] = None  # High confidence alerts
    
    # Discord-specific options
    use_embeds: bool = True
    include_footer: bool = True
    include_thumbnail: bool = True
    
    # Alert threshold
    conviction_threshold_alert: float = 0.6
```

### RankingConfig
```python
@dataclass
class RankingConfig:
    # Sorting method
    primary_sort: SortCriteria = SortCriteria.COMBINED
    
    # Combined score weights (sum = 1.0)
    conviction_weight: float = 0.5
    agreement_weight: float = 0.3
    regime_weight: float = 0.2
    
    # Regime preferences (0-1, relative)
    regime_scores: dict = {
        RegimeType.TRENDING: 1.0,
        RegimeType.BREAKOUT: 0.8,
        RegimeType.RANGING: 0.5,
        RegimeType.NEUTRAL: 0.3,
    }
    
    # Risk penalty per flag (0-1)
    risk_penalty_per_flag: float = 0.1
    
    # Filters
    min_conviction: Optional[float] = None
    direction_filter: Optional[SignalDirection] = None
    exclude_high_risk: bool = False
```

## Key Design Principles

1. **Analysis-Only**: No execution or trading logic. Pure formatting and analysis.
2. **JSON-Serializable**: All outputs are JSON-compatible for easy storage/transmission.
3. **Configurable**: Every threshold and formatting option is configurable.
4. **Non-invasive**: Formatters don't modify TradeSignal objects (read-only).
5. **Safe Defaults**: All configurations have sensible defaults that are conservative.
6. **Discord-Native**: Includes native Discord embed support with rich formatting.

## Testing

Run tests with pytest:
```bash
pytest tests/test_alert_formatting.py -v

# Specific test class
pytest tests/test_alert_formatting.py::TestDiscordFormatting -v

# With coverage
pytest tests/test_alert_formatting.py --cov=alert_formatting --cov-report=html
```

## Future Extensions

1. **Email Formatter**: HTML email formatting with inline images
2. **Slack Formatter**: Slack Block Kit formatting
3. **Dashboard JSON**: Optimized JSON for web dashboards
4. **Chart Generation**: Matplotlib/Plotly chart integration
5. **Alert Routing**: Dynamic routing to multiple channels based on criteria
6. **History Tracking**: Store alert history for analytics
7. **A/B Testing**: Test different formatting on alerts

## Safety Notes

- All formatters are **read-only** (no state modification)
- No external API calls or network I/O
- Safe to use in high-frequency scenarios
- Thread-safe (stateless formatter instances)
- No secrets or credentials in outputs
"""
