'use client';

interface AgentOption {
  value: string;
  label: string;
}

interface AgentSelectorProps {
  value: string;
  onChange: (value: string) => void;
  options?: AgentOption[];
}

const DEFAULT_AGENTS: AgentOption[] = [
  { value: 'assistant', label: 'Assistant' },
  { value: 'customer-support', label: 'Customer Support' },
  { value: 'sales', label: 'Sales' },
];

export function AgentSelector({ value, onChange, options = DEFAULT_AGENTS }: AgentSelectorProps) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-foreground mb-1 text-sm font-semibold">Agent</legend>
      <div className="flex flex-wrap gap-3">
        {options.map((option) => (
          <label key={option.value} className="flex cursor-pointer items-center gap-2">
            <input
              type="radio"
              name="agent_name"
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
              className="accent-primary"
            />
            <span className="text-sm">{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
