export type ProposalDiffHunk = {
  id: string;
  before: string;
  after: string;
  label?: string;
};

export function ProposalDiff({ hunks, selectedHunkIds, onSelectionChange }: {
  hunks: readonly ProposalDiffHunk[];
  selectedHunkIds: readonly string[];
  onSelectionChange: (hunkId: string, selected: boolean) => void;
}) {
  const selected = new Set(selectedHunkIds);
  return <section aria-label="Proposal diff">
    <h3>Suggested changes</h3>
    {hunks.length === 0 ? <p>No changes proposed.</p> : <ol>
      {hunks.map((hunk, index) => <li key={hunk.id}>
        <label>
          <input
            type="checkbox"
            checked={selected.has(hunk.id)}
            onChange={event => onSelectionChange(hunk.id, event.target.checked)}
          />
          {hunk.label ?? `Change ${index + 1}`}
        </label>
        <p aria-label={`Inline diff for ${hunk.label ?? `change ${index + 1}`}`}>
          <del>{hunk.before}</del>{" "}<ins>{hunk.after}</ins>
        </p>
      </li>)}
    </ol>}
  </section>;
}
