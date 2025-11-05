#!/bin/bash

set -euo pipefail

# If the driver is already registered, nothing to do.
if command -v odbcinst >/dev/null 2>&1; then
    if odbcinst -q -d 2>/dev/null | grep -qi "ODBC Driver 18 for SQL Server"; then
        exit 0
    fi
fi

export DEBIAN_FRONTEND=noninteractive

# Ensure foundational packages are present (idempotent if they already are).
apt-get update
apt-get install -y curl gnupg apt-transport-https unixodbc unixodbc-dev

# Add Microsoft's package repository for the SQL Server ODBC driver.
if [ ! -f /etc/apt/sources.list.d/msprod.list ]; then
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
    curl https://packages.microsoft.com/config/debian/12/prod.list \
        > /etc/apt/sources.list.d/msprod.list
fi

apt-get update
ACCEPT_EULA=Y apt-get install -y msodbcsql18

# Verify installation succeeded.
if ! (odbcinst -q -d 2>/dev/null | grep -qi "ODBC Driver 18 for SQL Server"); then
    echo "Failed to install Microsoft ODBC Driver 18 for SQL Server" >&2
    exit 1
fi

exit 0
