import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import { DiffLines } from "./SclDiffPreview";

const components: Components = {
  pre({ children, ...props }) {
    return (
      <pre className="md-pre" {...props}>
        {children}
      </pre>
    );
  },
  code({ className, children, ...props }) {
    const text = String(children).replace(/\n$/, "");
    const isBlock = Boolean(className) || text.includes("\n");
    if (isBlock) {
      const lang = (className || "").replace(/^language-/, "") || "scl";
      if (lang === "diff") {
        return <DiffLines text={text} />;
      }
      return (
        <code className={`md-code-block language-${lang}`} {...props}>
          {text}
        </code>
      );
    }
    return (
      <code className="md-code-inline" {...props}>
        {children}
      </code>
    );
  },
  p({ children }) {
    return <p className="md-p">{children}</p>;
  },
  ul({ children }) {
    return <ul className="md-ul">{children}</ul>;
  },
  ol({ children }) {
    return <ol className="md-ol">{children}</ol>;
  },
  li({ children }) {
    return <li className="md-li">{children}</li>;
  },
  strong({ children }) {
    return <strong className="md-strong">{children}</strong>;
  },
};

type Props = {
  content: string;
  className?: string;
};

/** Render assistant / PLC answers as Markdown (SCL fences, bold, lists). */
export default function MarkdownBody({ content, className }: Props) {
  return (
    <div className={className ? `markdown-body ${className}` : "markdown-body"}>
      <ReactMarkdown components={components}>{content}</ReactMarkdown>
    </div>
  );
}
