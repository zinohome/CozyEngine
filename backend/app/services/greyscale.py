"""Greyscale Service for feature flagging and traffic splitting."""

import hashlib
from typing import Any

from app.core.config.manager import get_config
from app.observability.logging import get_logger

logger = get_logger(__name__)

class GreyscaleService:
    """
    Manages greyscale rollout strategies.
    Supports:
    - User allowlists (User ID)
    - Percentage rollout (User ID hash)
    - Environment gating
    """

    @staticmethod
    def is_enabled(feature: str, user_id: str | None = None, session_id: str | None = None) -> bool:
        """
        Check if a feature is enabled for the given context.
        
        Args:
            feature: Feature flag name (e.g. "new_engine_v3", "realtime_v2")
            user_id: User identifier
            session_id: Session identifier (optional alternative for hashing)
            
        Returns:
            bool: True if feature is enabled
        """
        config = get_config()
        
        # 1. Check if configuration exists
        if not hasattr(config, "greyscale"):
            return True # Default to enabled if no greyscale config (or False? usually default open for main features)
            # Actually, safe default is False for new features, True for legacy?
            # Let's assume features are ON by default unless gated.
            # But "Greyscale" implies gated rollout. 
            # If config is missing, maybe assume GLOBAL enabling? 
            # Let's check a `enabled` flag.
        
        greyscale_config = getattr(config, "greyscale", {})
        if not greyscale_config:
             return True

        feature_rule = greyscale_config.get(feature)
        if not feature_rule:
            return greyscale_config.get("default_behavior", True)

        # 2. Check enabled switch
        if not feature_rule.get("enabled", True):
            return False

        # 3. Check Allowlists (P0)
        allowlist = feature_rule.get("allowlist", [])
        if user_id and user_id in allowlist:
            return True
            
        # 4. Check Blocklists (P0)
        blocklist = feature_rule.get("blocklist", [])
        if user_id and user_id in blocklist:
            return False

        # 5. Check Percentage Rollout (P1)
        percentage = feature_rule.get("percentage", 100)
        if percentage >= 100:
            return True
        if percentage <= 0:
            return False
            
        target_id = user_id or session_id or "anonymous"
        # Deterministic hash
        hash_val = int(hashlib.sha256(f"{feature}:{target_id}".encode()).hexdigest(), 16)
        return (hash_val % 100) < percentage

# Global Instance
greyscale = GreyscaleService()
