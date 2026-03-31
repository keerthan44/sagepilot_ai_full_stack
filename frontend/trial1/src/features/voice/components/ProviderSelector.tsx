'use client';

interface ProviderOption {
  value: string;
  label: string;
}

interface ProviderSelectorProps {
  label: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  options: ProviderOption[];
  disabled?: boolean;
}

export function ProviderSelector({
  label,
  name,
  value,
  onChange,
  options,
  disabled = false,
}: ProviderSelectorProps) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-foreground mb-1 text-sm font-semibold">{label}</legend>
      <div className="flex flex-wrap gap-3">
        {options.map((option) => (
          <label key={option.value} className="flex cursor-pointer items-center gap-2">
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
              className="accent-primary"
              disabled={disabled}
            />
            <span className="text-sm">{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
