#!/usr/bin/env python3
"""
Query temperature data from the database.

Provides convenient Python functions to load temperature data into
pandas DataFrames for analysis.

Usage as a script:
    python query_temperature.py DB_PATH [--deployment NAME] [--sensor REG_NUM]

Usage in Python:
    from query_temperature import load_deployment_data, load_sensor_data
    
    df = load_deployment_data('temperature.db', 'Adak_2025Dec')
    df = load_sensor_data('temperature.db', 'ABC123')
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from utils import get_db_connection


def load_deployment_data(db_path: str, deployment_name: str, 
                        start_time_utc: Optional[int] = None,
                        end_time_utc: Optional[int] = None) -> pd.DataFrame:
    """
    Load all temperature data for a deployment.
    
    Args:
        db_path: Path to SQLite database
        deployment_name: Name of the deployment
        start_time_utc: Optional start time (Unix epoch seconds)
        end_time_utc: Optional end time (Unix epoch seconds)
        
    Returns:
        DataFrame with columns:
            - time_utc: Unix epoch seconds
            - time_utc_iso: ISO format UTC timestamp
            - time_local_text: Original local timestamp string
            - value_c: Temperature in Celsius
            - sensor_registration: Sensor registration number
            - sensor_label: Sensor label (if set)
            - quality_flag: Quality flag (0=good)
    """
    conn = get_db_connection(db_path)
    
    query = """
        SELECT 
            tr.time_utc,
            datetime(tr.time_utc, 'unixepoch') AS time_utc_iso,
            tr.time_local_text,
            tr.value_c,
            s.registration_number AS sensor_registration,
            s.label AS sensor_label,
            tr.quality_flag
        FROM temperature_readings tr
        JOIN sensors s ON tr.sensor_id = s.sensor_id
        JOIN deployments d ON tr.deployment_id = d.deployment_id
        WHERE d.name = ?
    """
    
    params = [deployment_name]
    
    if start_time_utc is not None:
        query += " AND tr.time_utc >= ?"
        params.append(start_time_utc)
    
    if end_time_utc is not None:
        query += " AND tr.time_utc <= ?"
        params.append(end_time_utc)
    
    query += " ORDER BY tr.time_utc, s.registration_number"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return df


def load_sensor_data(db_path: str, registration_number: str,
                    start_time_utc: Optional[int] = None,
                    end_time_utc: Optional[int] = None) -> pd.DataFrame:
    """
    Load all temperature data for a specific sensor.
    
    Args:
        db_path: Path to SQLite database
        registration_number: Sensor registration number
        start_time_utc: Optional start time (Unix epoch seconds)
        end_time_utc: Optional end time (Unix epoch seconds)
        
    Returns:
        DataFrame with columns:
            - time_utc: Unix epoch seconds
            - time_utc_iso: ISO format UTC timestamp
            - time_local_text: Original local timestamp string
            - value_c: Temperature in Celsius
            - deployment_name: Deployment name
            - site: Site name
            - quality_flag: Quality flag (0=good)
    """
    conn = get_db_connection(db_path)
    
    query = """
        SELECT 
            tr.time_utc,
            datetime(tr.time_utc, 'unixepoch') AS time_utc_iso,
            tr.time_local_text,
            tr.value_c,
            d.name AS deployment_name,
            d.site,
            tr.quality_flag
        FROM temperature_readings tr
        JOIN sensors s ON tr.sensor_id = s.sensor_id
        JOIN deployments d ON tr.deployment_id = d.deployment_id
        WHERE s.registration_number = ?
    """
    
    params = [registration_number]
    
    if start_time_utc is not None:
        query += " AND tr.time_utc >= ?"
        params.append(start_time_utc)
    
    if end_time_utc is not None:
        query += " AND tr.time_utc <= ?"
        params.append(end_time_utc)
    
    query += " ORDER BY tr.time_utc"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return df


def load_time_range_data(db_path: str, start_time_utc: int, end_time_utc: int,
                         deployment_name: Optional[str] = None) -> pd.DataFrame:
    """
    Load all temperature data within a time range.
    
    Args:
        db_path: Path to SQLite database
        start_time_utc: Start time (Unix epoch seconds)
        end_time_utc: End time (Unix epoch seconds)
        deployment_name: Optional deployment filter
        
    Returns:
        DataFrame with all temperature data in time range
    """
    conn = get_db_connection(db_path)
    
    query = """
        SELECT 
            tr.time_utc,
            datetime(tr.time_utc, 'unixepoch') AS time_utc_iso,
            tr.time_local_text,
            tr.value_c,
            s.registration_number AS sensor_registration,
            s.label AS sensor_label,
            d.name AS deployment_name,
            d.site,
            tr.quality_flag
        FROM temperature_readings tr
        JOIN sensors s ON tr.sensor_id = s.sensor_id
        JOIN deployments d ON tr.deployment_id = d.deployment_id
        WHERE tr.time_utc BETWEEN ? AND ?
    """
    
    params = [start_time_utc, end_time_utc]
    
    if deployment_name:
        query += " AND d.name = ?"
        params.append(deployment_name)
    
    query += " ORDER BY tr.time_utc, d.name, s.registration_number"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return df


def list_deployments(db_path: str) -> pd.DataFrame:
    """
    List all deployments in the database.
    
    Returns:
        DataFrame with deployment information
    """
    conn = get_db_connection(db_path)
    
    query = """
        SELECT 
            d.deployment_id,
            d.name,
            d.site,
            d.timezone_name,
            COUNT(DISTINCT tr.sensor_id) AS num_sensors,
            COUNT(tr.reading_id) AS num_readings,
            datetime(MIN(tr.time_utc), 'unixepoch') AS first_reading_utc,
            datetime(MAX(tr.time_utc), 'unixepoch') AS last_reading_utc
        FROM deployments d
        LEFT JOIN temperature_readings tr ON d.deployment_id = tr.deployment_id
        GROUP BY d.deployment_id
        ORDER BY d.name
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return df


def list_sensors(db_path: str) -> pd.DataFrame:
    """
    List all sensors in the database.
    
    Returns:
        DataFrame with sensor information
    """
    conn = get_db_connection(db_path)
    
    query = """
        SELECT 
            s.sensor_id,
            s.sensor_type,
            s.part_number,
            s.registration_number,
            s.label,
            COUNT(DISTINCT tr.deployment_id) AS num_deployments,
            COUNT(tr.reading_id) AS num_readings
        FROM sensors s
        LEFT JOIN temperature_readings tr ON s.sensor_id = tr.sensor_id
        GROUP BY s.sensor_id
        ORDER BY s.registration_number
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return df


def list_deployment_sensors(db_path: str, deployment_name: str) -> pd.DataFrame:
    """
    List all sensors used in a specific deployment with their deployment-specific metadata.
    
    Args:
        db_path: Path to SQLite database
        deployment_name: Name of deployment
        
    Returns:
        DataFrame with sensor and location information for the deployment
    """
    conn = get_db_connection(db_path)
    
    query = """
        SELECT 
            s.sensor_id,
            s.label,
            s.registration_number,
            sd.location_notes AS location,
            COUNT(tr.reading_id) AS num_readings,
            datetime(MIN(tr.time_utc), 'unixepoch') AS first_reading_utc,
            datetime(MAX(tr.time_utc), 'unixepoch') AS last_reading_utc
        FROM sensors s
        JOIN sensor_deployments sd ON s.sensor_id = sd.sensor_id
        JOIN deployments d ON sd.deployment_id = d.deployment_id
        JOIN temperature_readings tr ON s.sensor_id = tr.sensor_id AND d.deployment_id = tr.deployment_id
        WHERE d.name = ?
        GROUP BY s.sensor_id
        ORDER BY s.label
    """
    
    df = pd.read_sql_query(query, conn, params=[deployment_name])
    conn.close()
    
    return df


def get_file_summary(db_path: str) -> pd.DataFrame:
    """
    Get summary of all ingested files.
    
    Returns:
        DataFrame with file ingestion summary
    """
    conn = get_db_connection(db_path)
    df = pd.read_sql_query("SELECT * FROM v_file_summary", conn)
    conn.close()
    return df


def main():
    parser = argparse.ArgumentParser(
        description="Query temperature data from database",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('db_path', help='Path to SQLite database file')
    parser.add_argument('--deployment', help='Filter by deployment name')
    parser.add_argument('--sensor', help='Filter by sensor registration number')
    parser.add_argument('--list-deployments', action='store_true',
                       help='List all deployments')
    parser.add_argument('--list-sensors', action='store_true',
                       help='List all sensors')
    parser.add_argument('--list-deployment-sensors', metavar='DEPLOYMENT',
                       help='List sensors for a specific deployment with locations')
    parser.add_argument('--file-summary', action='store_true',
                       help='Show file ingestion summary')
    parser.add_argument('--output', help='Save results to CSV file')
    
    args = parser.parse_args()
    
    # Handle list operations
    if args.list_deployments:
        df = list_deployments(args.db_path)
        print("\n=== Deployments ===")
        print(df.to_string(index=False))
        if args.output:
            df.to_csv(args.output, index=False)
        return
    
    if args.list_sensors:
        df = list_sensors(args.db_path)
        print("\n=== Sensors ===")
        print(df.to_string(index=False))
        if args.output:
            df.to_csv(args.output, index=False)
        return
    
    if args.list_deployment_sensors:
        df = list_deployment_sensors(args.db_path, args.list_deployment_sensors)
        print(f"\n=== Sensors in {args.list_deployment_sensors} ===")
        print(df.to_string(index=False))
        if args.output:
            df.to_csv(args.output, index=False)
        return
    
    if args.file_summary:
        df = get_file_summary(args.db_path)
        print("\n=== File Summary ===")
        print(df.to_string(index=False))
        if args.output:
            df.to_csv(args.output, index=False)
        return
    
    # Load data based on filters
    if args.deployment:
        df = load_deployment_data(args.db_path, args.deployment)
        print(f"\n=== Deployment: {args.deployment} ===")
    elif args.sensor:
        df = load_sensor_data(args.db_path, args.sensor)
        print(f"\n=== Sensor: {args.sensor} ===")
    else:
        print("Please specify --deployment, --sensor, or a list option")
        sys.exit(1)
    
    print(f"Loaded {len(df)} temperature readings")
    print(df.head(10).to_string(index=False))
    
    if args.output:
        df.to_csv(args.output, index=False)
        print(f"\nSaved to: {args.output}")


if __name__ == '__main__':
    main()
