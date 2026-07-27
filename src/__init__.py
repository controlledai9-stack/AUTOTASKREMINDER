"""AI Daily Progress Tracker - core package.

This package contains the modular building blocks of the application:

- config: centralized configuration loaded from environment variables.
- database: SQLite connection handling and schema initialization.
- models: typed data structures shared across modules.
- task_manager: CRUD and query operations for tasks.
- progress_calculator: derives progress/completion statistics from tasks.
- streak_tracker: computes and persists daily completion streaks.
- email_service: builds and sends HTML progress/summary emails.
- utils: small shared helpers (logging, date/time utilities).
"""

__version__ = "1.0.0"
