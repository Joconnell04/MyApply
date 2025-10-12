"""Input validation and sanitization utilities for MyApply."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException, status


def sanitize_string(value: str, max_length: int = 1000, strip: bool = True) -> str:
    """
    Sanitize string input by removing dangerous characters and limiting length.

    Args:
        value: The string to sanitize
        max_length: Maximum allowed length
        strip: Whether to strip whitespace

    Returns:
        Sanitized string
    """
    if strip:
        value = value.strip()

    # Remove null bytes and control characters
    value = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', value)

    # Limit length
    if len(value) > max_length:
        value = value[:max_length]

    return value


def validate_email(email: str) -> str:
    """
    Validate and sanitize email address.

    Args:
        email: Email address to validate

    Returns:
        Sanitized email

    Raises:
        HTTPException: If email is invalid
    """
    email = sanitize_string(email, max_length=254).lower()

    # Basic email pattern
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )

    return email


def validate_password(password: str, min_length: int = 8, max_length: int = 72) -> str:
    """
    Validate password strength.

    Args:
        password: Password to validate
        min_length: Minimum password length
        max_length: Maximum password length (bcrypt limit is 72 bytes)

    Returns:
        The validated password

    Raises:
        HTTPException: If password is invalid
    """
    if not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required"
        )

    if len(password) < min_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {min_length} characters long"
        )

    # Check byte length for bcrypt
    if len(password.encode('utf-8')) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password is too long (max {max_length} bytes)"
        )

    return password


def validate_url(url: str, require_https: bool = False) -> str:
    """
    Validate and sanitize URL.

    Args:
        url: URL to validate
        require_https: Whether to require HTTPS

    Returns:
        Sanitized URL

    Raises:
        HTTPException: If URL is invalid
    """
    url = sanitize_string(url, max_length=2048).strip()

    if not url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL cannot be empty"
        )

    try:
        parsed = urlparse(url)

        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL structure")

        if require_https and parsed.scheme != 'https':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="HTTPS URL required"
            )

        if parsed.scheme not in ('http', 'https'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only HTTP and HTTPS URLs are allowed"
            )

        return url

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid URL: {str(e)}"
        )


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and other attacks.

    Args:
        filename: Filename to sanitize

    Returns:
        Safe filename
    """
    # Remove path separators and null bytes
    filename = re.sub(r'[/\\:\x00]', '', filename)

    # Remove leading dots to prevent hidden files
    filename = filename.lstrip('.')

    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + ('.' + ext if ext else '')

    return filename or 'unnamed'


def validate_text_length(
    text: str,
    field_name: str,
    min_length: int = 0,
    max_length: Optional[int] = None
) -> str:
    """
    Validate text length constraints.

    Args:
        text: Text to validate
        field_name: Name of the field for error messages
        min_length: Minimum required length
        max_length: Maximum allowed length

    Returns:
        The validated text

    Raises:
        HTTPException: If validation fails
    """
    text = text.strip()

    if len(text) < min_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be at least {min_length} characters long"
        )

    if max_length and len(text) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} cannot exceed {max_length} characters"
        )

    return text


def sanitize_html(text: str) -> str:
    """
    Basic HTML sanitization - removes all HTML tags.
    For more complex needs, consider using bleach or html5lib.

    Args:
        text: Text potentially containing HTML

    Returns:
        Text with HTML tags removed
    """
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Decode common HTML entities
    entities = {
        '&lt;': '<',
        '&gt;': '>',
        '&amp;': '&',
        '&quot;': '"',
        '&#39;': "'",
        '&nbsp;': ' ',
    }

    for entity, char in entities.items():
        text = text.replace(entity, char)

    return text


def validate_json_size(json_str: str, max_size_mb: float = 10.0) -> None:
    """
    Validate JSON size to prevent memory exhaustion.

    Args:
        json_str: JSON string to validate
        max_size_mb: Maximum size in megabytes

    Raises:
        HTTPException: If JSON is too large
    """
    size_bytes = len(json_str.encode('utf-8'))
    max_bytes = int(max_size_mb * 1024 * 1024)

    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"JSON payload too large (max {max_size_mb}MB)"
        )
