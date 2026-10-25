export function partialExplanation(reason: string | null) {
  if (reason === 'timeout') return 'Stopped at the time limit; the answer may be incomplete.';
  if (reason === 'step_limit') return 'Stopped at the tool-step limit; the answer may be incomplete.';
  return 'The agent stopped before finishing; the answer may be incomplete. Review the trace and run details.';
}
export function toolName(name: string) {
  return name === 'search_documents' ? 'Search documents' : name === 'query_metadata' ? 'Query document metadata' : name;
}
