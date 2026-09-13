# SpryteAI Twitch Integration — Multi-Community

SpryteAI uses one Twitch developer application and one shared SpryteAI Twitch bot identity. Every Discord community can authorize its own broadcaster account and gets separate EventSub connections and configuration.

## 1. Deployment-level Twitch setup

Create/register the Twitch developer application and use this callback URL unless you changed it in `.env`:

```text
http://localhost:8765/twitch/callback
```

Set deployment credentials in `.env`:

```dotenv
TWITCH_CLIENT_ID=your_client_id
TWITCH_CLIENT_SECRET=your_client_secret
TWITCH_REDIRECT_URI=http://localhost:8765/twitch/callback
```

Never put the Client Secret or OAuth access/refresh tokens in a community config.

## 2. Authorize the shared SpryteAI Twitch bot once

The SpryteAI deployment owner runs:

```text
/twitch authorize account:bot
```

Sign into the separate Twitch account used by SpryteAI chat. This authorization is shared across every community.

Bot scopes:

```text
user:read:chat
user:write:chat
user:bot
```

## 3. Authorize each community broadcaster

Inside that community's Discord guild, a server Administrator runs:

```text
/twitch authorize account:broadcaster
```

Sign into that community's broadcaster Twitch account. SpryteAI stores it as `broadcaster:<community_id>` and binds the Twitch broadcaster to that community only.

Broadcaster scopes:

```text
channel:bot
channel:manage:broadcast
channel:read:subscriptions
bits:read
channel:manage:redemptions
moderator:read:followers
moderator:manage:announcements
moderator:manage:shoutouts
moderator:manage:banned_users
channel:manage:polls
clips:edit
```

## 4. Check a community

```text
/twitch status
/twitch reconnect
```

Both commands resolve the community from the Discord guild where they are run.

## Discord Twitch commands

```text
/twitch status
/twitch authorize
/twitch reconnect
/twitch say
/twitch title
/twitch game
/twitch announcement
/twitch shoutout
/twitch clip
/twitch poll
/twitch timeout
/twitch ban
/twitch unban
/twitch link
/twitch unlink
/twitch syncroles
```

Community-management commands require Discord Administrator permission (the deployment owner also has access). Linking/unlinking is available to normal members for their own identity.

## Twitch chat commands

```text
!commands
!discord
!socials
!uptime
!followage
!lurk
!link CODE
!catch <pokemon name>
!pokemon
!list
!dex
```

Broadcasters/moderators also have:

```text
!title <title>
!game <category>
!so <streamer>
!clip
```

The command prefix and static replies come from that community's merged `twitch.chat` configuration.

## Discord ↔ Twitch account linking

A Discord member runs:

```text
/twitch link
```

Then types the returned one-time code in the bound Twitch channel:

```text
!link ABC123
```

Codes are community-bound, so a code issued in Community A cannot be consumed in Community B. If the Twitch viewer already caught Pokémon before linking, SpryteAI merges that Twitch-only player into the Discord player and preserves the game data.

## Twitch Pokécord visuals

Twitch chat cannot render the Discord spawn attachment, so SpryteAI includes the wild Pokémon's official artwork URL in the Twitch spawn announcement by default. Disable it for a community with:

```text
/community config-set path:twitch.chat.pokecord_image_links value:false
```

The Discord and Twitch catch commands still target the same wild spawn and use the same capture lock.

## Per-community Twitch/Discord settings

Community Administrators can override safe settings without editing the host configuration:

```text
/community config-set path:twitch.chat.prefix value:"?"
/community config-set path:twitch.discord.announce_subs value:true
/community config-set path:twitch.discord.announce_follows value:false
/community feature feature:twitch enabled:false
```

Twitch Client ID, Client Secret, redirect URI, and OAuth tokens remain deployment-controlled.

## Token storage

OAuth tokens remain in the deployment's git-ignored token store. Keys are:

```text
bot
broadcaster:<community_id>
```

A legacy `broadcaster` token is migrated to the first eligible community when possible.
