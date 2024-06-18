import MarkdownIt from "markdown-it";
import type Token from "markdown-it/lib/token.mjs";
import DOMPurify from "dompurify";

let markdownIt: MarkdownIt | null = null;

export function useMarkdownIt(): MarkdownIt {
  if (markdownIt === null) {
    markdownIt = new MarkdownIt("commonmark");
  }
  return markdownIt;
}

export function renderSanitize(c: string | Token[]): string {
  const md = useMarkdownIt();

  let r: string;
  if (typeof c === "string") {
    r = md.render(c);
  } else {
    r = md.renderer.render(c, md.options, {});
  }

  return DOMPurify.sanitize(r);
}
