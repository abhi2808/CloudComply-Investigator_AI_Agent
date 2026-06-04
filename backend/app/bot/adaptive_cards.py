"""
Adaptive Card builder for CloudComply AI Teams bot responses.
Produces richly formatted cards with severity badges, investigation
steps, and recommended actions.
"""

from botbuilder.schema import Attachment


# Severity → display colour mapping (Adaptive Card accent colours)
_SEVERITY_COLOURS = {
    "CRITICAL": "attention",   # red
    "HIGH":     "warning",     # orange-ish (maps to warning in Teams)
    "MEDIUM":   "warning",     # yellow
    "LOW":      "accent",      # blue
    "NONE":     "good",        # green
}

_SEVERITY_EMOJI = {
    "CRITICAL": "🔴",
    "HIGH":     "🟠",
    "MEDIUM":   "🟡",
    "LOW":      "🔵",
    "NONE":     "🟢",
}


def build_response_card(result: dict, account_name: str = "") -> Attachment:
    """
    Build a Teams Adaptive Card from an agent result dict.

    Expected keys in result:
        answer              str  — main response text
        severity            str  — CRITICAL | HIGH | MEDIUM | LOW | NONE
        steps_taken         list — [{tool_name, summary}, ...]
        recommended_actions list — [str, ...]
    """
    severity = (result.get("severity") or "NONE").upper()
    colour = _SEVERITY_COLOURS.get(severity, "default")
    emoji = _SEVERITY_EMOJI.get(severity, "⚪")
    answer = result.get("answer", "Investigation complete.")
    steps = result.get("steps_taken", []) or []
    actions = result.get("recommended_actions", []) or []

    # ── Header row ─────────────────────────────────────────────────────────
    header_column_set = {
        "type": "ColumnSet",
        "columns": [
            {
                "type": "Column",
                "width": "stretch",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "🛡️ CloudComply AI",
                        "weight": "Bolder",
                        "size": "Medium",
                        "color": "Accent",
                    }
                ],
            },
            {
                "type": "Column",
                "width": "auto",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": f"{emoji} {severity}",
                        "weight": "Bolder",
                        "color": colour,
                        "horizontalAlignment": "Right",
                    }
                ],
            },
        ],
    }

    # ── Separator ──────────────────────────────────────────────────────────
    separator = {
        "type": "TextBlock",
        "text": "",
        "separator": True,
        "spacing": "None",
    }

    # ── Answer block ───────────────────────────────────────────────────────
    answer_block = {
        "type": "TextBlock",
        "text": answer,
        "wrap": True,
        "size": "Default",
        "spacing": "Medium",
    }

    body = [header_column_set, separator, answer_block]

    # ── Investigation Steps (collapsed toggle) ──────────────────────────────
    if steps:
        step_facts = []
        for s in steps[:15]:  # cap at 15 to avoid card size limits
            tool = s.get("tool_name", "tool")
            summary = s.get("summary", "")[:120]
            step_facts.append({"title": f"  • {tool}", "value": summary})

        steps_container = {
            "type": "Container",
            "spacing": "Medium",
            "items": [
                {
                    "type": "TextBlock",
                    "text": f"🔍 Investigation Steps ({len(steps)})",
                    "weight": "Bolder",
                    "size": "Small",
                    "color": "Accent",
                },
                {
                    "type": "FactSet",
                    "facts": step_facts,
                    "isVisible": False,  # collapsed by default
                    "id": "stepsFactSet",
                },
            ],
            "selectAction": {
                "type": "Action.ToggleVisibility",
                "targetElements": ["stepsFactSet"],
            },
        }
        body.append(steps_container)

    # ── Recommended Actions ─────────────────────────────────────────────────
    if actions:
        actions_items: list = [
            {
                "type": "TextBlock",
                "text": "✅ Recommended Actions",
                "weight": "Bolder",
                "size": "Small",
                "spacing": "Medium",
                "color": "Good",
            }
        ]
        for i, action in enumerate(actions[:8], 1):
            actions_items.append({
                "type": "TextBlock",
                "text": f"{i}. {action}",
                "wrap": True,
                "size": "Small",
                "spacing": "Small",
            })
        body.append({
            "type": "Container",
            "items": actions_items,
            "spacing": "Medium",
        })

    # ── Footer ─────────────────────────────────────────────────────────────
    footer_text = "Investigated via CloudComply AI"
    if account_name:
        footer_text = f"Account: {account_name}  •  Investigated via CloudComply AI"
    body.append({
        "type": "TextBlock",
        "text": footer_text,
        "size": "Small",
        "isSubtle": True,
        "horizontalAlignment": "Right",
        "spacing": "Medium",
        "separator": True,
    })

    # ── Assemble card ──────────────────────────────────────────────────────
    card_content = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": body,
    }

    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card_content,
    )


def build_welcome_card() -> Attachment:
    """Welcome card sent when the bot is first added to a chat."""
    card_content = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "🛡️ CloudComply AI",
                "weight": "Bolder",
                "size": "Large",
                "color": "Accent",
            },
            {
                "type": "TextBlock",
                "text": "**CloudComply AI is ready.** Ask me anything about your AWS account security.",
                "wrap": True,
                "spacing": "Medium",
            },
            {
                "type": "TextBlock",
                "text": "Example questions:",
                "weight": "Bolder",
                "size": "Small",
                "spacing": "Medium",
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "→", "value": "Is my AWS account secure?"},
                    {"title": "→", "value": "Who logged in recently?"},
                    {"title": "→", "value": "Are there any open security groups?"},
                    {"title": "→", "value": "Check my S3 bucket permissions"},
                    {"title": "→", "value": "Show recent IAM changes"},
                ],
            },
        ],
    }
    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card_content,
    )


def build_accounts_card(accounts: list, active_account_id: str = "") -> Attachment:
    """
    Render a numbered list of AWS accounts for the `acc` command.
    Active account is highlighted with a checkmark.
    """
    facts = []
    for i, acc in enumerate(accounts, 1):
        acc_id = str(acc.get("_id", ""))
        nickname = acc.get("nickname", acc_id)
        region = acc.get("region", "unknown")
        marker = "✅" if acc_id == active_account_id else f"{i}."
        facts.append({
            "title": f"{marker}  {nickname}",
            "value": region,
        })

    body = [
        {
            "type": "TextBlock",
            "text": "🛡️ Your AWS Accounts",
            "weight": "Bolder",
            "size": "Medium",
            "color": "Accent",
        },
        {
            "type": "TextBlock",
            "text": "Use `switch <number or alias>` to change the active account.",
            "wrap": True,
            "isSubtle": True,
            "size": "Small",
            "spacing": "Small",
        },
        {
            "type": "FactSet",
            "facts": facts,
            "spacing": "Medium",
        },
    ]

    card_content = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": body,
    }
    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card_content,
    )
