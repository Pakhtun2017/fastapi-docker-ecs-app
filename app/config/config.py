import os

FEATURE_SECURITY_GROUPS = os.getenv("FEATURE_SECURITY_GROUPS", "false").lower() == "true"
