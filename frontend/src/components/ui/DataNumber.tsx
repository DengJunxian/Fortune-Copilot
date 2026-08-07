interface DataNumberProps {
  value: string;
  label: string;
}

export function DataNumber({ value, label }: DataNumberProps) {
  return (
    <span className="data-number" aria-label={label}>
      {value}
    </span>
  );
}

