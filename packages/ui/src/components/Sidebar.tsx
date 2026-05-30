import type { ReactNode } from "react";

import { cn } from "../lib/utils";

export interface SidebarProps {
  title?: string;
  children: ReactNode;
  className?: string;
}

export function Sidebar({ title, children, className }: SidebarProps) {
  return (
    <aside
      className={cn(
        "flex flex-col border-r border-border bg-muted/30",
        className,
      )}
    >
      {title ? (
        <div className="border-b border-border px-3 py-2 text-sm font-medium text-foreground">
          {title}
        </div>
      ) : null}
      <div className="flex-1 overflow-auto">{children}</div>
    </aside>
  );
}
