#!/bin/sh
set -eu

allowed="$(psql -At -v ON_ERROR_STOP=1 <<'SQL'
SET ROLE fde_runtime;
SET app.tenant_id = 'tenant-a';
INSERT INTO inbox (tenant_id,event_id,payload_json)
VALUES ('tenant-a','RLS-ALLOW-1','{}') ON CONFLICT DO NOTHING;
SELECT count(*) FROM inbox WHERE event_id = 'RLS-ALLOW-1';
SQL
)"
test "$(printf '%s\n' "$allowed" | tail -n 1)" = "1"

visible="$(psql -At -v ON_ERROR_STOP=1 <<'SQL'
SET ROLE fde_runtime;
SET app.tenant_id = 'tenant-b';
SELECT count(*) FROM inbox WHERE event_id = 'RLS-ALLOW-1';
SQL
)"
test "$(printf '%s\n' "$visible" | tail -n 1)" = "0"

if psql -v ON_ERROR_STOP=1 <<'SQL'
SET ROLE fde_runtime;
SET app.tenant_id = 'tenant-a';
INSERT INTO inbox (tenant_id,event_id,payload_json) VALUES ('tenant-b','RLS-DENY-1','{}');
SQL
then
  echo "cross-tenant insert unexpectedly succeeded" >&2
  exit 1
fi

echo "POSTGRES_RLS_RUNTIME_CHECK_PASSED"
