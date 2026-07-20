# Egison Book

A book introducing the Egison programming language, available in Japanese and English.

## Structure

- `tex/en/` — English LaTeX sources
- `tex/ja/` — Japanese LaTeX sources
- `html/en/` — generated English HTML edition
- `html/ja/` — generated Japanese HTML edition
- `scripts/build_html.py` — dependency-free HTML generator

## Building

Build both the HTML and PDF editions from the repository root:

```bash
make
```

Build only the HTML editions:

```bash
make html
```

The HTML generator requires Python 3. It creates chapter-separated static pages,
copies the figures, and generates the contents, bibliography, and index pages.
Edit files under `tex/`, then run `make html` to refresh the checked-in HTML.
Mathematical notation is rendered in the browser using MathJax.

Build only the PDF editions:

```bash
make tex
```

The TeX builds require `platex`, `pbibtex`, `makeindex`, and `dvipdfmx`.
Individual editions can also be built with `make -C tex/en` and
`make -C tex/ja`.
