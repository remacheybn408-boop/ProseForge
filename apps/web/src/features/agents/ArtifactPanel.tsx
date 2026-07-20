import type { AgentArtifact } from "../../lib/api/client";
import { agentArtifactSeal } from "./agentQueries";

function provenanceRole(provenance: Record<string, unknown>) {
  const role = provenance.role ?? provenance.reviewer_role ?? provenance.task_id;
  return typeof role === "string" ? role : "";
}

// Artifacts are listed with an ink line-glyph type seal, the sha256 prefix, the
// redacted preview, and the provenance role. An artifact whose payload failed
// schema validation (recorded in provenance.schema_error) shows an error
// placeholder instead of the preview; a failed fetch shows one for the whole panel.
export function ArtifactPanel({ artifacts, error = false }: { artifacts: AgentArtifact[]; error?: boolean }) {
  return <section aria-label="Artifacts" className="artifact-panel" style={{ display: "grid", gap: 8 }}>
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <strong style={{ fontFamily: "var(--font-seal)", fontWeight: 500 }}>Artifacts</strong>
      <span style={{ color: "var(--ink-mid)", font: "11px var(--font-mono)" }}>{artifacts.length} sealed</span>
    </header>
    {error && <p role="alert" className="artifact-error" style={{ margin: 0 }}>Artifact ledger unavailable — the schema could not be read.</p>}
    {artifacts.map(artifact => {
      const schemaError = typeof artifact.provenance.schema_error === "string" ? artifact.provenance.schema_error : undefined;
      const role = provenanceRole(artifact.provenance);
      return <article key={artifact.id} className="artifact-item">
        <span className="artifact-type-seal" aria-label={"Artifact type: " + artifact.artifact_type} title={artifact.artifact_type}>{agentArtifactSeal(artifact.artifact_type)}</span>
        <div className="artifact-item-body">
          <strong>{artifact.artifact_type}</strong>
          <code>{artifact.sha256.slice(0, 12)}</code>
          {schemaError
            ? <p role="alert" className="artifact-schema-error">Schema error — preview withheld: {schemaError}</p>
            : <p>{artifact.preview || "(no preview)"}</p>}
          {role && <small>provenance: {role}</small>}
        </div>
      </article>;
    })}
    {!error && !artifacts.length && <p className="agent-empty">No artifacts committed yet.</p>}
  </section>;
}
