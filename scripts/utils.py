"""
Utility functions for temperature database management.

Provides common functionality for:
- Database initialization
- File hashing
- Timestamp conversion
"""

import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo


def get_db_connection(db_path: str) -> sqlite3.Connection:
    """
    Get a connection to the SQLite database.
    
    Args:
        db_path: Path to the .sqlite file
        
    Returns:
        sqlite3.Connection with Row factory enabled
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(db_path: str, schema_path: str) -> None:
    """
    Initialize the database with the schema.
    
    Args:
        db_path: Path to the .sqlite file to create/initialize
        schema_path: Path to the temperature.sql schema file
    """
    schema_file = Path(schema_path)
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_file, 'r') as f:
        schema_sql = f.read()
    
    conn = get_db_connection(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
        print(f"Database initialized: {db_path}")
    finally:
        conn.close()


def compute_file_hash(file_path: str) -> str:
    """
    Compute SHA256 hash of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Hex string of SHA256 hash
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def local_to_utc(local_time_str: str, timezone_name: str = "America/New_York", 
                 fixed_offset: str = None) -> int:
    """
    Convert local timestamp string to UTC epoch seconds.
    
    Handles daylight savings time transitions using the 'fold' attribute.
    During ambiguous times (fall-back), assumes DST is NOT in effect (fold=1).
    
    Args:
        local_time_str: Timestamp string in format recognized by the sensor
        timezone_name: IANA timezone name (e.g., "America/New_York")
        fixed_offset: Optional fixed UTC offset (e.g., "-04:00" for EDT) to bypass DST
        
    Returns:
        Unix epoch seconds in UTC
        
    Raises:
        ValueError: If timestamp cannot be parsed
    """
    # Common iButton format: MM/DD/YY HH:MM:SS AM/PM
    # Try multiple common formats
    formats = [
        "%m/%d/%y %I:%M:%S %p",  # 12/31/24 11:59:59 PM
        "%m/%d/%Y %I:%M:%S %p",  # 12/31/2024 11:59:59 PM
        "%Y-%m-%d %H:%M:%S",      # 2024-12-31 23:59:59
        "%m/%d/%y %H:%M:%S",      # 12/31/24 23:59:59
    ]
    
    dt = None
    for fmt in formats:
        try:
            dt = datetime.strptime(local_time_str, fmt)
            break
        except ValueError:
            continue
    
    if dt is None:
        raise ValueError(f"Could not parse timestamp: {local_time_str}")
    
    # If fixed offset is provided, use it instead of timezone-aware conversion
    if fixed_offset:
        # Parse fixed offset (e.g., "-04:00" or "+05:30")
        sign = 1 if fixed_offset[0] == '+' else -1
        hours, minutes = map(int, fixed_offset[1:].split(':'))
        offset = timedelta(hours=sign*hours, minutes=sign*minutes)
        
        # Apply fixed offset
        utc_dt = dt - offset
        return int(utc_dt.replace(tzinfo=timezone.utc).timestamp())
    
    # Otherwise use timezone-aware conversion with DST handling
    tz = ZoneInfo(timezone_name)
    
    # Handle DST ambiguity: during fall-back, fold=1 means "second occurrence"
    # (i.e., standard time, not DST)
    localized_dt = dt.replace(tzinfo=tz, fold=1)
    
    # Convert to UTC and return epoch seconds
    return int(localized_dt.timestamp())


def file_already_ingested(conn: sqlite3.Connection, sha256: str) -> bool:
    """
    Check if a file has already been ingested.
    
    Args:
        conn: Database connection
        sha256: File hash to check
        
    Returns:
        True if file exists in database
    """
    cursor = conn.execute(
        "SELECT COUNT(*) FROM files WHERE sha256 = ?",
        (sha256,)
    )
    count = cursor.fetchone()[0]
    return count > 0
