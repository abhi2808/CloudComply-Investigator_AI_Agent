"""
In-memory session store for the Teams bot.

Maps a Teams user ID → session dict so the bot remembers:
  - which web-app user is logged in
  - which AWS account is currently selected

Lifetime: server process (resets on restart — fine for PoC).
For production, persist sessions in MongoDB.

Session schema:
{
    "user_id":     str,   # MongoDB _id of the web-app user
    "email":       str,   # display only
    "account_id":  str,   # MongoDB _id of selected AWS account
    "account_name": str,  # display nickname
}
"""

from typing import Optional

# teams_user_id → session dict
_sessions: dict[str, dict] = {}


def get_session(teams_user_id: str) -> Optional[dict]:
    """Return the session for a Teams user, or None if not logged in."""
    return _sessions.get(teams_user_id)


def set_session(teams_user_id: str, session: dict) -> None:
    """Store or overwrite the session for a Teams user."""
    _sessions[teams_user_id] = session


def clear_session(teams_user_id: str) -> None:
    """Remove the session (logout)."""
    _sessions.pop(teams_user_id, None)


def set_active_account(teams_user_id: str, account_id: str, account_name: str) -> bool:
    """
    Update the active account for an already-logged-in user.
    Returns False if the user is not logged in.
    """
    session = _sessions.get(teams_user_id)
    if not session:
        return False
    session["account_id"] = account_id
    session["account_name"] = account_name
    return True


def is_logged_in(teams_user_id: str) -> bool:
    return teams_user_id in _sessions
