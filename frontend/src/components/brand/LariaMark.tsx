import { cn } from "@/lib/utils";

type LariaMarkProps = {
  className?: string;
  size?: "sm" | "md" | "lg" | "hero";
  subtitle?: boolean;
};

const sizeMap = {
  sm: "text-xl",
  md: "text-3xl",
  lg: "text-5xl",
  hero: "text-6xl sm:text-7xl md:text-8xl",
};

export function LariaMark({ className, size = "md", subtitle = false }: LariaMarkProps) {
  return (
    <div className={cn("flex flex-col", className)}>
      <span
        className={cn(
          "font-display font-semibold text-ink tracking-tight",
          sizeMap[size],
        )}
      >
        LARIA
      </span>
      {subtitle ? (
        <span className="mt-1 text-sm text-muted-foreground sm:text-base">
          Tutor inteligente adaptativo
        </span>
      ) : null}
    </div>
  );
}
