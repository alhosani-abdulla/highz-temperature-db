#!/bin/bash
#
# Example: Ingest temperature data from a deployment
#
# This script shows how to ingest CSV files from iButton sensors
# into the temperature database.
#

# Configuration - CUSTOMIZE THESE PATHS FOR YOUR SETUP
DB_PATH="/path/to/temperature.db"
DEPLOYMENT_DIR="/path/to/Data/temp_raw/Adak/2025Dec"

# Note: All deployment metadata (deployment name, site, timezone, sensors)
# is read from deployment_metadata.json in the deployment directory.
# See ../examples/deployment_metadata_template.json for the required format.

# Initialize database (first time only)
echo "=== Initializing database ==="
cd "$(dirname "$0")/../scripts"
python ingest_ibutton_csv.py "$DB_PATH" "$DEPLOYMENT_DIR" --init-db 2>/dev/null || echo "Database already initialized"

# Ingest all CSV files from deployment directory
echo ""
echo "=== Ingesting deployment ==="
echo "Directory: $DEPLOYMENT_DIR"
python ingest_ibutton_csv.py "$DB_PATH" "$DEPLOYMENT_DIR"

# Verify ingestion
echo ""
echo "=== Deployment summary ==="
python query_temperature.py "$DB_PATH" --list-deployments

echo ""
echo "=== Sensors in this deployment ==="
# Replace 'Adak_2025Dec' with your actual deployment name from metadata
python query_temperature.py "$DB_PATH" --list-deployment-sensors Adak_2025Dec

echo ""
echo "=== All sensors ==="
python query_temperature.py "$DB_PATH" --list-sensors

echo ""
echo "✅ Ingestion complete! Database: $DB_PATH"
