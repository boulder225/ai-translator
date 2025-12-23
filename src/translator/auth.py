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

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24 hours default

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
        
        # Hash password
        password_hash = pwd_context.hash(password)
        
        # Create user
        user = User(username=username, password_hash=password_hash, roles=roles)
        users[username] = user
        
        user_index += 1
    
    return users


def get_user(username: str) -> Optional[User]:
    """Get user by username."""
    return _users.get(username)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


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
        return payload
    except JWTError:
        return None


# Initialize users on module import
_users = load_users_from_env()
