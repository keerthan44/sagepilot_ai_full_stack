'use client';

export interface AgentOption {
  value: string;
  label: string;
  /** Shown under the radio for this agent */
  description?: string;
}

interface AgentSelectorProps {
  value: string;
  onChange: (value: string) => void;
  options?: AgentOption[];
}

const DEFAULT_AGENTS: AgentOption[] = [
  { value: 'general_assistant', label: 'General Assistant' },
  { value: 'customer_support', label: 'Customer Support' },
];

export function AgentSelector({ value, onChange, options = DEFAULT_AGENTS }: AgentSelectorProps) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-foreground mb-1 text-sm font-semibold">Agent</legend>
      <div className="flex flex-col gap-4">
        {options.map((option) => (
          <label
            key={option.value}
            className="border-border hover:bg-accent/30 has-[:checked]:border-primary has-[:checked]:bg-accent/20 flex cursor-pointer flex-col gap-1.5 rounded-lg border p-3 transition-colors"
          >
            <div className="flex items-center gap-2">
              <input
                type="radio"
                name="agent_name"
                value={option.value}
                checked={value === option.value}
                onChange={() => onChange(option.value)}
                className="accent-primary shrink-0"
              />
              <span className="text-sm font-medium">{option.label}</span>
            </div>
            {option.description ? (
              <p className="text-muted-foreground pl-6 text-xs leading-relaxed">
                {option.description}
              </p>
            ) : null}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
