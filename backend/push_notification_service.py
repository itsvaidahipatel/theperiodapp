"""
Push notification service (FCM placeholder).

This file intentionally keeps Firebase initialization lightweight so we can
switch from email reminders to push flows without blocking on infra setup.
"""

from __future__ import annotations

import os
from typing import Optional

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
except ImportError:  # pragma: no cover - optional until firebase-admin is installed
    firebase_admin = None
    credentials = None
    messaging = None

from database import supabase


_firebase_initialized = False


def _init_firebase_admin() -> bool:
    """
    Initialize firebase-admin SDK if available and configured.
    Returns False when SDK/config is missing so callers can degrade gracefully.
    """
    global _firebase_initialized
    if _firebase_initialized:
        return True
    if firebase_admin is None:
        return False

    if firebase_admin._apps:
        _firebase_initialized = True
        return True

    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "").strip()
    if not cred_path:
        return False
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        return True
    except Exception as exc:
        print(f"⚠️ Firebase admin initialization failed: {exc}")
        return False


def _fetch_user_fcm_token(user_id: str) -> Optional[str]:
    try:
        res = supabase.table("users").select("fcm_token").eq("id", user_id).limit(1).execute()
        if not res.data:
            return None
        token = (res.data[0] or {}).get("fcm_token")
        if isinstance(token, str) and token.strip():
            return token.strip()
    except Exception as exc:
        print(f"⚠️ Failed to fetch FCM token for user {user_id}: {exc}")
    return None


def send_push_notification(user_id: str, title: str, body: str, category: str = "general") -> bool:
    """
    Send a push notification to the user's stored FCM device token.

    If Firebase isn't configured yet, this logs a placeholder event and returns
    False so jobs remain non-blocking in local/dev setups.
    """
    token = _fetch_user_fcm_token(user_id)
    if not token:
        print(f"ℹ️ No FCM token for user {user_id}; skipping push ({category})")
        return False

    if not _init_firebase_admin():
        print(f"ℹ️ FCM placeholder (firebase-admin not ready) user={user_id} category={category} title={title}")
        return False

    try:
        message = messaging.Message(
            token=token,
            notification=messaging.Notification(title=title, body=body),
            data={"category": category},
        )
        messaging.send(message)
        return True
    except Exception as exc:
        print(f"❌ Failed push notification for user {user_id}: {exc}")
        return False
