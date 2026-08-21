import {
  Pizza, Car, Home, Pill, Drama, Shirt, Briefcase,
  Smartphone, GraduationCap, HelpCircle, ShoppingBag,
  type LucideIcon,
} from "lucide-react";

/** Mappa categoria (chiave lowercase usata nel DB) → icona lucide-react.
 *  Sostituisce le emoji "standard Apple" con un set coerente monocromo. */
export const CATEGORY_ICONS: Record<string, LucideIcon> = {
  cibo: Pizza,
  trasporti: Car,
  casa: Home,
  salute: Pill,
  svago: Drama,
  abbigliamento: Shirt,
  lavoro: Briefcase,
  abbonamenti: Smartphone,
  formazione: GraduationCap,
  altro: HelpCircle,
  // sinonimi legacy eventualmente presenti nei dati storici
  intrattenimento: Drama,
  shopping: ShoppingBag,
};

export function getCategoryIcon(category: string): LucideIcon {
  return CATEGORY_ICONS[category] || HelpCircle;
}

interface CategoryIconProps {
  category: string;
  size?: number;
  className?: string;
}

/** Icona categoria pronta all'uso, al posto dell'emoji. */
export function CategoryIcon({ category, size = 18, className }: CategoryIconProps) {
  const Icon = getCategoryIcon(category);
  return <Icon size={size} className={className} aria-hidden="true" />;
}
