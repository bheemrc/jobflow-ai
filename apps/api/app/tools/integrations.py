"""Integration tools: send notifications, call webhooks."""

from __future__ import annotations

import json
import logging
import os

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def send_notification(channel: str, message: str, bot_name: str = "") -> str:
    """Send a notification through a configured channel (Telegram, Slack, Discord, or webhook).

    Use this tool to send bot outputs, alerts, or reports to external platforms.
    The channel must be pre-configured in the bot's integration settings.

    Args:
        channel: The channel type — "telegram", "slack", "discord", or "webhook".
        message: The message text to send. Supports markdown formatting.
        bot_name: The bot sending the notification (for attribution in the message).

    Returns:
        JSON with delivery status.
    """
    try:
        channel = channel.lower().strip()
        supported = ("telegram", "slack", "discord", "webhook")
        if channel not in supported:
            return json.dumps({
                "sent": False,
                "error": f"Unknown channel '{channel}'. Supported: {', '.join(supported)}.",
            })

        sender = bot_name or "Nexus Bot"

        # ── Telegram ──────────────────────────────────────────
        if channel == "telegram":
            token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
            if not token:
                return json.dumps({"sent": False, "channel": "telegram",
                                   "error": "TELEGRAM_BOT_TOKEN not configured."})
            if not chat_id:
                return json.dumps({"sent": False, "channel": "telegram",
                                   "error": "TELEGRAM_CHAT_ID not configured."})

            # Telegram limit is 4096 chars; split if needed
            header = f"*{sender}*\n\n"
            max_len = 4096 - len(header)
            chunks = [message[i:i + max_len] for i in range(0, len(message), max_len)]

            api_url = f"https://api.telegram.org/bot{token}/sendMessage"
            sent_count = 0
            with httpx.Client(timeout=15) as client:
                for chunk in chunks:
                    text = header + chunk if sent_count == 0 else chunk
                    resp = client.post(api_url, json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True,
                    })
                    if resp.status_code == 200:
                        sent_count += 1
                    else:
                        return json.dumps({
                            "sent": False, "channel": "telegram",
                            "error": f"Telegram API error {resp.status_code}: {resp.text[:300]}",
                            "chunks_sent": sent_count,
                        })

            return json.dumps({"sent": True, "channel": "telegram",
                               "chunks_sent": sent_count})

        # ── Slack ─────────────────────────────────────────────
        if channel == "slack":
            webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
            if not webhook_url:
                return json.dumps({"sent": False, "channel": "slack",
                                   "error": "SLACK_WEBHOOK_URL not configured."})

            payload = {
                "text": f"*{sender}*\n{message}",
                "username": sender,
                "icon_emoji": ":robot_face:",
            }
            with httpx.Client(timeout=15) as client:
                resp = client.post(webhook_url, json=payload)
                if resp.status_code == 200:
                    return json.dumps({"sent": True, "channel": "slack"})
                return json.dumps({"sent": False, "channel": "slack",
                                   "error": f"Slack returned {resp.status_code}: {resp.text[:300]}"})

        # ── Discord ───────────────────────────────────────────
        if channel == "discord":
            webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
            if not webhook_url:
                return json.dumps({"sent": False, "channel": "discord",
                                   "error": "DISCORD_WEBHOOK_URL not configured."})

            # Discord limit is 2000 chars
            content = f"**{sender}**\n{message}"
            if len(content) > 2000:
                content = content[:1997] + "..."

            payload = {"content": content, "username": sender}
            with httpx.Client(timeout=15) as client:
                resp = client.post(webhook_url, json=payload)
                if resp.status_code in (200, 204):
                    return json.dumps({"sent": True, "channel": "discord"})
                return json.dumps({"sent": False, "channel": "discord",
                                   "error": f"Discord returned {resp.status_code}: {resp.text[:300]}"})

        # ── Generic webhook ───────────────────────────────────
        if channel == "webhook":
            webhook_url = os.environ.get("WEBHOOK_URL", "")
            if not webhook_url:
                return json.dumps({"sent": False, "channel": "webhook",
                                   "error": "WEBHOOK_URL not configured."})

            from datetime import datetime, timezone
            payload = {
                "source": "jobflow",
                "bot_name": sender,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            with httpx.Client(timeout=15) as client:
                resp = client.post(webhook_url, json=payload)
                resp.raise_for_status()
            return json.dumps({"sent": True, "channel": "webhook",
                               "status_code": resp.status_code})

        return json.dumps({"sent": False, "error": "Unhandled channel."})
    except Exception as e:
        logger.error("send_notification error: %s", e)
        return json.dumps({"sent": False, "error": str(e)})


@tool
def call_webhook(url: str, method: str = "POST", payload: str = "{}") -> str:
    """Call an external webhook or API endpoint.

    Use this tool to integrate with external services, MCP servers, or custom APIs.
    The bot can use this to send data to any HTTP endpoint.

    Args:
        url: The full URL of the webhook or API endpoint.
        method: HTTP method — "GET" or "POST". Default: "POST".
        payload: JSON string payload for POST requests.

    Returns:
        JSON with the response status and body preview.
    """
    try:
        method = method.upper().strip()
        if method not in ("GET", "POST"):
            return json.dumps({"error": "Only GET and POST methods are supported."})

        # Security: only allow https and known safe domains
        if not url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            return json.dumps({"error": "Only HTTPS URLs or localhost are allowed for security."})

        with httpx.Client(timeout=30) as client:
            if method == "POST":
                try:
                    body = json.loads(payload)
                except json.JSONDecodeError:
                    return json.dumps({"error": "Invalid JSON payload."})
                resp = client.post(url, json=body)
            else:
                resp = client.get(url)

            return json.dumps({
                "status_code": resp.status_code,
                "body_preview": resp.text[:2000],
                "headers": dict(list(resp.headers.items())[:10]),
            })
    except Exception as e:
        logger.error("call_webhook error: %s", e)
        return json.dumps({"error": f"Webhook call failed: {e}"})
