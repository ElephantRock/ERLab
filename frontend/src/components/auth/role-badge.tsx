/** Role badge component — displays user role as a colored badge (BATCH-28). */

import { cn } from "@/lib/utils";

interface RoleBadgeProps {
  role: "admin" | "user";
  className?: string;
}

const ROLE_STYLES: Record<string, string> = {
  admin: "bg-info/10 text-info border-info/30 dark:bg-info/20 dark:text-info/70 dark:border-info/40",
  user: "bg-info/10 text-info border-info/30 dark:bg-info/20 dark:text-info/70 dark:border-info/40",
};

export function RoleBadge({ role, className }: RoleBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        ROLE_STYLES[role] || ROLE_STYLES.user,
        className,
      )}
      data-testid={`role-badge-${role}`}
    >
      {role}
    </span>
  );
}
