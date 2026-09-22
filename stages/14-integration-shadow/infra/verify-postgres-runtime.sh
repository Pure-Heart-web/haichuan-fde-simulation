#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 -f /schema/postgresql-rls.sql
psql -v ON_ERROR_STOP=1 -f /stage14/postgres-session-rls.sql
echo "STAGE14_POSTGRES_SESSION_RLS_PASSED"
