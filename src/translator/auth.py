"""
Role-based authentication system for Legal Translator.

Roles:
- admin: Full system access
- translator: Translator (initial translation pass)
- reviewer: Reviewer (quality check and validation)
- compliance_controller: Compliance Controller (legal compliance verification)
- integrator: Integrator (consolidates multiple document translations)

Users are pre-loaded from environment variables.
Format: USER_<N>_USERNAME, USER_<N>_PASSWORD, USER_<N>_ROLES
Example:
  USER_1_USERNAME=john
  USER_1_PASSWORD=secret123
  USER_1_ROLES=admin,translator
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

# Password hashing context (lazy initialization to avoid bcrypt import issues)
_pwd_context: Optional[CryptContextType] = None

def _get_pwd_context() -> CryptContextType:
    """Get password hashing context, initializing lazily."""
    global _pwd_context
    if _pwd_context is None:
        # Initialize bcrypt context lazily to avoid import-time errors
        # The bcrypt version check in passlib can fail during import
        # Wrap in try-except to handle passlib's bug detection gracefully
        try:
            _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            # Trigger initialization by hashing a short test password
            # This avoids the bug detection using a long password
            _pwd_context.hash("test")
        except (ValueError, AttributeError) as e:
            # If initialization fails due to bcrypt issues, try with pbkdf2 as fallback
            import warnings
            warnings.warn(f"bcrypt initialization failed ({e}), using pbkdf2_sha256 as fallback")
            _pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    return _pwd_context

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24 hours default

# Server instance ID - changes on each restart, invalidating all existing tokens
_SERVER_INSTANCE_ID: Optional[str] = None

def get_server_instance_id() -> str:
    """Get or generate server instance ID. Changes on each restart."""
    global _SERVER_INSTANCE_ID
    if _SERVER_INSTANCE_ID is None:
        _SERVER_INSTANCE_ID = secrets.token_urlsafe(16)
    return _SERVER_INSTANCE_ID

# Available roles
ROLES = {
    "admin": "Full system access",
    "translator": "Translator - initial translation pass",
    "reviewer": "Reviewer - quality check and validation",
    "compliance_controller": "Compliance Controller - legal compliance verification",
    "integrator": "Integrator - consolidates multiple document translations",
}


class User:
    """Represents a user with username, password hash, and roles."""
    
    def __init__(self, username: str, password_hash: str, roles: list[str]):
        self.username = username
        self.password_hash = password_hash
        self.roles = set(roles)  # Use set for efficient role checking
        
        # Ensure admin role is always included if user has any role
        if roles and "admin" not in self.roles:
            # Admin is separate, but we track it
            pass
    
    def has_role(self, role: str) -> bool:
        """Check if user has a specific role. Admin has all roles."""
        if "admin" in self.roles:
            return True
        return role in self.roles
    
    def has_any_role(self, *roles: str) -> bool:
        """Check if user has any of the specified roles. Admin has all roles."""
        if "admin" in self.roles:
            return True
        return any(role in self.roles for role in roles)
    
    def to_dict(self) -> dict:
        """Convert user to dictionary (without password)."""
        return {
            "username": self.username,
            "roles": sorted(self.roles),
        }


# In-memory user storage (loaded from env vars)
_users: dict[str, User] = {}
_users_loaded: bool = False


def load_users_from_env() -> dict[str, User]:
    """
    Load users from environment variables.
    
    Format:
    - USER_1_USERNAME=username1
    - USER_1_PASSWORD=password1
    - USER_1_ROLES=role1,role2,role3
    - USER_2_USERNAME=username2
    - USER_2_PASSWORD=password2
    - USER_2_ROLES=role1
    
    Returns dict mapping username -> User object.
    """
    users = {}
    user_index = 1
    
    while True:
        username_key = f"USER_{user_index}_USERNAME"
        password_key = f"USER_{user_index}_PASSWORD"
        roles_key = f"USER_{user_index}_ROLES"
        
        username = os.getenv(username_key)
        password = os.getenv(password_key)
        roles_str = os.getenv(roles_key, "")
        
        if not username or not password:
            # No more users
            break
        
        # Parse roles (comma-separated)
        roles = [r.strip() for r in roles_str.split(",") if r.strip()]
        
        # Validate roles
        invalid_roles = [r for r in roles if r not in ROLES]
        if invalid_roles:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"User {username} has invalid roles: {invalid_roles}. Valid roles: {list(ROLES.keys())}")
            roles = [r for r in roles if r in ROLES]
        
        # If no roles specified, default to empty (user can still login but has no permissions)
        # Admin role can be explicitly added
        
        # Hash password (bcrypt has 72-byte limit, truncate if necessary)
        # Note: We truncate to 72 bytes for hashing
        try:
            password_bytes = password.encode('utf-8')
            if len(password_bytes) > 72:
                # Truncate to 72 bytes for bcrypt compatibility
                password_to_hash = password_bytes[:72].decode('utf-8', errors='ignore')
            else:
                password_to_hash = password
            password_hash = _get_pwd_context().hash(password_to_hash)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to hash password for user {username}: {e}")
            # Skip this user if password hashing fails
            user_index += 1
            continue
        
        # Create user
        user = User(username=username, password_hash=password_hash, roles=roles)
        users[username] = user
        
        user_index += 1
    
    return users


def get_user(username: str) -> Optional[User]:
    """Get user by username. Loads users from env if not already loaded."""
    global _users_loaded
    if not _users_loaded:
        _load_users()
    return _users.get(username)


def _load_users() -> None:
    """Load users from environment variables (called lazily)."""
    global _users, _users_loaded
    if _users_loaded:
        return
    try:
        loaded = load_users_from_env()
        _users.clear()  # Clear existing dict
        _users.update(loaded)  # Update with loaded users
        _users_loaded = True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to load users from environment: {e}", exc_info=True)
        # Don't set _users_loaded = True so it can retry


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    # Handle bcrypt 72-byte limit by truncating if necessary
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        # Truncate to 72 bytes to match how it was hashed
        password_to_verify = password_bytes[:72].decode('utf-8', errors='ignore')
    else:
        password_to_verify = plain_password
    return _get_pwd_context().verify(password_to_verify, hashed_password)


def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    Authenticate a user by username and password.
    
    Returns User object if authentication succeeds, None otherwise.
    """
    user = get_user(username)
    if not user:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary to encode in the token (typically {"sub": username})
        expires_delta: Optional expiration time delta
    
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.
    
    Returns:
        Decoded token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Check if token was issued by current server instance
        # If server restarted, instance ID changed and token is invalid
        token_instance = payload.get("server_instance")
        current_instance = get_server_instance_id()
        # #region agent log
        import json
        debug_log_path = "/Users/enrico/workspace/translator/.cursor/debug.log"
        try:
            with open(debug_log_path, "a") as f:
                f.write(json.dumps({"location":"auth.py:265","message":"Token validation check","data":{"token_instance":token_instance,"current_instance":current_instance,"match":token_instance == current_instance},"timestamp":1735000000000,"sessionId":"debug-session","runId":"run1","hypothesisId":"A"})+"\n")
        except: pass
        # #endregion
        if token_instance != current_instance:
            # Token was issued before server restart - invalid
            # #region agent log
            try:
                with open(debug_log_path, "a") as f:
                    f.write(json.dumps({"location":"auth.py:270","message":"Token instance mismatch - token invalid","data":{"token_instance":token_instance,"current_instance":current_instance},"timestamp":1735000000000,"sessionId":"debug-session","runId":"run1","hypothesisId":"A"})+"\n")
            except: pass
            # #endregion
            return None
        return payload
    except JWTError as e:
        # #region agent log
        try:
            with open(debug_log_path, "a") as f:
                f.write(json.dumps({"location":"auth.py:277","message":"JWT decode error","data":{"error":str(e)},"timestamp":1735000000000,"sessionId":"debug-session","runId":"run1","hypothesisId":"B"})+"\n")
        except: pass
        # #endregion
        return None


# Users will be loaded lazily on first access or explicitly via _load_users()
