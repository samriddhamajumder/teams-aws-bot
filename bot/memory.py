# bot/memory.py
# Ultimate user memory store for Teams Bot + CrewAI (thread-safe + optional Redis)

import threading
import os
import json
import ast

try:
    import redis
except ImportError:
    redis = None

USE_REDIS = bool(os.getenv("REDIS_URL")) and redis is not None
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class MemoryStore:
    """
    Multi-user session memory store
    Priority → Redis (if available) → else thread-safe local memory
    """
    _lock = threading.Lock()
    _store = {}

    if USE_REDIS:
        _client = redis.Redis.from_url(REDIS_URL)
        print(f"✅ Memory: using Redis backend → {REDIS_URL}")
    else:
        print("✅ Memory: using local in-memory store")

    @classmethod
    def _get_user_session(cls, user_id):
        if USE_REDIS:
            value = cls._client.get(user_id)
            return json.loads(value.decode()) if value else {
                "last_intent": None,
                "last_action": None,
                "last_entity": None,
                "context": {}
            }

        with cls._lock:
            if user_id not in cls._store:
                cls._store[user_id] = {
                    "last_intent": None,
                    "last_action": None,
                    "last_entity": None,
                    "context": {}
                }
            return cls._store[user_id]

    @classmethod
    def update(cls, user_id, intent=None, action=None, entity=None, context=None):
        """
        Update session memory for a user
        """
        if USE_REDIS:
            value = cls._client.get(user_id)
            session = ast.literal_eval(value.decode()) if value else {
                "last_intent": None,
                "last_action": None,
                "last_entity": None,
                "context": {}
        }
        else:
            with cls._lock:
                session = cls._store.get(user_id, {
                    "last_intent": None,
                    "last_action": None,
                    "last_entity": None,
                    "context": {}
            })

    # Update values
        if intent is not None:
            session["last_intent"] = intent
        if action is not None:
            session["last_action"] = action
        if entity is not None:
            session["last_entity"] = entity
        if context is not None:
            session["context"].update(context)

    # Save back
        if USE_REDIS:
            cls._client.setex(user_id, 3600, json.dumps(session))
        else:
            with cls._lock:
                cls._store[user_id] = session

    @classmethod
    def get(cls, user_id):
        """
        Get current session memory for a user
        """
        return cls._get_user_session(user_id)

    @classmethod
    def clear(cls, user_id):
        """
        Reset session memory for a user
        """
        if USE_REDIS:
            cls._client.delete(user_id)
        else:
            with cls._lock:
                if user_id in cls._store:
                    del cls._store[user_id]
