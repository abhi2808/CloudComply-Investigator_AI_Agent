"""
CloudComply AI Teams Bot Handler - with login, account listing, and account switching.

Commands (works in DM or @mention in channel):
  login <email> <password>   - authenticate with your CloudComply web-app credentials
  acc                        - list your registered AWS accounts
  switch <number|alias>      - switch active account by list number or nickname
  logout                     - clear session
  help                       - show available commands
  <anything else>            - run an AWS security investigation

Important PoC note:
  Sessions are in-memory per bot process.
  Restarting the backend clears all sessions (users must re-login).
"""

import logging
import re

from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from botbuilder.schema import Activity, ActivityTypes

from app.bot.adaptive_cards import build_response_card, build_welcome_card, build_accounts_card
from app.bot import session_store

logger = logging.getLogger(__name__)

# Strip @mention prefix Teams sometimes prepends (e.g. "<at>CloudComply AI</at> login ...")
_MENTION_RE = re.compile(r"<at>[^<]*</at>\s*", re.IGNORECASE)


def _clean(text: str) -> str:
    """Remove @mention XML tags and normalise whitespace."""
    return _MENTION_RE.sub("", text or "").strip()


class CloudComplyBot(ActivityHandler):
    """ActivityHandler with command parsing and per-user session management."""

    # -------------------------------------------------------------------------
    # Entry point
    # -------------------------------------------------------------------------
    async def on_message_activity(self, turn_context: TurnContext) -> None:
        raw_text = turn_context.activity.text or ""
        text = _clean(raw_text)

        if not text:
            await turn_context.send_activity(
                MessageFactory.text(
                    "Please send a command or ask a security question.\n"
                    "Type 'help' to see available commands."
                )
            )
            return

        teams_user_id = turn_context.activity.from_property.id
        user_name = turn_context.activity.from_property.name or "there"

        lower = text.lower()

        # Command routing
        if lower == "help":
            await self._cmd_help(turn_context, user_name)
        elif lower.startswith("login "):
            await self._cmd_login(turn_context, teams_user_id, text)
        elif lower == "logout":
            await self._cmd_logout(turn_context, teams_user_id)
        elif lower in ("acc", "accounts", "account list"):
            await self._cmd_list_accounts(turn_context, teams_user_id)
        elif lower.startswith("switch "):
            await self._cmd_switch(turn_context, teams_user_id, text)
        else:
            # Everything else -> security investigation
            await self._cmd_investigate(turn_context, teams_user_id, user_name, text)

    # -------------------------------------------------------------------------
    # Welcome
    # -------------------------------------------------------------------------
    async def on_members_added_activity(self, members_added, turn_context: TurnContext) -> None:
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                card = build_welcome_card()
                await turn_context.send_activity(MessageFactory.attachment(card))

    # =========================================================================
    # Command handlers
    # =========================================================================

    async def _cmd_help(self, turn_context: TurnContext, user_name: str) -> None:
        msg = (
            "Hi **" + user_name + "**! Here is what I understand:\n\n"
            "| Command | What it does |\n"
            "|---|---|\n"
            "| `login <email> <password>` | Authenticate with your CloudComply account |\n"
            "| `acc` | List your registered AWS accounts |\n"
            "| `switch <number or alias>` | Switch the active AWS account |\n"
            "| `logout` | Clear your session |\n"
            "| *(any question)* | Investigate your active AWS account |\n\n"
            "**Tip:** type `login` first, then ask anything like:\n"
            "*Who logged in recently?* or *Are my S3 buckets public?*"
        )
        await turn_context.send_activity(MessageFactory.text(msg))

    # ── LOGIN -----------------------------------------------------------------
    async def _cmd_login(
        self, turn_context: TurnContext, teams_user_id: str, text: str
    ) -> None:
        parts = text.split(maxsplit=2)  # ["login", "email", "password"]
        if len(parts) != 3:
            await turn_context.send_activity(
                MessageFactory.text(
                    "Usage: `login <email> <password>`\n"
                    "Example: `login alice@example.com mypassword123`"
                )
            )
            return

        _, email, password = parts

        from app.db.repositories.user_repository import user_repository
        from app.core.security import verify_password

        user_doc = await user_repository.get_user_by_email(email.lower())
        if not user_doc or not verify_password(password, user_doc.get("hashed_password", "")):
            await turn_context.send_activity(
                MessageFactory.text(
                    "Login failed - email or password is incorrect.\n"
                    "Use the same credentials as your CloudComply web app."
                )
            )
            return

        # Load their accounts
        from app.db.repositories.account_repository import account_repository
        accounts = await account_repository.get_accounts_by_user(str(user_doc["_id"]))

        # Pick first account as default
        active_account_id = ""
        active_account_name = "(none - use 'acc' then 'switch <n>' to select)"
        if accounts:
            first = accounts[0]
            active_account_id = str(first["_id"])
            active_account_name = first.get("nickname", active_account_id)

        session_store.set_session(teams_user_id, {
            "user_id":      str(user_doc["_id"]),
            "email":        email.lower(),
            "account_id":   active_account_id,
            "account_name": active_account_name,
            "accounts":     accounts,
        })

        if accounts:
            acct_line = "Active account: **" + active_account_name + "**"
            if len(accounts) > 1:
                acct_line += " (+ " + str(len(accounts) - 1) + " more - use 'acc' to list)"
        else:
            acct_line = "No AWS accounts registered yet. Add one via the web app first."

        await turn_context.send_activity(
            MessageFactory.text(
                "Logged in as **" + email + "**\n\n"
                + acct_line + "\n\n"
                "You can now ask security questions!"
            )
        )

    # ── LOGOUT ----------------------------------------------------------------
    async def _cmd_logout(self, turn_context: TurnContext, teams_user_id: str) -> None:
        if session_store.is_logged_in(teams_user_id):
            session = session_store.get_session(teams_user_id)
            email = session.get("email", "")
            session_store.clear_session(teams_user_id)
            await turn_context.send_activity(
                MessageFactory.text("Logged out from **" + email + "**. Session cleared.")
            )
        else:
            await turn_context.send_activity(
                MessageFactory.text("You are not currently logged in.")
            )

    # ── LIST ACCOUNTS ---------------------------------------------------------
    async def _cmd_list_accounts(
        self, turn_context: TurnContext, teams_user_id: str
    ) -> None:
        session = session_store.get_session(teams_user_id)
        if not session:
            await self._not_logged_in(turn_context)
            return

        accounts = session.get("accounts", [])
        if not accounts:
            await turn_context.send_activity(
                MessageFactory.text(
                    "No AWS accounts registered.\n"
                    "Add accounts via the CloudComply web app first."
                )
            )
            return

        active_id = session.get("account_id", "")
        card = build_accounts_card(accounts, active_id)
        await turn_context.send_activity(MessageFactory.attachment(card))

    # ── SWITCH ACCOUNT --------------------------------------------------------
    async def _cmd_switch(
        self, turn_context: TurnContext, teams_user_id: str, text: str
    ) -> None:
        session = session_store.get_session(teams_user_id)
        if not session:
            await self._not_logged_in(turn_context)
            return

        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await turn_context.send_activity(
                MessageFactory.text("Usage: `switch <number or account alias>`")
            )
            return

        selector = parts[1].strip()
        accounts = session.get("accounts", [])

        matched = None

        # By list number (1-based)
        if selector.isdigit():
            idx = int(selector) - 1
            if 0 <= idx < len(accounts):
                matched = accounts[idx]

        # By exact nickname (case-insensitive)
        if not matched:
            for acc in accounts:
                if acc.get("nickname", "").lower() == selector.lower():
                    matched = acc
                    break

        # By partial nickname match
        if not matched:
            for acc in accounts:
                if selector.lower() in acc.get("nickname", "").lower():
                    matched = acc
                    break

        if not matched:
            names = "\n".join(
                "  " + str(i + 1) + ". " + a.get("nickname", str(a["_id"]))
                for i, a in enumerate(accounts)
            )
            await turn_context.send_activity(
                MessageFactory.text(
                    "Account '" + selector + "' not found.\n\n"
                    "Your accounts:\n" + names + "\n\n"
                    "Use `switch 1` or `switch <alias>`."
                )
            )
            return

        new_id = str(matched["_id"])
        new_name = matched.get("nickname", new_id)
        session_store.set_active_account(teams_user_id, new_id, new_name)

        await turn_context.send_activity(
            MessageFactory.text(
                "Switched to **" + new_name + "** "
                "(" + matched.get("region", "unknown region") + ")\n\n"
                "Ask your next security question!"
            )
        )

    # ── INVESTIGATE (main AI flow) --------------------------------------------
    async def _cmd_investigate(
        self,
        turn_context: TurnContext,
        teams_user_id: str,
        user_name: str,
        question: str,
    ) -> None:
        session = session_store.get_session(teams_user_id)
        if not session:
            await self._not_logged_in(turn_context)
            return

        account_id = session.get("account_id", "")
        account_name = session.get("account_name", "Unknown")
        user_id = session.get("user_id", "")

        if not account_id:
            await turn_context.send_activity(
                MessageFactory.text(
                    "No account selected.\n"
                    "Use `acc` to list your accounts, then `switch <n>` to pick one."
                )
            )
            return

        logger.info(
            "Teams investigation - user=%s account=%s question=%s",
            session["email"], account_name, question[:80]
        )

        # Typing indicator
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))

        try:
            from app.services.agent.runner import run as agent_run
            result = await agent_run(
                user_question=question,
                account_id=account_id,
                user_id=user_id,
                conversation_history=[],
            )
        except Exception as exc:
            logger.exception("Agent failed for Teams user '%s': %s", user_name, exc)
            await turn_context.send_activity(
                MessageFactory.text("Investigation failed: " + str(exc))
            )
            return

        card = build_response_card(result, account_name=account_name)
        await turn_context.send_activity(MessageFactory.attachment(card))

    # ── Helper ----------------------------------------------------------------
    async def _not_logged_in(self, turn_context: TurnContext) -> None:
        await turn_context.send_activity(
            MessageFactory.text(
                "You are not logged in.\n\n"
                "Use: `login <email> <password>`\n"
                "Example: `login alice@example.com mypassword`\n\n"
                "Use the same credentials as your CloudComply web app."
            )
        )
