import type { Metadata } from "next";

export const metadata: Metadata = { title: "Evaluations" };

const metrics = [
  ["hit@k", "Does the golden passage appear in the retrieved set?"],
  ["MRR", "How high does the first correct passage rank?"],
  ["citation precision", "Do the cited chunks actually support the sentence?"],
  ["faithfulness proxy", "Overlap between the answer and its sources."],
  ["refusal accuracy", "Unanswerable questions end in an explicit refusal."],
  ["leakage", "Cross-role probes return zero protected passages. Any leak fails the run."],
  ["p50 / p95 latency", "Wall-clock time per question, measured by the harness."],
];

export default function EvalsPage() {
  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-14">
      <span className="chip chip-accent mono">measurement</span>
      <h1 className="mt-4 text-3xl font-semibold tracking-tight">Evaluation harness</h1>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-[var(--text-muted)]">
        A golden set of questions runs against the live API: answerable questions across roles,
        unanswerable questions that must be refused, Bengali questions over English documents, and
        cross-role probes that must leak nothing.
      </p>

      <div className="panel mt-6 overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-[var(--panel-2)] text-[var(--text-muted)]">
            <tr>
              <th className="px-4 py-3 font-medium" scope="col">
                Metric
              </th>
              <th className="px-4 py-3 font-medium" scope="col">
                What it answers
              </th>
            </tr>
          </thead>
          <tbody>
            {metrics.map(([metric, description]) => (
              <tr className="border-t border-[var(--border)]" key={metric}>
                <td className="mono px-4 py-3 text-xs">{metric}</td>
                <td className="px-4 py-3 text-[13px] text-[var(--text-muted)]">{description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel-2 mt-6 p-5">
        <h2 className="text-sm font-semibold">Current status</h2>
        <p className="mt-2 text-[13px] leading-7 text-[var(--text-muted)]">
          The harness and the golden set are committed (<span className="mono">eval/run_eval.py</span>
          , <span className="mono">eval/golden_set.jsonl</span>). A published report is not shown
          here yet: the free API instance cannot hold the retrieval models and the answer path at the
          same time, so a full run would measure an outage rather than quality. The page will print
          the report from <span className="mono">docs/reports/eval.json</span> once the run completes.
        </p>
        <p className="mt-2 text-[13px] leading-7 text-[var(--text-muted)]">
          Refusals are counted as correct when the golden set marks a question as unanswerable, so a
          blunt &ldquo;I don&rsquo;t know&rdquo; does not inflate the score.
        </p>
      </div>
    </div>
  );
}
