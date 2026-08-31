# Nawaf — feature set

## Tickets
- Configurable ticket panel title and description.
- Ticket category configuration.
- Owner cannot close their own ticket.
- Rating from 1 to 10 with optional note.
- Rating buttons remain available after bot restart.
- Optional ticket close log channel.

## Applications
- Multiple application types.
- Up to 10 configurable questions per type.
- Custom panel title, description, color and image.
- Review channel and result channel.
- Accept/reject workflow with optional reason.
- Optional role automatically granted on acceptance.
- Applicant receives the result by DM when possible.

## Levels
- XP and levels per server/member.
- XP is rate-limited to reduce message spam farming.
- Configurable role reward for any level.
- Dedicated `/level-image-role` command for an image/media role milestone.

## Economy + Shop
- Server-specific currency name and symbol.
- Detailed balance and top-balance commands.
- Transfer, add, remove, set and reset balance.
- Generic products, role products and advertisement products.
- Advertisement purchase collects ad text and optional image URL.
- Orders are sent to a configurable order channel.
- Role products can be delivered automatically when the bot has permission.

## Moderation + Messaging
- Send a message to a selected channel.
- Send a private message to a selected member.
- Configurable jail role.
- Jail and unjail commands with role restoration.
- Optional timed jail with automatic release.

## Dhikr + announcements
- Automatic dhikr messages with configurable channel and interval.
- Server announcement command.

## Stack
Python / discord.py 2.x / SQLite / python-dotenv.
