import type { CitationItem } from "./researchModel";

function citationNumber(c: CitationItem, index: number): number {
  const m = c.id.match(/^C(\d+)$/i);
  return m ? Number(m[1]) : index + 1;
}

/** Highlight the `[^Cn]` marker in the report body (simple scrollIntoView). */
function flashCitationRef(n: number) {
  const el = document.querySelector<HTMLElement>(`[data-citation-ref="${n}"]`);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("flash");
  void el.offsetWidth;
  el.classList.add("flash");
  window.setTimeout(() => el.classList.remove("flash"), 1400);
}

type Props = {
  citations: CitationItem[];
};

/** Side rail listing the current task's citations (id/title/url/locator). */
export default function CitationRail({ citations }: Props) {
  if (!citations.length) {
    return (
      <div className="citation-rail">
        <p className="empty">暂无引用 — 研究产出证据后，这里会列出标题、链接与定位符。</p>
      </div>
    );
  }

  return (
    <div className="citation-rail" aria-label="引用">
      <ol className="citation-list">
        {citations.map((c, i) => {
          const n = citationNumber(c, i);
          const label = /^C\d+$/i.test(c.id) ? `[^${c.id}]` : `[^C${n}]`;
          return (
            <li key={`${c.id}-${i}`} className="citation-item">
              <button
                type="button"
                className="citation-jump"
                title="定位正文中的引用标记"
                onClick={() => flashCitationRef(n)}
              >
                {label}
              </button>
              <div className="citation-body">
                {c.title ? (
                  c.url ? (
                    <a className="citation-title" href={c.url} target="_blank" rel="noreferrer">
                      {c.title}
                    </a>
                  ) : (
                    <span className="citation-title">{c.title}</span>
                  )
                ) : null}
                {c.locator ? <span className="citation-locator">{c.locator}</span> : null}
                {c.quote ? <p className="citation-quote">{c.quote}</p> : null}
                {c.source ? <span className="muted citation-source">{c.source}</span> : null}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
