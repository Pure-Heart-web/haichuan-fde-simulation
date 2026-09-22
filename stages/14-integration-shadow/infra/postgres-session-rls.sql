-- Run after the Stage 13 RLS schema. This checks that SET LOCAL tenant state
-- does not survive a transaction boundary, which models pooled connections.
SET ROLE fde_runtime;

BEGIN;
SET LOCAL app.tenant_id = 'tenant-a';
INSERT INTO inbox (tenant_id,event_id,payload_json)
VALUES ('tenant-a','POOL-RLS-A','{}') ON CONFLICT DO NOTHING;
SELECT count(*) AS tenant_a_visible FROM inbox WHERE event_id='POOL-RLS-A';
COMMIT;

BEGIN;
SET LOCAL app.tenant_id = 'tenant-b';
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM inbox WHERE event_id='POOL-RLS-A') THEN
    RAISE EXCEPTION 'pooled session leaked tenant-a rows to tenant-b';
  END IF;
END $$;
COMMIT;

RESET ROLE;
