export default function Spinner({ size = 'md', className = '' }) {
  const sizes = {
    sm: 'h-4 w-4 border-2',
    md: 'h-6 w-6 border-2',
    lg: 'h-10 w-10 border-[3px]',
  };
  return (
    <span
      role="status"
      aria-label="Lädt…"
      className={`inline-block animate-spin rounded-full border-mint/30 border-t-mint ${sizes[size]} ${className}`}
    />
  );
}

export function PageSpinner() {
  return (
    <div className="flex justify-center py-16">
      <Spinner size="lg" />
    </div>
  );
}
