interface BrandMarkProps {
  /** Lato del quadrato contenitore in px */
  size?: number;
}

/** Marchio FinCopilot: portafoglio a tratto sottile in quadrato con bordo 1px. */
export default function BrandMark({ size = 28 }: BrandMarkProps) {
  const icon = Math.round(size * 0.6);
  return (
    <span className="brand-mark" style={{ width: size, height: size }} aria-hidden="true">
      <svg
        width={icon}
        height={icon}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1" />
        <path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4" />
      </svg>
    </span>
  );
}
