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

/** Colore per categoria. Uso: SOLO badge (bg=col+"22", border=col+"44", text=col) e fill dei grafici.
 *  Mai come sfondo pieno. */
export const CATEGORY_COLOR: Record<string, string> = {
  cibo: "#ff9f43",
  trasporti: "#54a0ff",
  casa: "#55efc4",
  salute: "#00cec9",
  svago: "#fd79a8",
  abbigliamento: "#b2bec3",
  lavoro: "#a29bfe",
  abbonamenti: "#74b9ff",
  formazione: "#fdcb6e",
  altro: "#636e72",
  // sinonimi legacy
  shopping: "#fdcb6e",
  intrattenimento: "#fd79a8",
};

export function getCategoryColor(category: string): string {
  return CATEGORY_COLOR[category] || CATEGORY_COLOR.altro;
}

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
