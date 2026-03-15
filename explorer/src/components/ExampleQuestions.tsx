interface ExampleQuestionsProps {
  onSelect: (query: string) => void;
  disabled?: boolean;
}

const EXAMPLES = [
  "Einwohner von Berlin",
  "Frankfurt und München vergleichen",
  "Welche Flüsse fließen durch Deutschland?",
];

export function ExampleQuestions({ onSelect, disabled }: ExampleQuestionsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <span className="text-xs text-slate-500 self-center">Beispielfragen:</span>
      {EXAMPLES.map((q) => (
        <button
          key={q}
          type="button"
          onClick={() => onSelect(q)}
          disabled={disabled}
          className="rounded border border-slate-600 bg-slate-800/60 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-700 hover:text-slate-100 hover:border-slate-500 disabled:opacity-40 transition-colors"
        >
          {q}
        </button>
      ))}
    </div>
  );
}
