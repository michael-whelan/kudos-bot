# Biorce Kudos bot

Slack bot for giving teammates kudos tied to company values (Excellence,
Ownership, Ambition). `/kudos` opens a modal: pick a person, pick a kudos
type or write a custom one, choose public or private.

Public kudos are posted to the kudos channel, where anyone can react with
emoji. Private kudos go as a DM to the recipient only, always naming the
giver. No stats, no leaderboards. Self-kudos and kudos to bots are blocked.

## Files

- `app.py` — the whole bot (Bolt for Python, Socket Mode)
- `templates.yaml` — values and kudos templates; edit this to change the list
- `slack_app_manifest.yaml` — paste into Slack to create the app
- `requirements.txt`, `Procfile` — dependencies and Railway start command

## Setup, part 1: Slack (5 minutes)

1. Go to api.slack.com/apps, Create New App, From an app manifest, pick your
   workspace, paste the contents of `slack_app_manifest.yaml`.
2. Basic Information, App-Level Tokens: generate a token with scope
   `connections:write`. Save it — this is `SLACK_APP_TOKEN` (xapp-...).
3. Install App to Workspace. Copy the Bot User OAuth Token — this is
   `SLACK_BOT_TOKEN` (xoxb-...).
4. Create (or pick) the public kudos channel, e.g. `#kudos`, and invite the
   bot to it (`/invite @Kudos` in the channel). Copy the channel ID (channel
   details, bottom of the About tab) — this is `KUDOS_CHANNEL` (C0...).

## Setup, part 2: Railway (5 minutes)

1. Push this folder to a GitHub repo (or use `railway up` from the CLI).
2. In your Railway project, create a service from that repo.
3. Set environment variables on the service: `SLACK_BOT_TOKEN`,
   `SLACK_APP_TOKEN`, `KUDOS_CHANNEL`.
4. Set the start command to `python app.py` if Railway does not pick up the
   Procfile automatically. No public domain/port is needed — Socket Mode
   connects outward to Slack.
5. Deploy. Logs should show a successful Socket Mode connection.

Test it: type `/kudos` anywhere in Slack.

## Editing templates

Everything people can pick lives in `templates.yaml`. Add a template by
appending a block with a unique `id`, one of the `value` keys, a `heading`
(what shows in the dropdown and the posted message) and a `prompt` (the
editable prefill). Redeploy to apply.

## Behavior details

- Switching kudos type in the modal re-prefills the message box, replacing
  whatever was typed there. Recipient and visibility choices are preserved.
- Custom kudos get an optional heading and an optional value tag.
- Private kudos are a DM from the bot; the giver gets a DM confirmation.
- The bot must be a member of the kudos channel to post there.

Owner: Michael Whelan. Next step: deploy to Railway and run a team pilot in
#kudos for two weeks before announcing company-wide.
