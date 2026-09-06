import { useEditorStore, type OutlineItem } from "@paperhelp/shared";
import { cn } from "@paperhelp/ui";

const LEVEL_PADDING: Record<OutlineItem["level"], string> = {
  1: "pl-2",
  2: "pl-5",
  3: "pl-8",
};

export function Outline() {
  const outline = useEditorStore((s) => s.outline);

  if (outline.length === 0) {
    return (
      <p className="px-3 py-4 text-sm text-muted-foreground">
        暂无标题，在正文中添加 H1–H3 后会显示在这里。
      </p>
    );
  }

  return (
    <nav aria-label="Document outline" className="py-2">
      <ul className="space-y-1">
        {outline.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              className={cn(
                "w-full truncate rounded-md px-2 py-1.5 text-left text-sm text-foreground hover:bg-accent hover:text-accent-foreground",
                LEVEL_PADDING[item.level],
              )}
            >
              {item.text}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
