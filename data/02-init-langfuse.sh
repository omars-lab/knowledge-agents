#!/bin/bash
# Create Langfuse database if it doesn't exist
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE langfuse OWNER knowledge' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec
EOSQL
