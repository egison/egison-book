#!/usr/bin/env python3
"""Build the English and Japanese HTML editions from the LaTeX sources."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEX_ROOT = ROOT / "tex"
HTML_ROOT = ROOT / "html"

LANGUAGE = {
    "en": {
        "book_title": "Introduction to the Egison Programming Language",
        "short_title": "Egison Book",
        "author": "Egison Development Team",
        "home": "Contents",
        "previous": "Previous",
        "next": "Next",
        "source": "TeX source",
        "other": "日本語",
        "front": "Front Matter",
        "introduction": "Introduction",
        "appendix": "Appendices",
        "bibliography": "Bibliography",
        "index": "Index",
        "chapter": "Chapter",
        "skip": "Skip to content",
        "description": "An open online book about the Egison programming language, covering pattern-match-oriented programming, computer algebra, tensor computation, and differential geometry.",
        "edition": "Open online edition",
        "start_reading": "Start reading",
        "browse_contents": "Browse contents",
        "about": "About this book",
        "about_body": "Egison is a programming language designed to make pattern matching and mathematical notation first-class tools. This book introduces the language from its foundations and develops practical techniques for symbolic and tensor computation.",
        "learn": "What you will learn",
        "complete_book": "Complete book",
        "topics": (
            ("Pattern matching", "Describe patterns directly, even for sets, multisets, graphs, and other non-free data types."),
            ("Computer algebra", "Work with symbolic expressions, simplification rules, and extensible mathematical functions."),
            ("Tensor notation", "Express tensor calculations and differential geometry with index notation."),
        ),
    },
    "ja": {
        "book_title": "プログラミング言語Egison入門",
        "short_title": "Egison Book",
        "author": "Egison開発チーム",
        "home": "目次",
        "previous": "前へ",
        "next": "次へ",
        "source": "TeX原稿",
        "other": "English",
        "front": "前付け",
        "introduction": "序論",
        "appendix": "付録",
        "bibliography": "参考文献",
        "index": "索引",
        "chapter": "第",
        "skip": "本文へ移動",
        "description": "パターンマッチ指向プログラミング、数式処理、テンソル計算、微分幾何を解説する、プログラミング言語Egisonのオンライン入門書です。",
        "edition": "オンライン公開版",
        "start_reading": "読み始める",
        "browse_contents": "目次を見る",
        "about": "本書について",
        "about_body": "Egisonは、パターンマッチと数学的な記法を第一級の道具として扱うために設計されたプログラミング言語です。本書では言語の基礎から始め、記号計算やテンソル計算の実践的な手法までを解説します。",
        "learn": "本書で学べること",
        "complete_book": "全目次",
        "topics": (
            ("パターンマッチ", "集合・多重集合・グラフなどの非自由データ型に対するパターンを直接記述します。"),
            ("数式処理", "数式データ、簡約規則、拡張可能な数学関数の仕組みを学びます。"),
            ("テンソル記法", "添字記法によるテンソル計算と微分幾何のプログラムを解説します。"),
        ),
    },
}

MATHJAX_CONFIG = r"""
<script>
window.MathJax = {
  tex: {
    inlineMath: [['\\(', '\\)']],
    displayMath: [['\\[', '\\]']],
    macros: {
      bt: ['\\mathtt{#1}', 1],
      set: ['\\{#1\\}', 1],
      abs: ['\\lvert #1\\rvert', 1],
      cons: ':', none: '\\mathtt{none}', some: '\\mathtt{some}',
      opt: '\\mathtt{opt}', FV: '\\mathrm{FV}', FTV: '\\mathrm{FTV}'
    }
  },
  options: {skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']}
};
</script>
<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
""".strip()


@dataclass
class Page:
    source: str
    filename: str
    title: str = ""
    number: str = ""
    group: str = ""
    appendix: bool = False
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class Label:
    page: str
    anchor: str
    display: str


def strip_comments(source: str) -> str:
    """Remove TeX comments while preserving verbatim listing contents."""
    output: list[str] = []
    in_listing = False
    for line in source.splitlines():
        if r"\begin{lstlisting}" in line:
            in_listing = True
        if in_listing:
            output.append(line)
        else:
            cut = len(line)
            for index, char in enumerate(line):
                if char == "%" and (index == 0 or line[index - 1] != "\\"):
                    cut = index
                    break
            output.append(line[:cut].rstrip())
        if r"\end{lstlisting}" in line:
            in_listing = False
    return "\n".join(output)


def braced(source: str, start: int) -> tuple[str, int]:
    """Return the contents and end position of a balanced braced argument."""
    if start >= len(source) or source[start] != "{":
        return "", start
    depth = 0
    index = start
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1 : index], index + 1
        index += 1
    return source[start + 1 :], len(source)


def optional(source: str, start: int) -> tuple[str, int]:
    if start >= len(source) or source[start] != "[":
        return "", start
    end = source.find("]", start + 1)
    if end < 0:
        return source[start + 1 :], len(source)
    return source[start + 1 : end], end + 1


def command_argument(source: str, start: int) -> tuple[str, int]:
    while start < len(source) and source[start].isspace():
        start += 1
    if start < len(source) and source[start] == "{":
        return braced(source, start)
    return "", start


def plain_tex(source: str) -> str:
    """Extract plain text from a small TeX fragment for titles and metadata."""
    source = re.sub(r"\\(?:label|index)\{.*?\}", "", source)
    source = re.sub(r"\\(?:lstinline|texttt|emph|textbf|textit)\{([^{}]*)\}", r"\1", source)
    source = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", "", source)
    source = source.replace("{", "").replace("}", "").replace("~", " ")
    return html.unescape(source).strip()


class BookBuilder:
    def __init__(self, lang: str):
        self.lang = lang
        self.words = LANGUAGE[lang]
        self.tex_dir = TEX_ROOT / lang
        self.out_dir = HTML_ROOT / lang
        self.pages: list[Page] = []
        self.labels: dict[str, Label] = {}
        self.citations: dict[str, int] = {}
        self.index_terms: dict[str, set[str]] = {}
        self._tokens: dict[str, str] = {}
        self._token_count = 0

    def token(self, value: str) -> str:
        key = f"@@EGISONHTML{self._token_count:06d}@@"
        self._token_count += 1
        self._tokens[key] = value
        return key

    def restore_tokens(self, source: str) -> str:
        # Table tokens may contain inline-code tokens created earlier.
        for key, value in reversed(tuple(self._tokens.items())):
            source = source.replace(key, value)
        return source

    def discover_pages(self) -> None:
        main = strip_comments((self.tex_dir / "main.tex").read_text(encoding="utf-8"))
        body = main.split(r"\begin{document}", 1)[-1]
        group = self.words["front"]
        appendix = False
        chapter_number = 0
        appendix_number = 0
        pattern = re.compile(r"\\(part|include|appendix)(?:\{([^{}]*)\})?")
        for match in pattern.finditer(body):
            command, value = match.group(1), match.group(2)
            if command == "part":
                group = plain_tex(value or "")
            elif command == "appendix":
                appendix = True
                group = self.words["appendix"]
            elif command == "include" and value:
                if value == "intro" and group == self.words["front"]:
                    group = self.words["introduction"]
                path = self.tex_dir / f"{value}.tex"
                if not path.exists():
                    continue
                source = strip_comments(path.read_text(encoding="utf-8"))
                heading = re.search(r"\\chapter(\*)?\{", source)
                title = value
                starred = False
                if heading:
                    title_arg, _ = braced(source, heading.end() - 1)
                    title = plain_tex(title_arg)
                    starred = bool(heading.group(1))
                number = ""
                if not starred:
                    if appendix:
                        appendix_number += 1
                        number = chr(ord("A") + appendix_number - 1)
                    else:
                        chapter_number += 1
                        number = str(chapter_number)
                self.pages.append(Page(value, f"{value}.html", title, number, group, appendix))

    def scan_labels(self) -> None:
        for page in self.pages:
            source = strip_comments((self.tex_dir / f"{page.source}.tex").read_text(encoding="utf-8"))
            section = 0
            subsection = 0
            current_display = page.number or page.title
            heading_pattern = re.compile(r"\\(chapter|section|subsection|subsubsection)(\*)?\{")
            events: list[tuple[int, str, str]] = []
            for match in heading_pattern.finditer(source):
                title, end = braced(source, match.end() - 1)
                events.append((match.start(), "heading", f"{match.group(1)}\t{match.group(2) or ''}\t{title}"))
            for match in re.finditer(r"\\label\{([^{}]+)\}", source):
                events.append((match.start(), "label", match.group(1)))
            for _, kind, value in sorted(events):
                if kind == "heading":
                    level, starred, title = value.split("\t", 2)
                    if not starred:
                        if level == "chapter":
                            current_display = page.number
                        elif level == "section":
                            section += 1
                            subsection = 0
                            current_display = f"{page.number}.{section}" if page.number else str(section)
                        elif level == "subsection":
                            subsection += 1
                            current_display = f"{page.number}.{section}.{subsection}" if page.number else f"{section}.{subsection}"
                    continue
                anchor = self.anchor(value)
                display = current_display or "↗"
                self.labels[value] = Label(page.filename, anchor, display)
                page.labels[value] = anchor

        main = strip_comments((self.tex_dir / "main.tex").read_text(encoding="utf-8"))
        part_number = 0
        for match in re.finditer(r"\\part\{([^{}]+)\}\\label\{([^{}]+)\}", main):
            part_number += 1
            title, label = match.groups()
            target = next((page for page in self.pages if page.group == plain_tex(title)), self.pages[0])
            anchor = self.anchor(label)
            self.labels[label] = Label(target.filename, anchor, self.roman(part_number))
            target.labels[label] = anchor

    @staticmethod
    def roman(number: int) -> str:
        values = ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
        result = ""
        for value, numeral in values:
            while number >= value:
                result += numeral
                number -= value
        return result

    @staticmethod
    def anchor(label: str) -> str:
        return "ref-" + re.sub(r"[^a-zA-Z0-9_-]+", "-", label).strip("-")

    def protect_listings(self, source: str) -> str:
        pattern = re.compile(r"\\begin\{lstlisting\}(?:\[([^]]*)\])?\s*\n?(.*?)\\end\{lstlisting\}", re.S)

        def replacement(match: re.Match[str]) -> str:
            options = match.group(1) or ""
            code = "\n".join(line.rstrip() for line in match.group(2).rstrip("\n").splitlines())
            language = "haskell" if "haskell" in options.lower() else "egison"
            value = f'<pre class="listing"><code class="language-{language}">{html.escape(code)}</code></pre>'
            return "\n\n" + self.token(value) + "\n\n"

        return pattern.sub(replacement, source)

    def protect_inline_code(self, source: str) -> str:
        """Protect lstinline and verb before dollar-delimited math is scanned."""
        output: list[str] = []
        index = 0
        pattern = re.compile(r"\\(lstinline|verb)\*?")
        while index < len(source):
            match = pattern.search(source, index)
            if not match:
                output.append(source[index:])
                break
            output.append(source[index : match.start()])
            cursor = match.end()
            options, cursor = optional(source, cursor)
            if cursor >= len(source):
                output.append(source[match.start() :])
                break
            delimiter = source[cursor]
            if delimiter == "{":
                # In \lstinline{\}, the backslash is content and the next
                # brace is still the delimiter; normal TeX brace escaping does
                # not apply inside listings.
                end = source.find("}", cursor + 1)
                if end < 0:
                    output.append(source[match.start() :])
                    break
                value, cursor = source[cursor + 1 : end], end + 1
            else:
                end = source.find(delimiter, cursor + 1)
                if end < 0:
                    output.append(source[match.start() :])
                    break
                value, cursor = source[cursor + 1 : end], end + 1
            if "mathescape" in options:
                parts = re.split(r"(\$[^$]*\$)", value)
                rendered = []
                for part in parts:
                    if part.startswith("$") and part.endswith("$"):
                        rendered.append(f'<span class="math-inline">\\({html.escape(part[1:-1])}\\)</span>')
                    else:
                        rendered.append(html.escape(part))
                code = '<span class="inline-code">' + "".join(rendered) + "</span>"
            else:
                code = f"<code>{html.escape(value)}</code>"
            output.append(self.token(code))
            index = cursor
        return "".join(output)

    def protect_math(self, source: str) -> str:
        display_patterns = [
            re.compile(r"\\\[(.*?)\\\]", re.S),
            re.compile(r"\$\$(.*?)\$\$", re.S),
            re.compile(r"\\begin\{(alignat\*?|align\*?|equation\*?|gather\*?)\}(.*?)\\end\{\1\}", re.S),
        ]
        for pattern in display_patterns:
            def display(match: re.Match[str]) -> str:
                content = match.group(2) if match.lastindex and match.lastindex > 1 else match.group(1)
                value = f'<div class="math-display">\\[{html.escape(content.strip())}\\]</div>'
                return "\n\n" + self.token(value) + "\n\n"
            source = pattern.sub(display, source)

        output: list[str] = []
        index = 0
        while index < len(source):
            if source[index] == "$" and (index == 0 or source[index - 1] != "\\"):
                end = index + 1
                while end < len(source):
                    if source[end] == "$" and source[end - 1] != "\\":
                        break
                    end += 1
                if end < len(source):
                    content = source[index + 1 : end]
                    output.append(self.token(f'<span class="math-inline">\\({html.escape(content)}\\)</span>'))
                    index = end + 1
                    continue
            output.append(source[index])
            index += 1
        return "".join(output)

    def inline(self, source: str, page: Page) -> str:
        output: list[str] = []
        index = 0
        simple_wrappers = {
            "textbf": ("<strong>", "</strong>"),
            "bf": ("<strong>", "</strong>"),
            "emph": ("<em>", "</em>"),
            "textit": ("<em>", "</em>"),
            "texttt": ("<code>", "</code>"),
            "bt": ("<code>", "</code>"),
            "small": ('<span class="small">', "</span>"),
        }
        skip_with_arg = {"hspace", "vspace", "addcontentsline", "setcounter", "addtolength"}
        skip_commands = {
            "centering", "noindent", "medskip", "bigskip", "smallskip", "clearpage", "newpage",
            "frontmatter", "mainmatter", "backmatter", "appendix", "tableofcontents", "printindex",
            "bibliographystyle", "bibliography", "maketitle", "normalfont", "footnotesize",
        }
        symbols = {
            "%": "%", "&": "&amp;", "_": "_", "#": "#", "$": "$", "{": "{", "}": "}",
            "LaTeX": "LaTeX", "TeX": "TeX", "ldots": "…", "dots": "…", "copyright": "©",
            "textlangle": "⟨", "textrangle": "⟩",
        }
        while index < len(source):
            if source.startswith("@@EGISONHTML", index):
                end = source.find("@@", index + 2)
                if end >= 0:
                    key = source[index : end + 2]
                    output.append(key)
                    index = end + 2
                    continue
            char = source[index]
            if char == "{":
                value, end = braced(source, index)
                output.append(self.inline(value, page))
                index = end
                continue
            if char != "\\":
                if source.startswith("---", index):
                    output.append("—")
                    index += 3
                elif source.startswith("``", index):
                    output.append("“")
                    index += 2
                elif source.startswith("''", index):
                    output.append("”")
                    index += 2
                elif char == "~":
                    output.append("&nbsp;")
                    index += 1
                else:
                    output.append(html.escape(char))
                    index += 1
                continue

            if index + 1 < len(source) and source[index + 1] == "\\":
                output.append("<br>")
                index += 2
                continue
            command_match = re.match(r"\\([A-Za-z@]+\*?|.)", source[index:])
            if not command_match:
                output.append("\\")
                index += 1
                continue
            command = command_match.group(1)
            bare = command.rstrip("*")
            cursor = index + len(command_match.group(0))
            if command in symbols:
                output.append(symbols[command])
                index = cursor
                continue
            if command in {'"', "'", "`", "^", "~", "c"}:
                value, end = command_argument(source, cursor)
                if end == cursor and cursor < len(source):
                    value, end = source[cursor], cursor + 1
                if not value:
                    output.append(html.escape(command))
                    index = cursor
                    continue
                accent = {'"': "\u0308", "'": "\u0301", "`": "\u0300", "^": "\u0302", "~": "\u0303", "c": "\u0327"}[command]
                output.append(html.escape(unicodedata.normalize("NFC", value + accent)))
                index = end
                continue
            if bare in {"lstinline", "verb"}:
                _, cursor = optional(source, cursor)
                if cursor >= len(source):
                    index = cursor
                    continue
                delimiter = source[cursor]
                if delimiter == "{":
                    end = source.find("}", cursor + 1)
                    if end < 0:
                        end = len(source)
                    value, cursor = source[cursor + 1 : end], min(end + 1, len(source))
                else:
                    end = source.find(delimiter, cursor + 1)
                    if end < 0:
                        end = len(source)
                    value, cursor = source[cursor + 1 : end], min(end + 1, len(source))
                output.append(f"<code>{html.escape(value)}</code>")
                index = cursor
                continue
            if bare in simple_wrappers:
                value, cursor = command_argument(source, cursor)
                opening, closing = simple_wrappers[bare]
                output.append(opening + self.inline(value, page) + closing)
                index = cursor
                continue
            if bare in {"ref", "pageref", "eqref"}:
                value, cursor = command_argument(source, cursor)
                target = self.labels.get(value)
                if target:
                    href = f"{target.page}#{target.anchor}"
                    display = target.display
                    if bare == "eqref":
                        display = f"({display})"
                    output.append(f'<a class="reference" href="{html.escape(href)}">{html.escape(display)}</a>')
                else:
                    output.append('<span class="missing-reference">↗</span>')
                index = cursor
                continue
            if bare == "label":
                value, cursor = command_argument(source, cursor)
                output.append(f'<span id="{self.anchor(value)}" class="anchor"></span>')
                index = cursor
                continue
            if bare == "cite":
                value, cursor = command_argument(source, cursor)
                rendered = []
                for key in (item.strip() for item in value.split(",")):
                    number = self.citations.setdefault(key, len(self.citations) + 1)
                    rendered.append(f'<a href="bibliography.html#cite-{html.escape(key)}">{number}</a>')
                output.append("[" + ", ".join(rendered) + "]")
                index = cursor
                continue
            if bare == "index":
                value, cursor = command_argument(source, cursor)
                rendered = self.restore_tokens(value.split("@")[-1])
                term = plain_tex(re.sub(r"<[^>]+>", "", rendered)).strip()
                if term:
                    self.index_terms.setdefault(term, set()).add(page.filename)
                index = cursor
                continue
            if bare == "url":
                value, cursor = command_argument(source, cursor)
                escaped = html.escape(value)
                output.append(f'<a href="{escaped}">{escaped}</a>')
                index = cursor
                continue
            if bare == "href":
                url, cursor = command_argument(source, cursor)
                label, cursor = command_argument(source, cursor)
                output.append(f'<a href="{html.escape(url)}">{self.inline(label, page)}</a>')
                index = cursor
                continue
            if bare == "footnote":
                value, cursor = command_argument(source, cursor)
                output.append(f'<span class="footnote" role="note">{self.inline(value, page)}</span>')
                index = cursor
                continue
            if bare == "includegraphics":
                _, cursor = optional(source, cursor)
                value, cursor = command_argument(source, cursor)
                filename = Path(value).name
                output.append(f'<img src="assets/{html.escape(filename)}" alt="">')
                index = cursor
                continue
            if bare == "fcolorbox":
                _, cursor = command_argument(source, cursor)
                _, cursor = command_argument(source, cursor)
                value, cursor = command_argument(source, cursor)
                output.append(f'<span class="boxed">{self.inline(value, page)}</span>')
                index = cursor
                continue
            if bare in skip_with_arg:
                _, cursor = command_argument(source, cursor)
                if bare == "addcontentsline":
                    _, cursor = command_argument(source, cursor)
                    _, cursor = command_argument(source, cursor)
                index = cursor
                continue
            if bare in skip_commands:
                index = cursor
                continue
            value, end = command_argument(source, cursor)
            if end != cursor:
                output.append(self.inline(value, page))
                index = end
            else:
                index = cursor
        return "".join(output)

    def table(self, source: str, page: Page) -> str:
        source = re.sub(r"^\{[^\n]*\}\s*", "", source.strip())
        source = re.sub(r"\\(?:hline|toprule|midrule|bottomrule|hhline\{[^}]*\})", "", source)
        rows = re.split(r"(?<!\\)\\\\(?:\[[^]]*\])?", source)
        rendered_rows = []
        for row in rows:
            if not row.strip():
                continue
            cells = re.split(r"(?<!\\)&", row)
            rendered = "".join(f"<td>{self.inline(cell.strip(), page)}</td>" for cell in cells)
            rendered_rows.append(f"<tr>{rendered}</tr>")
        return '<div class="table-scroll"><table><tbody>' + "".join(rendered_rows) + "</tbody></table></div>"

    def convert_page(self, page: Page) -> str:
        self._tokens = {}
        self._token_count = 0
        source = strip_comments((self.tex_dir / f"{page.source}.tex").read_text(encoding="utf-8"))
        source = self.protect_listings(source)
        source = self.protect_inline_code(source)
        source = self.protect_math(source)

        table_pattern = re.compile(r"\\begin\{tabular\}(?:\{[^\n]*\})?(.*?)\\end\{tabular\}", re.S)
        source = table_pattern.sub(lambda match: "\n\n" + self.token(self.table(match.group(1), page)) + "\n\n", source)

        lines = source.splitlines()
        blocks: list[str] = []
        paragraph: list[str] = []
        list_stack: list[str] = []
        li_open = False
        section = 0
        subsection = 0

        def flush_paragraph() -> None:
            if paragraph:
                content = self.inline(" ".join(part.strip() for part in paragraph), page).strip()
                if content:
                    blocks.append(f"<p>{content}</p>")
                paragraph.clear()

        for line in lines:
            stripped = line.strip()
            if not stripped:
                flush_paragraph()
                continue
            token_only = re.fullmatch(r"@@EGISONHTML\d{6}@@", stripped)
            if token_only:
                flush_paragraph()
                blocks.append(stripped)
                continue
            heading_match = re.match(r"\\(chapter|section|subsection|subsubsection|paragraph)(\*)?\{", stripped)
            if heading_match:
                flush_paragraph()
                title, end = braced(stripped, heading_match.end() - 1)
                level, starred = heading_match.group(1), bool(heading_match.group(2))
                number = ""
                tag = {"chapter": "h1", "section": "h2", "subsection": "h3", "subsubsection": "h4", "paragraph": "h5"}[level]
                if not starred:
                    if level == "chapter":
                        number = page.number
                    elif level == "section":
                        section += 1
                        subsection = 0
                        number = f"{page.number}.{section}" if page.number else str(section)
                    elif level == "subsection":
                        subsection += 1
                        number = f"{page.number}.{section}.{subsection}" if page.number else f"{section}.{subsection}"
                prefix = f'<span class="heading-number">{html.escape(number)}</span>' if number else ""
                blocks.append(f"<{tag}>{prefix}{self.inline(title, page)}</{tag}>")
                remainder = stripped[end:].strip()
                if remainder:
                    paragraph.append(remainder)
                continue
            begin = re.match(r"\\begin\{([^}]+)\}(?:\[[^]]*\])?(?:\{[^}]*\})?", stripped)
            if begin:
                flush_paragraph()
                env = begin.group(1)
                tags = {
                    "framed": '<aside class="callout">', "oframed": '<aside class="callout">',
                    "figure": "<figure>", "figure*": "<figure>", "subfigure": '<div class="subfigure">',
                    "table": '<figure class="table-figure">', "center": '<div class="center">',
                    "flushright": '<div class="flushright">', "minipage": '<div class="minipage">',
                    "itemize": "<ul>", "enumerate": "<ol>",
                }
                if env in {"itemize", "enumerate"}:
                    list_stack.append(env)
                    li_open = False
                if env in tags:
                    blocks.append(tags[env])
                remainder = stripped[begin.end():].strip()
                if remainder:
                    paragraph.append(remainder)
                continue
            end_match = re.match(r"\\end\{([^}]+)\}", stripped)
            if end_match:
                flush_paragraph()
                env = end_match.group(1)
                tags = {
                    "framed": "</aside>", "oframed": "</aside>", "figure": "</figure>",
                    "figure*": "</figure>", "subfigure": "</div>", "table": "</figure>",
                    "center": "</div>", "flushright": "</div>", "minipage": "</div>",
                    "itemize": "</ul>", "enumerate": "</ol>",
                }
                if env in {"itemize", "enumerate"}:
                    if li_open:
                        blocks.append("</li>")
                    li_open = False
                    if list_stack:
                        list_stack.pop()
                if env in tags:
                    blocks.append(tags[env])
                remainder = stripped[end_match.end():].strip()
                if remainder:
                    paragraph.append(remainder)
                continue
            item = re.match(r"\\item(?:\[([^]]*)\])?\s*(.*)", stripped)
            if item:
                flush_paragraph()
                if li_open:
                    blocks.append("</li>")
                label, content = item.groups()
                label_html = f'<span class="item-label">{self.inline(label, page)}</span> ' if label else ""
                blocks.append(f"<li>{label_html}{self.inline(content, page)}")
                li_open = True
                continue
            caption = re.match(r"\\caption(?:\[[^]]*\])?\{", stripped)
            if caption:
                flush_paragraph()
                value, end = braced(stripped, caption.end() - 1)
                blocks.append(f"<figcaption>{self.inline(value, page)}</figcaption>")
                remainder = stripped[end:].strip()
                if remainder:
                    paragraph.append(remainder)
                continue
            if re.fullmatch(r"\\(?:hline|toprule|midrule|bottomrule|centering|medskip|bigskip|smallskip)", stripped):
                flush_paragraph()
                continue
            paragraph.append(stripped)
        flush_paragraph()
        if li_open:
            blocks.append("</li>")
        rendered = self.restore_tokens("\n".join(blocks))
        source_labels = set(re.findall(r"\\label\{([^{}]+)\}", source))
        synthetic = "".join(
            f'<span id="{anchor}" class="anchor"></span>'
            for label, anchor in page.labels.items()
            if label not in source_labels
        )
        return synthetic + rendered

    def shell(
        self,
        title: str,
        body: str,
        page: str,
        previous: Page | None = None,
        following: Page | None = None,
        *,
        include_math: bool = True,
        home: bool = False,
    ) -> str:
        other = "ja" if self.lang == "en" else "en"
        other_target = f"../{other}/{page}"
        contents_target = "#contents" if home else "index.html#contents"
        nav_links = [
            '<a class="site-brand" href="index.html">Egison Book</a>',
            f'<a href="{contents_target}">{self.words["home"]}</a>',
        ]
        if previous:
            nav_links.append(f'<a rel="prev" href="{previous.filename}">← {self.words["previous"]}</a>')
        if following:
            nav_links.append(f'<a rel="next" href="{following.filename}">{self.words["next"]} →</a>')
        nav_links.append(f'<a class="language" hreflang="{other}" href="{other_target}">{self.words["other"]}</a>')
        description = html.escape(self.words["description"], quote=True)
        page_title = f"{title} — {self.words['short_title']}"
        schema = ""
        if home:
            schema_data = {
                "@context": "https://schema.org",
                "@type": "Book",
                "name": self.words["book_title"],
                "description": self.words["description"],
                "author": {"@type": "Organization", "name": self.words["author"]},
                "inLanguage": self.lang,
            }
            schema = f'<script type="application/ld+json">{json.dumps(schema_data, ensure_ascii=False)}</script>'
        mathjax = MATHJAX_CONFIG if include_math else ""
        head_extras = "\n".join(extra for extra in (schema, mathjax) if extra)
        main_class = "book-page home-page" if home else "book-page"
        source_url = f"https://github.com/egison/egison-book/tree/master/tex/{self.lang}"
        return f"""<!doctype html>
<html lang="{self.lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="generator" content="egison-book/scripts/build_html.py">
  <meta name="description" content="{description}">
  <meta name="theme-color" content="#126b4b">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Egison Book">
  <meta property="og:title" content="{html.escape(page_title, quote=True)}">
  <meta property="og:description" content="{description}">
  <meta property="og:locale" content="{'en_US' if self.lang == 'en' else 'ja_JP'}">
  <meta name="twitter:card" content="summary">
  <link rel="alternate" hreflang="en" href="../en/{page}">
  <link rel="alternate" hreflang="ja" href="../ja/{page}">
  <link rel="alternate" hreflang="x-default" href="../index.html">
  <title>{html.escape(page_title)}</title>
  <link rel="stylesheet" href="../style.css">
{head_extras}
</head>
<body>
  <a class="skip-link" href="#main-content">{self.words['skip']}</a>
  <header class="site-header"><nav aria-label="{'Primary navigation' if self.lang == 'en' else 'メインナビゲーション'}">{''.join(nav_links)}</nav></header>
  <main id="main-content" class="{main_class}">
    {body}
  </main>
  <footer><a href="{source_url}">{self.words['source']}</a></footer>
</body>
</html>
"""

    def bibliography_html(self) -> str:
        bib = (self.tex_dir / "main.bib").read_text(encoding="utf-8")
        entries = re.split(r"(?=@[A-Za-z]+\s*\{)", bib)
        rendered: list[str] = []
        cited = sorted(self.citations.items(), key=lambda item: item[1])
        by_key: dict[str, str] = {}
        for entry in entries:
            key_match = re.match(r"@[A-Za-z]+\s*\{\s*([^,]+),", entry)
            if not key_match:
                continue
            key = key_match.group(1).strip()
            fields = dict((name.lower(), plain_tex(value.strip())) for name, value in re.findall(r"([A-Za-z]+)\s*=\s*[\{\"](.*?)[\}\"]\s*,?\s*(?=\n\s*[A-Za-z]+\s*=|\n?\})", entry, re.S))
            pieces = [fields.get("author", ""), fields.get("title", ""), fields.get("journal", fields.get("booktitle", "")), fields.get("year", "")]
            by_key[key] = ". ".join(piece for piece in pieces if piece)
        for key, number in cited:
            rendered.append(f'<li id="cite-{html.escape(key)}" value="{number}">{html.escape(by_key.get(key, key))}</li>')
        return f'<h1>{self.words["bibliography"]}</h1><ol class="bibliography">{"".join(rendered)}</ol>'

    def index_html(self) -> str:
        items = []
        titles = {page.filename: page.title for page in self.pages}
        for term in sorted(self.index_terms, key=str.casefold):
            links = ", ".join(f'<a href="{page}">{html.escape(titles.get(page, page))}</a>' for page in sorted(self.index_terms[term]))
            items.append(f'<dt>{html.escape(term)}</dt><dd>{links}</dd>')
        return f'<h1>{self.words["index"]}</h1><dl class="index-list">{"".join(items)}</dl>'

    def contents_html(self) -> str:
        groups: list[tuple[str, list[Page]]] = []
        for page in self.pages:
            if not groups or groups[-1][0] != page.group:
                groups.append((page.group, []))
            groups[-1][1].append(page)
        sections = []
        for group, pages in groups:
            links = []
            for page in pages:
                number = f'<span class="toc-number">{html.escape(page.number)}</span>' if page.number else '<span class="toc-number"></span>'
                links.append(f'<li><a href="{page.filename}">{number}<span>{html.escape(page.title)}</span></a></li>')
            sections.append(f'<section class="toc-part"><h2>{html.escape(group)}</h2><ol>{"".join(links)}</ol></section>')
        extras = f'<section class="toc-part toc-extras"><ol><li><a href="bibliography.html"><span class="toc-number"></span><span>{self.words["bibliography"]}</span></a></li><li><a href="index-terms.html"><span class="toc-number"></span><span>{self.words["index"]}</span></a></li></ol></section>'
        topics = "".join(
            f'<li><span class="topic-number">{number:02d}</span><div><h3>{html.escape(title)}</h3><p>{html.escape(description)}</p></div></li>'
            for number, (title, description) in enumerate(self.words["topics"], 1)
        )
        return f"""<section class="home-hero" aria-labelledby="book-title">
  <p class="eyebrow">{html.escape(self.words['edition'])}</p>
  <h1 id="book-title">{html.escape(self.words['book_title'])}</h1>
  <p class="hero-summary">{html.escape(self.words['description'])}</p>
  <p class="author">{html.escape(self.words['author'])}</p>
  <div class="hero-actions">
    <a class="button button-primary" href="preface.html">{html.escape(self.words['start_reading'])}</a>
    <a class="button button-secondary" href="#contents">{html.escape(self.words['browse_contents'])}</a>
  </div>
</section>
<section class="home-about" aria-labelledby="about-heading">
  <div class="about-copy">
    <p class="eyebrow">Egison Book</p>
    <h2 id="about-heading">{html.escape(self.words['about'])}</h2>
    <p>{html.escape(self.words['about_body'])}</p>
  </div>
  <div class="topic-panel">
    <p class="eyebrow">{html.escape(self.words['learn'])}</p>
    <ol class="topic-list">{topics}</ol>
  </div>
</section>
<section class="contents" id="contents" aria-labelledby="contents-heading">
  <p class="eyebrow">{html.escape(self.words['complete_book'])}</p>
  <h2 id="contents-heading">{self.words['home']}</h2>
  <div class="toc-grid">{''.join(sections)}{extras}</div>
</section>"""

    def build(self) -> None:
        self.discover_pages()
        self.scan_labels()
        self.out_dir.mkdir(parents=True, exist_ok=True)
        assets = self.out_dir / "assets"
        if assets.exists():
            shutil.rmtree(assets)
        assets.mkdir()
        for image in self.tex_dir.glob("*.png"):
            shutil.copy2(image, assets / image.name)

        converted: list[tuple[Page, str]] = []
        for page in self.pages:
            converted.append((page, self.convert_page(page)))
        for index, (page, body) in enumerate(converted):
            previous = self.pages[index - 1] if index else None
            following = self.pages[index + 1] if index + 1 < len(self.pages) else None
            output = self.shell(page.title, body, page.filename, previous, following)
            (self.out_dir / page.filename).write_text(output, encoding="utf-8")

        (self.out_dir / "index.html").write_text(
            self.shell(self.words["book_title"], self.contents_html(), "index.html", include_math=False, home=True),
            encoding="utf-8",
        )
        (self.out_dir / "bibliography.html").write_text(
            self.shell(self.words["bibliography"], self.bibliography_html(), "bibliography.html", include_math=False),
            encoding="utf-8",
        )
        (self.out_dir / "index-terms.html").write_text(
            self.shell(self.words["index"], self.index_html(), "index-terms.html", include_math=False),
            encoding="utf-8",
        )


def write_root_index() -> None:
    body = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Read the Egison Book online in English or Japanese.">
<meta name="theme-color" content="#126b4b">
<link rel="alternate" hreflang="en" href="en/"><link rel="alternate" hreflang="ja" href="ja/">
<title>Egison Book — English / 日本語</title><link rel="stylesheet" href="style.css"></head>
<body><main class="language-picker"><p class="eyebrow">Open online edition</p><h1>Egison Book</h1>
<p class="language-lead">Choose a language <span lang="ja">／ 言語を選択してください</span></p>
<div><a href="en/">English</a><a href="ja/" lang="ja">日本語</a></div></main></body></html>
"""
    (HTML_ROOT / "index.html").write_text(body, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("language", nargs="?", choices=("all", "en", "ja"), default="all")
    args = parser.parse_args()
    HTML_ROOT.mkdir(exist_ok=True)
    languages = ("en", "ja") if args.language == "all" else (args.language,)
    for lang in languages:
        BookBuilder(lang).build()
    write_root_index()


if __name__ == "__main__":
    main()
