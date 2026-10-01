"""Biorce Kudos bot.

/kudos opens a modal: pick a person, pick a kudos type (grouped by company
value) or Custom, edit the message, choose public or private.

Public  -> posted by the bot to the kudos channel (emoji reactions work natively).
Private -> DM to the recipient only, giver named (never anonymous).

No stats, no history features. Self-kudos and kudos to bots are blocked.

Env vars:
  SLACK_BOT_TOKEN   xoxb-...   (OAuth bot token)
  SLACK_APP_TOKEN   xapp-...   (app-level token with connections:write, for Socket Mode)
  KUDOS_CHANNEL     channel ID of the public kudos channel, e.g. C0123456789
"""

import logging
import os

# Load a .env file sitting next to this script, if present (no dependency needed)
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

import yaml
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("kudos")

KUDOS_CHANNEL = os.environ["KUDOS_CHANNEL"]

CUSTOM_ID = "custom"
NO_VALUE_ID = "none"

# ---------------------------------------------------------------- templates

with open(os.path.join(os.path.dirname(__file__), "templates.yaml")) as f:
    _cfg = yaml.safe_load(f)

VALUES = _cfg["values"]  # {value_id: {name, emoji}}
TEMPLATES = {t["id"]: t for t in _cfg["templates"]}


def template_option_groups():
    """Build the grouped dropdown: one group per value, plus Custom."""
    groups = []
    for vid, v in VALUES.items():
        options = [
            {
                "text": {"type": "plain_text", "text": t["heading"]},
                "value": t["id"],
            }
            for t in _cfg["templates"]
            if t["value"] == vid
        ]
        if options:
            groups.append(
                {
                    "label": {"type": "plain_text", "text": f"{v['emoji']} {v['name']}"},
                    "options": options,
                }
            )
    groups.append(
        {
            "label": {"type": "plain_text", "text": "✏️ Your own words"},
            "options": [
                {
                    "text": {"type": "plain_text", "text": "Custom kudos"},
                    "value": CUSTOM_ID,
                }
            ],
        }
    )
    return groups


def value_options():
    opts = [
        {
            "text": {"type": "plain_text", "text": f"{v['emoji']} {v['name']}"},
            "value": vid,
        }
        for vid, v in VALUES.items()
    ]
    opts.append(
        {
            "text": {"type": "plain_text", "text": "No value tag"},
            "value": NO_VALUE_ID,
        }
    )
    return opts


# ------------------------------------------------------------------- modal


def build_modal(
    selected_template=None,
    recipient=None,
    visibility="public",
    custom_value=None,
):
    """Build the kudos modal.

    The message input's block_id embeds the selected template id so that
    switching templates re-renders the input with a fresh prefill (Slack
    keeps typed values for unchanged block_ids, so changing it is how we
    swap the prefill).
    """
    tid = selected_template or ""
    template = TEMPLATES.get(tid)
    is_custom = tid == CUSTOM_ID

    recipient_el = {
        "type": "users_select",
        "action_id": "recipient",
        "placeholder": {"type": "plain_text", "text": "Who deserves it?"},
    }
    if recipient:
        recipient_el["initial_user"] = recipient

    template_el = {
        "type": "static_select",
        "action_id": "template_select",
        "placeholder": {"type": "plain_text", "text": "Pick a kudos type"},
        "option_groups": template_option_groups(),
    }
    if template:
        template_el["initial_option"] = {
            "text": {"type": "plain_text", "text": template["heading"]},
            "value": tid,
        }
    elif is_custom:
        template_el["initial_option"] = {
            "text": {"type": "plain_text", "text": "Custom kudos"},
            "value": CUSTOM_ID,
        }

    message_block = {
        "type": "input",
        # template id in the block_id forces a re-render (new prefill) on change
        "block_id": f"message__{tid or 'blank'}",
        "label": {"type": "plain_text", "text": "Message"},
        "element": {
            "type": "plain_text_input",
            "action_id": "message",
            "multiline": True,
            "placeholder": {
                "type": "plain_text",
                "text": "Say what they did and why it mattered",
            },
        },
    }
    if template and template.get("prompt"):
        message_block["element"]["initial_value"] = template["prompt"]

    visibility_el = {
        "type": "radio_buttons",
        "action_id": "visibility",
        "options": [
            {
                "text": {"type": "plain_text", "text": "🌍 Public — posted in the kudos channel"},
                "value": "public",
            },
            {
                "text": {"type": "plain_text", "text": "🔒 Private — only they see it (from you, never anonymous)"},
                "value": "private",
            },
        ],
        "initial_option": None,
    }
    visibility_el["initial_option"] = visibility_el["options"][0 if visibility == "public" else 1]

    blocks = [
        {
            "type": "input",
            "block_id": "recipient_block",
            "label": {"type": "plain_text", "text": "Give kudos to"},
            "element": recipient_el,
        },
        {
            "type": "input",
            "block_id": "template_block",
            "dispatch_action": True,
            "label": {"type": "plain_text", "text": "Kudos type"},
            "element": template_el,
        },
    ]

    # Custom kudos: optional heading + optional value tag
    if is_custom:
        blocks.append(
            {
                "type": "input",
                "block_id": "custom_heading_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "Heading (optional)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "custom_heading",
                    "max_length": 60,
                    "placeholder": {"type": "plain_text", "text": "e.g. Legendary debugging"},
                },
            }
        )
        value_el = {
            "type": "static_select",
            "action_id": "custom_value",
            "options": value_options(),
        }
        if custom_value:
            match = next(o for o in value_options() if o["value"] == custom_value)
            value_el["initial_option"] = match
        blocks.append(
            {
                "type": "input",
                "block_id": "custom_value_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "Link to a value (optional)"},
                "element": value_el,
            }
        )

    blocks.append(message_block)
    blocks.append(
        {
            "type": "input",
            "block_id": "visibility_block",
            "label": {"type": "plain_text", "text": "Visibility"},
            "element": visibility_el,
        }
    )

    return {
        "type": "modal",
        "callback_id": "kudos_submit",
        "title": {"type": "plain_text", "text": "Hear ye! Give kudos 🔔"},
        "submit": {"type": "plain_text", "text": "Proclaim!"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }


def _state_get(state_values, block_prefix, action_id, key):
    """Pull a value out of view state, tolerant of dynamic block_ids."""
    for block_id, actions in state_values.items():
        if block_id.startswith(block_prefix) and action_id in actions:
            return actions[action_id].get(key)
    return None


# ------------------------------------------------------------------ app

app = App(token=os.environ["SLACK_BOT_TOKEN"])


@app.command("/kudos")
def open_kudos_modal(ack, body, client):
    ack()
    client.views_open(trigger_id=body["trigger_id"], view=build_modal())


@app.action("template_select")
def on_template_change(ack, body, client):
    ack()
    state = body["view"]["state"]["values"]
    selected = body["actions"][0]["selected_option"]["value"]

    # preserve what the user already picked
    recipient = _state_get(state, "recipient_block", "recipient", "selected_user")
    vis_opt = _state_get(state, "visibility_block", "visibility", "selected_option")
    visibility = vis_opt["value"] if vis_opt else "public"
    cv_opt = _state_get(state, "custom_value_block", "custom_value", "selected_option")
    custom_value = cv_opt["value"] if cv_opt else None

    client.views_update(
        view_id=body["view"]["id"],
        hash=body["view"]["hash"],
        view=build_modal(
            selected_template=selected,
            recipient=recipient,
            visibility=visibility,
            custom_value=custom_value,
        ),
    )


@app.view("kudos_submit")
def handle_submission(ack, body, client, logger):
    state = body["view"]["state"]["values"]
    giver = body["user"]["id"]

    recipient = _state_get(state, "recipient_block", "recipient", "selected_user")
    tmpl_opt = _state_get(state, "template_block", "template_select", "selected_option")
    message = (_state_get(state, "message__", "message", "value") or "").strip()
    vis_opt = _state_get(state, "visibility_block", "visibility", "selected_option")
    visibility = vis_opt["value"] if vis_opt else "public"

    errors = {}
    if not tmpl_opt:
        errors["template_block"] = "Pick a kudos type (or Custom)."
    if recipient == giver:
        errors["recipient_block"] = "Kudos are for teammates — you can't send them to yourself. 😄"
    if not message:
        # find the actual message block_id for the error key
        mb = next((b for b in state if b.startswith("message__")), "message__blank")
        errors[mb] = "Say a few words — that's the whole point!"
    if errors:
        ack(response_action="errors", errors=errors)
        return

    # block bots as recipients
    try:
        info = client.users_info(user=recipient)["user"]
        if info.get("is_bot") or info.get("id") == "USLACKBOT":
            ack(
                response_action="errors",
                errors={"recipient_block": "Bots have no feelings. Pick a human. 🤖"},
            )
            return
    except Exception as e:  # noqa: BLE001 - fail open on lookup errors
        logger.warning("users_info failed: %s", e)

    ack()

    tid = tmpl_opt["value"]
    if tid == CUSTOM_ID:
        heading = (_state_get(state, "custom_heading_block", "custom_heading", "value") or "Kudos").strip() or "Kudos"
        cv_opt = _state_get(state, "custom_value_block", "custom_value", "selected_option")
        value_id = cv_opt["value"] if cv_opt else NO_VALUE_ID
    else:
        t = TEMPLATES[tid]
        heading = t["heading"]
        value_id = t["value"]

    if value_id != NO_VALUE_ID and value_id in VALUES:
        v = VALUES[value_id]
        value_tag = f"{v['emoji']} {v['name']}"
    else:
        value_tag = None

    tagline = f"  ·  {value_tag}" if value_tag else ""
    quoted = "\n".join(f"> {line}" for line in message.splitlines())

    if visibility == "public":
        client.chat_postMessage(
            channel=KUDOS_CHANNEL,
            text=f"Hear ye! Kudos from <@{giver}> to <@{recipient}>: {heading}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"🔔 *Hear ye, hear ye!* <@{giver}> proclaims kudos unto <@{recipient}>:\n"
                            f"*{heading}*{tagline}\n{quoted}"
                        ),
                    },
                }
            ],
        )
        confirmation = f"📜 Thy kudos to <@{recipient}> hath been proclaimed in <#{KUDOS_CHANNEL}>!"
    else:
        client.chat_postMessage(
            channel=recipient,
            text=f"Private kudos from <@{giver}>: {heading}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"🔔 *Hear ye! A private proclamation, for thine eyes only.*\n"
                            f"*{heading}*{tagline}  —  from <@{giver}>\n{quoted}"
                        ),
                    },
                }
            ],
        )
        confirmation = f"📜 Thy private kudos was delivered to <@{recipient}>. None other shall know of it."

    client.chat_postMessage(channel=giver, text=confirmation)


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
