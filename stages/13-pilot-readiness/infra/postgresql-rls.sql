-- Stage 13 contract only. Apply through an approved migration tool in a real environment.
CREATE ROLE fde_runtime NOLOGIN NOCREATEDB NOCREATEROLE;

CREATE TABLE inbox (tenant_id text NOT NULL, event_id text NOT NULL, payload_json jsonb NOT NULL, PRIMARY KEY (tenant_id,event_id));
CREATE TABLE cases (tenant_id text NOT NULL, case_id text NOT NULL, artifact_json jsonb NOT NULL, PRIMARY KEY (tenant_id,case_id));
CREATE TABLE reviews (tenant_id text NOT NULL, review_id bigint GENERATED ALWAYS AS IDENTITY, case_id text NOT NULL, PRIMARY KEY (tenant_id,review_id));
CREATE TABLE outbox (tenant_id text NOT NULL, message_id text NOT NULL, payload_json jsonb NOT NULL, PRIMARY KEY (tenant_id,message_id));
CREATE TABLE audit (tenant_id text NOT NULL, audit_id bigint GENERATED ALWAYS AS IDENTITY, action text NOT NULL, PRIMARY KEY (tenant_id,audit_id));
CREATE TABLE incidents (tenant_id text NOT NULL, incident_id text NOT NULL, detail text NOT NULL, PRIMARY KEY (tenant_id,incident_id));

ALTER TABLE inbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE inbox FORCE ROW LEVEL SECURITY;
CREATE POLICY inbox_tenant_scope ON inbox USING (tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases FORCE ROW LEVEL SECURITY;
CREATE POLICY cases_tenant_scope ON cases USING (tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews FORCE ROW LEVEL SECURITY;
CREATE POLICY reviews_tenant_scope ON reviews USING (tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
ALTER TABLE outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox FORCE ROW LEVEL SECURITY;
CREATE POLICY outbox_tenant_scope ON outbox USING (tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
ALTER TABLE audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_tenant_scope ON audit USING (tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents FORCE ROW LEVEL SECURITY;
CREATE POLICY incidents_tenant_scope ON incidents USING (tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

GRANT SELECT, INSERT, UPDATE ON inbox, cases, reviews, outbox, audit, incidents TO fde_runtime;
