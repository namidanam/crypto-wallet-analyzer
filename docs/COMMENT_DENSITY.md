# Comment Density

Comment density is a simple maintainability indicator: how much of your codebase is comments.

This repo computes an **approximate** comment density over the same filtered (source-only) file set used by other metrics.

## What is counted

The script counts:
- **Code SLOC**: non-blank, non-comment lines (same approach as the COCOMO SLOC counter)
- **Comment-only lines**:
  - Python: lines whose first non-whitespace is `#`
  - JS/TS: lines whose first non-whitespace is `//` or starts a block comment `/* ... */`

By default, Python docstrings are **not** treated as comments.

## Run

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --comment-density
```

Include Python docstrings as comment lines:

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --comment-density --comment-docstrings
```

Include tests in the analysis:

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --comment-density --include-tests
```

