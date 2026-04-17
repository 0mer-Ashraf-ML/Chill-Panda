"""
One-time migration: backfill `title` field on existing sessions.

For each session without a title, finds the most recent user message
from chat_history and writes the first 100 chars as the title.

Run once:
    python migrate_session_titles.py
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()


def run():
    client = MongoClient(
        os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        serverSelectionTimeoutMS=5000,
    )
    db = client[os.getenv("MONGODB_DATABASE", "chillpanda_db")]
    sessions_col = db[os.getenv("MONGODB_SESSIONS_COLLECTION", "user_sessions")]
    chats_col = db[os.getenv("MONGODB_CHATS_COLLECTION", "chat_history")]

    # Only target sessions that don't have a title yet
    sessions_without_title = list(
        sessions_col.find({"title": {"$exists": False}}, {"session_id": 1})
    )

    print(f"Found {len(sessions_without_title)} sessions without a title.")

    updated = 0
    skipped = 0

    for session in sessions_without_title:
        session_id = session["session_id"]

        # Get the last user message for this session
        last_user_msg = chats_col.find_one(
            {"session_id": session_id, "role": "user"},
            {"content": 1},
            sort=[("timestamp", -1)],
        )

        if not last_user_msg or not last_user_msg.get("content"):
            skipped += 1
            continue

        title = last_user_msg["content"][:100]
        sessions_col.update_one(
            {"session_id": session_id},
            {"$set": {"title": title}},
        )
        updated += 1

    print(f"Done. Updated: {updated}, Skipped (no user messages): {skipped}")
    client.close()


if __name__ == "__main__":
    run()
