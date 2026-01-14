# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Multi-session aggregation and reporting (#5)
- Realistic fee and slippage modeling for paper trading (#4)
- Parameter drift monitoring with bounds and penalties (#6)
- Bot legacy test coverage for backward compatibility (#3)

### Changed
- Enhanced paper trader with realistic execution cost models
- Improved aggregation with proper zero-value handling for empty sessions

### Fixed
- Edge case handling in multi-session aggregator for single-row sessions
- Missing dependencies (python-dotenv, ta) in requirements.txt

## [0.1.0] - 2025-01-13

### Added
- Initial project structure with modular architecture
- Paper trading engine with cash/equity model
- Risk management system with position sizing
- Strategy profile system with JSON-based configuration
- Config-driven backtesting framework
- Safety validation suite with invariant checks
- ML pipeline for feature engineering and model training
- Live trading safety gates (paper-only by default)
- Comprehensive test coverage (300+ tests)

### Security
- Two-key safety gate for live trading protection
- Paper-only default mode with explicit opt-in for live trading
- Kill switch via environment variable
- Safety limits validation
