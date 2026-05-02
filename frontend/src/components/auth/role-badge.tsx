/** Role badge component — displays user role as a colored badge (BATCH-28). */

import { cn } from "@/lib/utils";

interface RoleBadgeProps {
  role: "admin" | "user";
  className?: string;
}

const ROLE_STYLES: Record<string, string> = {
  admin: "bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-900 dark:text-purple-200 dark:border-purple-700",
  user: "bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900 dark:text-blue-200 dark:border-blue-700",
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
