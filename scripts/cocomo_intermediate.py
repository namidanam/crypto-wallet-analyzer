#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import csv
import keyword
import math
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


DEFAULT_INCLUDE_EXTS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".mjs",
    ".cjs",
}

DEFAULT_EXCLUDE_DIR_PARTS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".next",
    ".nuxt",
    ".cache",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "env",
    "docs",
}

DEFAULT_EXCLUDE_PATHS = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}


def _run_git_ls_files(root: Path) -> list[Path]:
    try:
        completed = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Failed to list files via `git ls-files`. Run inside a git repo.") from exc

    files: list[Path] = []
    for raw in completed.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        files.append((root / raw).resolve())
    return files


def _path_has_excluded_dir(path: Path, excluded_dir_parts: set[str]) -> bool:
    for part in path.parts:
        if part in excluded_dir_parts:
            return True
    return False


def _is_test_path(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if "tests" in parts or "__tests__" in parts:
        return True
    name = path.name.lower()
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith(".test.js") or name.endswith(".spec.js"):
        return True
    if name.endswith(".test.ts") or name.endswith(".spec.ts"):
        return True
    return False


def _iter_candidate_files(
    *,
    root: Path,
    include_exts: set[str],
    excluded_dir_parts: set[str],
    excluded_paths: set[str],
    include_tests: bool,
) -> list[Path]:
    candidates: list[Path] = []
    for path in _run_git_ls_files(root):
        rel = path.relative_to(root)
        if rel.as_posix() in excluded_paths or path.name in excluded_paths:
            continue
        if _path_has_excluded_dir(rel, excluded_dir_parts):
            continue
        if not include_tests and _is_test_path(rel):
            continue
        if path.suffix.lower() not in include_exts:
            continue
        if path.name.endswith(".min.js"):
            continue
        candidates.append(path)
    return candidates


def _read_text_lines(path: Path) -> list[str]:
    try:
        data = path.read_bytes()
    except OSError:
        return []

    if b"\x00" in data:
        return []

    return data.decode("utf-8", errors="replace").splitlines()


def _count_sloc_python(lines: list[str], *, exclude_docstrings: bool) -> int:
    count = 0
    in_triple: str | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if in_triple is not None:
            end_index = stripped.find(in_triple)
            if end_index == -1:
                continue
            remainder = stripped[end_index + 3 :].strip()
            in_triple = None
            if not remainder:
                continue
            stripped = remainder

        if stripped.startswith("#"):
            continue

        if exclude_docstrings and (stripped.startswith('"""') or stripped.startswith("'''")):
            triple = stripped[:3]
            # One-line triple-quoted string: """doc"""
            if stripped.count(triple) >= 2:
                after = stripped.split(triple, 2)[2].strip()
                if not after:
                    continue
                stripped = after
            else:
                in_triple = triple
                continue

        count += 1

    return count


def _count_sloc_js_like(lines: list[str]) -> int:
    count = 0
    in_block_comment = False

    for line in lines:
        s = line.strip()
        if not s:
            continue

        while True:
            if in_block_comment:
                end = s.find("*/")
                if end == -1:
                    s = ""
                    break
                s = s[end + 2 :].strip()
                in_block_comment = False
                if not s:
                    break
                continue

            if s.startswith("//"):
                s = ""
                break

            if s.startswith("/*"):
                end = s.find("*/", 2)
                if end == -1:
                    in_block_comment = True
                    s = ""
                    break
                s = s[end + 2 :].strip()
                if not s:
                    break
                continue

            break

        if not s:
            continue

        count += 1

    return count


def count_sloc(path: Path, *, exclude_docstrings: bool) -> int:
    lines = _read_text_lines(path)
    ext = path.suffix.lower()
    if ext == ".py":
        return _count_sloc_python(lines, exclude_docstrings=exclude_docstrings)
    return _count_sloc_js_like(lines)


@dataclass(frozen=True)
class CocomoCoefficients:
    a: float
    b: float
    c: float
    d: float


COCOMO_COEFFICIENTS: dict[str, CocomoCoefficients] = {
    "organic": CocomoCoefficients(a=2.4, b=1.05, c=2.5, d=0.38),
    "semidetached": CocomoCoefficients(a=3.0, b=1.12, c=2.5, d=0.35),
    "embedded": CocomoCoefficients(a=3.6, b=1.20, c=2.5, d=0.32),
}


# COCOMO'81 Intermediate cost drivers (Effort Adjustment Factor multipliers).
COCOMO_DRIVERS: dict[str, dict[str, float]] = {
    "RELY": {"VL": 0.75, "L": 0.88, "N": 1.00, "H": 1.15, "VH": 1.40},
    "DATA": {"L": 0.94, "N": 1.00, "H": 1.08, "VH": 1.16},
    "CPLX": {"VL": 0.70, "L": 0.85, "N": 1.00, "H": 1.15, "VH": 1.30, "XH": 1.65},
    "TIME": {"N": 1.00, "H": 1.11, "VH": 1.30, "XH": 1.66},
    "STOR": {"N": 1.00, "H": 1.06, "VH": 1.21, "XH": 1.56},
    "VIRT": {"VL": 0.87, "L": 0.94, "N": 1.00, "H": 1.10, "VH": 1.15},
    "TURN": {"L": 0.87, "N": 1.00, "H": 1.07, "VH": 1.15},
    "ACAP": {"VL": 1.46, "L": 1.19, "N": 1.00, "H": 0.86, "VH": 0.71},
    "AEXP": {"VL": 1.29, "L": 1.13, "N": 1.00, "H": 0.91, "VH": 0.82},
    "PCAP": {"VL": 1.42, "L": 1.17, "N": 1.00, "H": 0.86, "VH": 0.70},
    "VEXP": {"VL": 1.21, "L": 1.10, "N": 1.00, "H": 0.90},
    "LEXP": {"VL": 1.14, "L": 1.07, "N": 1.00, "H": 0.95},
    "MODP": {"VL": 1.24, "L": 1.10, "N": 1.00, "H": 0.91, "VH": 0.82},
    "TOOL": {"VL": 1.24, "L": 1.10, "N": 1.00, "H": 0.91, "VH": 0.83},
    "SCED": {"VL": 1.23, "L": 1.08, "N": 1.00, "H": 1.04, "VH": 1.10},
}


def _parse_driver_assignments(assignments: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for a in assignments:
        if "=" not in a:
            raise ValueError(f"Invalid --driver value: {a!r}. Expected e.g. RELY=H")
        key, value = a.split("=", 1)
        key = key.strip().upper()
        value = value.strip().upper()
        if not key or not value:
            raise ValueError(f"Invalid --driver value: {a!r}. Expected e.g. RELY=H")
        parsed[key] = value
    return parsed


def compute_eaf(drivers: dict[str, str]) -> float:
    eaf = 1.0
    for driver_name, rating in drivers.items():
        if driver_name not in COCOMO_DRIVERS:
            valid = ", ".join(sorted(COCOMO_DRIVERS))
            raise ValueError(f"Unknown driver {driver_name!r}. Valid: {valid}")
        rating_map = COCOMO_DRIVERS[driver_name]
        if rating not in rating_map:
            valid_ratings = ", ".join(sorted(rating_map))
            raise ValueError(f"Invalid rating {rating!r} for {driver_name}. Valid: {valid_ratings}")
        eaf *= rating_map[rating]
    return eaf


@dataclass(frozen=True)
class CocomoResult:
    kloc: float
    eaf: float
    effort_pm: float
    tdev_months: float
    avg_staff: float


def compute_cocomo_intermediate(*, mode: str, kloc: float, eaf: float) -> CocomoResult:
    if kloc <= 0:
        raise ValueError("KLOC must be > 0")
    coeff = COCOMO_COEFFICIENTS[mode]
    effort = coeff.a * (kloc**coeff.b) * eaf
    tdev = coeff.c * (effort**coeff.d)
    staff = effort / tdev if tdev > 0 else float("nan")
    return CocomoResult(kloc=kloc, eaf=eaf, effort_pm=effort, tdev_months=tdev, avg_staff=staff)


@dataclass(frozen=True)
class HalsteadCounts:
    distinct_operators: int
    distinct_operands: int
    total_operators: int
    total_operands: int


@dataclass(frozen=True)
class HalsteadMetrics:
    n1: int
    n2: int
    N1: int
    N2: int
    vocabulary: int
    length: int
    volume: float
    difficulty: float
    effort: float
    time_seconds: float
    delivered_bugs: float


def _safe_log2(x: float) -> float:
    return math.log2(x) if x > 0 else 0.0


def compute_halstead_metrics(counts: HalsteadCounts) -> HalsteadMetrics:
    n1 = int(counts.distinct_operators)
    n2 = int(counts.distinct_operands)
    N1 = int(counts.total_operators)
    N2 = int(counts.total_operands)

    vocabulary = n1 + n2
    length = N1 + N2
    volume = float(length) * _safe_log2(float(vocabulary))
    difficulty = (float(n1) / 2.0) * (float(N2) / float(n2)) if n2 > 0 else 0.0
    effort = difficulty * volume
    time_seconds = effort / 18.0 if effort > 0 else 0.0
    delivered_bugs = volume / 3000.0 if volume > 0 else 0.0

    return HalsteadMetrics(
        n1=n1,
        n2=n2,
        N1=N1,
        N2=N2,
        vocabulary=vocabulary,
        length=length,
        volume=volume,
        difficulty=difficulty,
        effort=effort,
        time_seconds=time_seconds,
        delivered_bugs=delivered_bugs,
    )


@dataclass(frozen=True)
class FunctionPointCounts:
    ei: tuple[int, int, int]  # low, avg, high
    eo: tuple[int, int, int]
    eq: tuple[int, int, int]
    ilf: tuple[int, int, int]
    eif: tuple[int, int, int]


@dataclass(frozen=True)
class FunctionPointResult:
    ufp: int
    tdi: int | None
    vaf: float | None
    afp: float


IFPUG_WEIGHTS: dict[str, tuple[int, int, int]] = {
    "EI": (3, 4, 6),
    "EO": (4, 5, 7),
    "EQ": (3, 4, 6),
    "ILF": (7, 10, 15),
    "EIF": (5, 7, 10),
}


def _weighted_sum(counts: tuple[int, int, int], weights: tuple[int, int, int]) -> int:
    return int(counts[0]) * int(weights[0]) + int(counts[1]) * int(weights[1]) + int(counts[2]) * int(weights[2])


def compute_function_points(
    *,
    counts: FunctionPointCounts,
    gsc_ratings: list[int] | None,
    vaf_override: float | None,
) -> FunctionPointResult:
    for group_name, triplet in {
        "EI": counts.ei,
        "EO": counts.eo,
        "EQ": counts.eq,
        "ILF": counts.ilf,
        "EIF": counts.eif,
    }.items():
        if any(v < 0 for v in triplet):
            raise ValueError(f"{group_name} counts must be >= 0")

    ufp = 0
    ufp += _weighted_sum(counts.ei, IFPUG_WEIGHTS["EI"])
    ufp += _weighted_sum(counts.eo, IFPUG_WEIGHTS["EO"])
    ufp += _weighted_sum(counts.eq, IFPUG_WEIGHTS["EQ"])
    ufp += _weighted_sum(counts.ilf, IFPUG_WEIGHTS["ILF"])
    ufp += _weighted_sum(counts.eif, IFPUG_WEIGHTS["EIF"])

    if vaf_override is not None:
        vaf = float(vaf_override)
        if vaf <= 0:
            raise ValueError("--vaf must be > 0")
        return FunctionPointResult(ufp=ufp, tdi=None, vaf=vaf, afp=float(ufp) * vaf)

    if gsc_ratings is None:
        return FunctionPointResult(ufp=ufp, tdi=None, vaf=None, afp=float(ufp))

    if len(gsc_ratings) != 14:
        raise ValueError("--gsc must have exactly 14 integers (0..5)")
    if any((r < 0 or r > 5) for r in gsc_ratings):
        raise ValueError("--gsc ratings must be integers in range 0..5")

    tdi = int(sum(gsc_ratings))
    vaf = 0.65 + 0.01 * float(tdi)
    return FunctionPointResult(ufp=ufp, tdi=tdi, vaf=vaf, afp=float(ufp) * vaf)


def _python_docstring_line_ranges(path: Path) -> list[tuple[int, int]]:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    ranges: list[tuple[int, int]] = []

    def add_doc(node: ast.AST) -> None:
        body = getattr(node, "body", None)
        if not body:
            return
        first = body[0]
        if not isinstance(first, ast.Expr):
            return
        value = first.value
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            return
        start = getattr(value, "lineno", None)
        end = getattr(value, "end_lineno", None)
        if isinstance(start, int) and isinstance(end, int):
            ranges.append((start, end))

    add_doc(tree)

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            add_doc(node)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            add_doc(node)
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            add_doc(node)
            self.generic_visit(node)

    Visitor().visit(tree)
    return ranges


def _line_in_ranges(line: int, ranges: list[tuple[int, int]]) -> bool:
    for start, end in ranges:
        if start <= line <= end:
            return True
    return False


def halstead_counts_python(path: Path, *, include_docstrings: bool) -> HalsteadCounts:
    operators, operands, total_ops, total_operands = halstead_tally_python(
        path, include_docstrings=include_docstrings
    )
    return HalsteadCounts(len(operators), len(operands), total_ops, total_operands)


def halstead_tally_python(
    path: Path, *, include_docstrings: bool
) -> tuple[set[str], set[str], int, int]:
    operators: set[str] = set()
    operands: set[str] = set()
    total_ops = 0
    total_operands = 0

    doc_ranges = _python_docstring_line_ranges(path) if not include_docstrings else []

    try:
        with tokenize.open(path) as f:
            tokens = tokenize.generate_tokens(f.readline)
            for tok in tokens:
                tok_type = tok.type
                tok_str = tok.string

                if tok_type in {
                    tokenize.NL,
                    tokenize.NEWLINE,
                    tokenize.INDENT,
                    tokenize.DEDENT,
                    tokenize.ENCODING,
                    tokenize.ENDMARKER,
                    tokenize.COMMENT,
                }:
                    continue

                if tok_type == tokenize.STRING:
                    if (not include_docstrings) and _line_in_ranges(tok.start[0], doc_ranges):
                        continue
                    operands.add("<str>")
                    total_operands += 1
                    continue

                if tok_type == tokenize.NUMBER:
                    operands.add("<num>")
                    total_operands += 1
                    continue

                if tok_type == tokenize.NAME:
                    if keyword.iskeyword(tok_str):
                        operators.add(tok_str)
                        total_ops += 1
                    else:
                        operands.add(tok_str)
                        total_operands += 1
                    continue

                if tok_type == tokenize.OP:
                    operators.add(tok_str)
                    total_ops += 1
                    continue
    except OSError:
        return set(), set(), 0, 0
    except tokenize.TokenError:
        return set(), set(), 0, 0

    return operators, operands, total_ops, total_operands


JS_KEYWORDS = {
    "break",
    "case",
    "catch",
    "class",
    "const",
    "continue",
    "debugger",
    "default",
    "delete",
    "do",
    "else",
    "export",
    "extends",
    "finally",
    "for",
    "function",
    "if",
    "import",
    "in",
    "instanceof",
    "let",
    "new",
    "return",
    "super",
    "switch",
    "this",
    "throw",
    "try",
    "typeof",
    "var",
    "void",
    "while",
    "with",
    "yield",
    "await",
    "enum",
    "implements",
    "interface",
    "package",
    "private",
    "protected",
    "public",
    "static",
    "null",
    "true",
    "false",
}


JS_OPERATORS = sorted(
    {
        ">>>=",
        "===", "!==",
        ">>>", "<<=", ">>=",
        "**=",
        "&&=", "||=", "??=",
        "==", "!=", "<=", ">=",
        "&&", "||", "??",
        "++", "--",
        "+=", "-=", "*=", "/=", "%=",
        "&=", "|=", "^=",
        "=>",
        "<<", ">>",
        "**",
        "+", "-", "*", "/", "%", "!",
        "~", "&", "|", "^",
        "<", ">", "=", "?",
        ":", ".", ",", ";",
        "(", ")", "[", "]", "{", "}",
    },
    key=len,
    reverse=True,
)


def _js_tokenize(source: str) -> list[tuple[str, str]]:
    """
    Approximate JS/TS tokenizer.
    Returns list of (kind, value) where kind is: 'op', 'id', 'num', 'str', 'kw'.
    """
    tokens: list[tuple[str, str]] = []
    i = 0
    n = len(source)

    def startswith_any(ops: list[str], at: int) -> str | None:
        for op in ops:
            if source.startswith(op, at):
                return op
        return None

    while i < n:
        ch = source[i]

        if ch.isspace():
            i += 1
            continue

        if source.startswith("//", i):
            nl = source.find("\n", i + 2)
            i = n if nl == -1 else nl + 1
            continue

        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue

        if ch in {"'", '"', "`"}:
            quote = ch
            i += 1
            while i < n:
                c = source[i]
                if c == "\\":
                    i += 2
                    continue
                if c == quote:
                    i += 1
                    break
                i += 1
            tokens.append(("str", "<str>"))
            continue

        if ch.isdigit():
            j = i + 1
            while j < n and (source[j].isdigit() or source[j] in {".", "_", "x", "X", "a", "b", "c", "d", "e", "f", "A", "B", "C", "D", "E", "F"}):
                j += 1
            tokens.append(("num", "<num>"))
            i = j
            continue

        if ch.isalpha() or ch in {"_", "$"}:
            j = i + 1
            while j < n and (source[j].isalnum() or source[j] in {"_", "$"}):
                j += 1
            ident = source[i:j]
            if ident in JS_KEYWORDS:
                tokens.append(("kw", ident))
            else:
                tokens.append(("id", ident))
            i = j
            continue

        op = startswith_any(JS_OPERATORS, i)
        if op is not None:
            tokens.append(("op", op))
            i += len(op)
            continue

        # Unknown single character: treat as operator to avoid dropping structure.
        tokens.append(("op", ch))
        i += 1

    return tokens


def halstead_counts_js_like(path: Path) -> HalsteadCounts:
    operators, operands, total_ops, total_operands = halstead_tally_js_like(path)
    return HalsteadCounts(len(operators), len(operands), total_ops, total_operands)


def halstead_tally_js_like(path: Path) -> tuple[set[str], set[str], int, int]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), 0, 0

    operators: set[str] = set()
    operands: set[str] = set()
    total_ops = 0
    total_operands = 0

    for kind, val in _js_tokenize(source):
        if kind in {"op", "kw"}:
            operators.add(val)
            total_ops += 1
        elif kind in {"id", "num", "str"}:
            operands.add(val)
            total_operands += 1

    return operators, operands, total_ops, total_operands


def halstead_counts(path: Path, *, include_docstrings: bool) -> HalsteadCounts:
    ext = path.suffix.lower()
    if ext == ".py":
        return halstead_counts_python(path, include_docstrings=include_docstrings)
    return halstead_counts_js_like(path)


def halstead_tally(path: Path, *, include_docstrings: bool) -> tuple[set[str], set[str], int, int]:
    ext = path.suffix.lower()
    if ext == ".py":
        return halstead_tally_python(path, include_docstrings=include_docstrings)
    return halstead_tally_js_like(path)


def _parse_cfd_csv(path: Path) -> tuple[list[date], list[str], list[list[int]]]:
    """
    CSV format:
      date,<stage1>,<stage2>,...
    where each row is a daily snapshot and values are counts (>= 0).
    """
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError("CSV has no header row")
            fieldnames = [h.strip() for h in reader.fieldnames if h is not None]
            if not fieldnames or fieldnames[0].lower() != "date":
                raise ValueError("First header must be 'date'")
            stages = fieldnames[1:]
            if not stages:
                raise ValueError("CSV must include at least one stage column after 'date'")

            dates: list[date] = []
            rows: list[list[int]] = []
            for row in reader:
                raw_date = (row.get("date") or "").strip()
                if not raw_date:
                    continue
                try:
                    d = date.fromisoformat(raw_date)
                except ValueError as exc:
                    raise ValueError(f"Invalid date {raw_date!r}; expected YYYY-MM-DD") from exc

                values: list[int] = []
                for stage in stages:
                    raw = (row.get(stage) or "").strip()
                    if raw == "":
                        raise ValueError(f"Missing value for stage {stage!r} on {raw_date}")
                    try:
                        v = int(raw)
                    except ValueError as exc:
                        raise ValueError(
                            f"Invalid integer {raw!r} for stage {stage!r} on {raw_date}"
                        ) from exc
                    if v < 0:
                        raise ValueError(f"Stage {stage!r} count must be >= 0 on {raw_date}")
                    values.append(v)

                dates.append(d)
                rows.append(values)
    except OSError as exc:
        raise ValueError(f"Unable to read CFD CSV: {path}") from exc

    if not dates:
        raise ValueError("No CFD rows found (empty file?)")

    combined = sorted(zip(dates, rows), key=lambda t: t[0])
    dates_sorted = [d for d, _ in combined]
    rows_sorted = [r for _, r in combined]

    seen: set[date] = set()
    for d in dates_sorted:
        if d in seen:
            raise ValueError(f"Duplicate date in CFD CSV: {d.isoformat()}")
        seen.add(d)

    return dates_sorted, stages, rows_sorted


def _svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _cfd_palette(n: int) -> list[str]:
    base = [
        "#4E79A7",
        "#F28E2B",
        "#E15759",
        "#76B7B2",
        "#59A14F",
        "#EDC948",
        "#B07AA1",
        "#FF9DA7",
        "#9C755F",
        "#BAB0AC",
    ]
    if n <= len(base):
        return base[:n]
    # Repeat deterministically if more stages than palette.
    out: list[str] = []
    for i in range(n):
        out.append(base[i % len(base)])
    return out


def _render_cfd_svg(
    *,
    dates: list[date],
    stages: list[str],
    rows: list[list[int]],
    title: str,
    width: int,
    height: int,
) -> str:
    if len(dates) != len(rows):
        raise ValueError("CFD dates/rows length mismatch")
    if not stages:
        raise ValueError("No CFD stages")

    totals = [sum(r) for r in rows]
    max_total = max(totals) if totals else 0
    max_total = max(max_total, 1)

    margin_left = 70
    margin_right = 20
    margin_top = 50
    margin_bottom = 60
    plot_w = max(1, width - margin_left - margin_right)
    plot_h = max(1, height - margin_top - margin_bottom)

    n_points = len(dates)
    x_positions: list[float] = []
    for i in range(n_points):
        x = margin_left + (plot_w * i / (n_points - 1)) if n_points > 1 else margin_left
        x_positions.append(float(x))

    def y_for(value: float) -> float:
        return float(margin_top + plot_h * (1.0 - (value / float(max_total))))

    # Build cumulative boundaries.
    cum: list[list[int]] = []
    for row in rows:
        running = 0
        bounds: list[int] = [0]
        for v in row:
            running += v
            bounds.append(running)
        cum.append(bounds)  # length = len(stages)+1

    colors = _cfd_palette(len(stages))

    parts: list[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    parts.append('<rect x="0" y="0" width="100%" height="100%" fill="#ffffff"/>')
    parts.append(f'<text x="{width/2:.1f}" y="28" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" fill="#111">{_svg_escape(title)}</text>')

    # Gridlines and y-axis labels (0, 25, 50, 75, 100% of max_total)
    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        yv = y_for(max_total * frac)
        parts.append(f'<line x1="{margin_left}" y1="{yv:.1f}" x2="{margin_left+plot_w}" y2="{yv:.1f}" stroke="#e6e6e6" stroke-width="1"/>')
        label = int(round(max_total * frac))
        parts.append(f'<text x="{margin_left-10}" y="{yv+4:.1f}" text-anchor="end" font-family="Arial, sans-serif" font-size="10" fill="#444">{label}</text>')

    # X-axis ticks (up to ~8 labels)
    max_labels = 8
    step = max(1, int(math.ceil(n_points / max_labels)))
    for i in range(0, n_points, step):
        x = x_positions[i]
        parts.append(f'<line x1="{x:.1f}" y1="{margin_top+plot_h}" x2="{x:.1f}" y2="{margin_top+plot_h+6}" stroke="#666" stroke-width="1"/>')
        lbl = dates[i].isoformat()
        parts.append(f'<text x="{x:.1f}" y="{margin_top+plot_h+22}" text-anchor="middle" font-family="Arial, sans-serif" font-size="10" fill="#444">{_svg_escape(lbl)}</text>')

    # Axes
    parts.append(f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top+plot_h}" stroke="#666" stroke-width="1.2"/>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top+plot_h}" x2="{margin_left+plot_w}" y2="{margin_top+plot_h}" stroke="#666" stroke-width="1.2"/>')

    # Stacked areas from bottom to top.
    for stage_index, stage_name in enumerate(stages):
        top_points: list[tuple[float, float]] = []
        bottom_points: list[tuple[float, float]] = []
        for i in range(n_points):
            x = x_positions[i]
            y_top = y_for(cum[i][stage_index + 1])
            y_bottom = y_for(cum[i][stage_index])
            top_points.append((x, y_top))
            bottom_points.append((x, y_bottom))

        # Polygon path: top left->right then bottom right->left.
        pts = top_points + list(reversed(bottom_points))
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        color = colors[stage_index]
        parts.append(f'<polygon points="{d}" fill="{color}" fill-opacity="0.85" stroke="#ffffff" stroke-width="1"/>')

    # Legend (right side)
    legend_x = margin_left + plot_w - 10
    legend_y = margin_top + 8
    parts.append(f'<g font-family="Arial, sans-serif" font-size="11" fill="#111">')
    for i, stage_name in enumerate(reversed(stages)):
        idx = len(stages) - 1 - i
        y = legend_y + i * 18
        parts.append(f'<rect x="{legend_x-140}" y="{y-10}" width="12" height="12" fill="{colors[idx]}" fill-opacity="0.85" stroke="#fff" stroke-width="1"/>')
        parts.append(f'<text x="{legend_x-122}" y="{y}" text-anchor="start">{_svg_escape(stage_name)}</text>')
    parts.append("</g>")

    parts.append("</svg>")
    return "\n".join(parts)


def _stage_index(stages: list[str], stage_name: str) -> int:
    normalized = {s.strip().lower(): i for i, s in enumerate(stages)}
    key = stage_name.strip().lower()
    if key not in normalized:
        raise ValueError(f"Stage {stage_name!r} not found in CSV headers: {', '.join(stages)}")
    return normalized[key]


@dataclass(frozen=True)
class ThroughputPoint:
    period_start: date
    completed: int
    raw_delta: int


def _compute_throughput_daily(
    *,
    dates: list[date],
    stages: list[str],
    rows: list[list[int]],
    done_stage: str,
    allow_negative: bool,
) -> list[ThroughputPoint]:
    idx = _stage_index(stages, done_stage)
    points: list[ThroughputPoint] = []
    prev_done: int | None = None
    for d, row in zip(dates, rows):
        done = int(row[idx])
        if prev_done is None:
            prev_done = done
            continue
        delta = done - prev_done
        prev_done = done
        completed = delta if allow_negative else max(0, delta)
        points.append(ThroughputPoint(period_start=d, completed=completed, raw_delta=delta))
    return points


def _compute_throughput_weekly(points: list[ThroughputPoint]) -> list[ThroughputPoint]:
    buckets: dict[date, tuple[int, int]] = {}
    for p in points:
        week_start = p.period_start - timedelta(days=p.period_start.weekday())
        completed_sum, raw_sum = buckets.get(week_start, (0, 0))
        buckets[week_start] = (completed_sum + int(p.completed), raw_sum + int(p.raw_delta))

    out: list[ThroughputPoint] = []
    for week_start in sorted(buckets):
        completed_sum, raw_sum = buckets[week_start]
        out.append(ThroughputPoint(period_start=week_start, completed=completed_sum, raw_delta=raw_sum))
    return out


def _render_throughput_markdown(
    *,
    title: str,
    done_stage: str,
    period: str,
    points: list[ThroughputPoint],
) -> str:
    values = [p.completed for p in points]
    total = sum(values)
    avg = (float(total) / float(len(values))) if values else 0.0

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- Stage: `{done_stage}`")
    lines.append(f"- Period: `{period}`")
    lines.append(f"- Data points: `{len(points)}`")
    lines.append(f"- Total throughput: `{total}`")
    lines.append(f"- Avg throughput: `{avg:.2f}`")
    lines.append("")
    lines.append("| Period start | Throughput | Raw Δ Done |")
    lines.append("|---|---:|---:|")
    for p in points:
        lines.append(f"| {p.period_start.isoformat()} | {p.completed} | {p.raw_delta} |")
    lines.append("")
    return "\n".join(lines)


def _render_burndown_svg(
    *,
    dates: list[date],
    remaining: list[int],
    title: str,
    width: int,
    height: int,
    show_ideal: bool,
) -> str:
    if len(dates) != len(remaining):
        raise ValueError("Burndown dates/remaining length mismatch")
    if not dates:
        raise ValueError("Burndown requires at least one data point")

    max_rem = max(max(remaining), 1)

    margin_left = 70
    margin_right = 20
    margin_top = 50
    margin_bottom = 60
    plot_w = max(1, width - margin_left - margin_right)
    plot_h = max(1, height - margin_top - margin_bottom)

    n_points = len(dates)
    x_positions: list[float] = []
    for i in range(n_points):
        x = margin_left + (plot_w * i / (n_points - 1)) if n_points > 1 else margin_left
        x_positions.append(float(x))

    def y_for(value: float) -> float:
        return float(margin_top + plot_h * (1.0 - (value / float(max_rem))))

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    )
    parts.append('<rect x="0" y="0" width="100%" height="100%" fill="#ffffff"/>')
    parts.append(
        f'<text x="{width/2:.1f}" y="28" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" fill="#111">{_svg_escape(title)}</text>'
    )

    # Gridlines and y-axis labels (0, 25, 50, 75, 100% of max_rem)
    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        yv = y_for(max_rem * frac)
        parts.append(
            f'<line x1="{margin_left}" y1="{yv:.1f}" x2="{margin_left+plot_w}" y2="{yv:.1f}" stroke="#e6e6e6" stroke-width="1"/>'
        )
        label = int(round(max_rem * frac))
        parts.append(
            f'<text x="{margin_left-10}" y="{yv+4:.1f}" text-anchor="end" font-family="Arial, sans-serif" font-size="10" fill="#444">{label}</text>'
        )

    # X-axis ticks (up to ~8 labels)
    max_labels = 8
    step = max(1, int(math.ceil(n_points / max_labels)))
    for i in range(0, n_points, step):
        x = x_positions[i]
        parts.append(
            f'<line x1="{x:.1f}" y1="{margin_top+plot_h}" x2="{x:.1f}" y2="{margin_top+plot_h+6}" stroke="#666" stroke-width="1"/>'
        )
        lbl = dates[i].isoformat()
        parts.append(
            f'<text x="{x:.1f}" y="{margin_top+plot_h+22}" text-anchor="middle" font-family="Arial, sans-serif" font-size="10" fill="#444">{_svg_escape(lbl)}</text>'
        )

    # Axes
    parts.append(
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top+plot_h}" stroke="#666" stroke-width="1.2"/>'
    )
    parts.append(
        f'<line x1="{margin_left}" y1="{margin_top+plot_h}" x2="{margin_left+plot_w}" y2="{margin_top+plot_h}" stroke="#666" stroke-width="1.2"/>'
    )

    # Ideal line (linear to 0 at end)
    if show_ideal and n_points > 1:
        x0 = x_positions[0]
        x1 = x_positions[-1]
        y0 = y_for(float(remaining[0]))
        y1 = y_for(0.0)
        parts.append(
            f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="#999" stroke-width="2" stroke-dasharray="6,6"/>'
        )

    # Actual burndown polyline
    pts = " ".join(f"{x_positions[i]:.1f},{y_for(float(remaining[i])):.1f}" for i in range(n_points))
    parts.append(
        f'<polyline points="{pts}" fill="none" stroke="#4E79A7" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
    )
    for i in range(n_points):
        parts.append(
            f'<circle cx="{x_positions[i]:.1f}" cy="{y_for(float(remaining[i])):.1f}" r="3" fill="#4E79A7" stroke="#ffffff" stroke-width="1"/>'
        )

    # Legend
    legend_x = margin_left + plot_w - 10
    legend_y = margin_top + 8
    parts.append('<g font-family="Arial, sans-serif" font-size="11" fill="#111">')
    parts.append(
        f'<line x1="{legend_x-140}" y1="{legend_y-6}" x2="{legend_x-120}" y2="{legend_y-6}" stroke="#4E79A7" stroke-width="3"/>'
    )
    parts.append(f'<text x="{legend_x-112}" y="{legend_y-2}" text-anchor="start">Remaining</text>')
    if show_ideal and n_points > 1:
        parts.append(
            f'<line x1="{legend_x-140}" y1="{legend_y+12}" x2="{legend_x-120}" y2="{legend_y+12}" stroke="#999" stroke-width="3" stroke-dasharray="6,6"/>'
        )
        parts.append(f'<text x="{legend_x-112}" y="{legend_y+16}" text-anchor="start">Ideal</text>')
    parts.append("</g>")

    parts.append("</svg>")
    return "\n".join(parts)


def _render_burnup_svg(
    *,
    dates: list[date],
    done: list[int],
    scope: list[int],
    title: str,
    width: int,
    height: int,
    show_ideal: bool,
    show_scope: bool,
) -> str:
    if len(dates) != len(done) or len(dates) != len(scope):
        raise ValueError("Burnup dates/done/scope length mismatch")
    if not dates:
        raise ValueError("Burnup requires at least one data point")

    max_y = max(max(scope), max(done), 1)

    margin_left = 70
    margin_right = 20
    margin_top = 50
    margin_bottom = 60
    plot_w = max(1, width - margin_left - margin_right)
    plot_h = max(1, height - margin_top - margin_bottom)

    n_points = len(dates)
    x_positions: list[float] = []
    for i in range(n_points):
        x = margin_left + (plot_w * i / (n_points - 1)) if n_points > 1 else margin_left
        x_positions.append(float(x))

    def y_for(value: float) -> float:
        return float(margin_top + plot_h * (1.0 - (value / float(max_y))))

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    )
    parts.append('<rect x="0" y="0" width="100%" height="100%" fill="#ffffff"/>')
    parts.append(
        f'<text x="{width/2:.1f}" y="28" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" fill="#111">{_svg_escape(title)}</text>'
    )

    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        yv = y_for(max_y * frac)
        parts.append(
            f'<line x1="{margin_left}" y1="{yv:.1f}" x2="{margin_left+plot_w}" y2="{yv:.1f}" stroke="#e6e6e6" stroke-width="1"/>'
        )
        label = int(round(max_y * frac))
        parts.append(
            f'<text x="{margin_left-10}" y="{yv+4:.1f}" text-anchor="end" font-family="Arial, sans-serif" font-size="10" fill="#444">{label}</text>'
        )

    max_labels = 8
    step = max(1, int(math.ceil(n_points / max_labels)))
    for i in range(0, n_points, step):
        x = x_positions[i]
        parts.append(
            f'<line x1="{x:.1f}" y1="{margin_top+plot_h}" x2="{x:.1f}" y2="{margin_top+plot_h+6}" stroke="#666" stroke-width="1"/>'
        )
        lbl = dates[i].isoformat()
        parts.append(
            f'<text x="{x:.1f}" y="{margin_top+plot_h+22}" text-anchor="middle" font-family="Arial, sans-serif" font-size="10" fill="#444">{_svg_escape(lbl)}</text>'
        )

    parts.append(
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top+plot_h}" stroke="#666" stroke-width="1.2"/>'
    )
    parts.append(
        f'<line x1="{margin_left}" y1="{margin_top+plot_h}" x2="{margin_left+plot_w}" y2="{margin_top+plot_h}" stroke="#666" stroke-width="1.2"/>'
    )

    done_color = "#4E79A7"
    scope_color = "#F28E2B"
    ideal_color = "#999"

    if show_ideal and n_points > 1:
        x0 = x_positions[0]
        x1 = x_positions[-1]
        y0 = y_for(0.0)
        y1 = y_for(float(done[-1] if show_scope is False else scope[-1]))
        parts.append(
            f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{ideal_color}" stroke-width="2" stroke-dasharray="6,6"/>'
        )

    if show_scope:
        pts_scope = " ".join(
            f"{x_positions[i]:.1f},{y_for(float(scope[i])):.1f}" for i in range(n_points)
        )
        parts.append(
            f'<polyline points="{pts_scope}" fill="none" stroke="{scope_color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
        )

    pts_done = " ".join(
        f"{x_positions[i]:.1f},{y_for(float(done[i])):.1f}" for i in range(n_points)
    )
    parts.append(
        f'<polyline points="{pts_done}" fill="none" stroke="{done_color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
    )
    for i in range(n_points):
        parts.append(
            f'<circle cx="{x_positions[i]:.1f}" cy="{y_for(float(done[i])):.1f}" r="3" fill="{done_color}" stroke="#ffffff" stroke-width="1"/>'
        )

    legend_x = margin_left + plot_w - 10
    legend_y = margin_top + 8
    parts.append('<g font-family="Arial, sans-serif" font-size="11" fill="#111">')
    parts.append(
        f'<line x1="{legend_x-140}" y1="{legend_y-6}" x2="{legend_x-120}" y2="{legend_y-6}" stroke="{done_color}" stroke-width="3"/>'
    )
    parts.append(f'<text x="{legend_x-112}" y="{legend_y-2}" text-anchor="start">Done</text>')
    legend_offset = 18
    if show_scope:
        parts.append(
            f'<line x1="{legend_x-140}" y1="{legend_y+legend_offset-6}" x2="{legend_x-120}" y2="{legend_y+legend_offset-6}" stroke="{scope_color}" stroke-width="3"/>'
        )
        parts.append(
            f'<text x="{legend_x-112}" y="{legend_y+legend_offset-2}" text-anchor="start">Scope</text>'
        )
        legend_offset += 18
    if show_ideal and n_points > 1:
        parts.append(
            f'<line x1="{legend_x-140}" y1="{legend_y+legend_offset-6}" x2="{legend_x-120}" y2="{legend_y+legend_offset-6}" stroke="{ideal_color}" stroke-width="3" stroke-dasharray="6,6"/>'
        )
        parts.append(
            f'<text x="{legend_x-112}" y="{legend_y+legend_offset-2}" text-anchor="start">Ideal</text>'
        )
    parts.append("</g>")

    parts.append("</svg>")
    return "\n".join(parts)


@dataclass(frozen=True)
class CommentDensity:
    code_sloc: int
    comment_only_lines: int


def _count_comment_only_python(path: Path, *, include_docstrings_as_comments: bool) -> int:
    lines = _read_text_lines(path)
    if not lines:
        return 0
    doc_ranges = _python_docstring_line_ranges(path) if include_docstrings_as_comments else []

    count = 0
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if include_docstrings_as_comments and _line_in_ranges(idx, doc_ranges):
            count += 1
            continue
        if stripped.startswith("#"):
            count += 1
    return count


def _count_comment_only_js_like(path: Path) -> int:
    lines = _read_text_lines(path)
    if not lines:
        return 0

    count = 0
    in_block = False
    for line in lines:
        s = line.strip()
        if not s:
            continue

        if in_block:
            count += 1
            end = s.find("*/")
            if end != -1:
                in_block = False
            continue

        if s.startswith("//"):
            count += 1
            continue

        if s.startswith("/*"):
            count += 1
            if "*/" not in s[2:]:
                in_block = True
            continue

    return count


def compute_comment_density(
    files: list[Path],
    *,
    include_docstrings: bool,
    include_docstrings_as_comments: bool,
) -> tuple[CommentDensity, dict[str, CommentDensity]]:
    total_code = 0
    total_comments = 0

    per_lang: dict[str, CommentDensity] = {}

    for p in files:
        ext = p.suffix.lower()
        if ext not in DEFAULT_INCLUDE_EXTS:
            continue

        code_sloc = count_sloc(p, exclude_docstrings=not include_docstrings)
        if ext == ".py":
            comment_only = _count_comment_only_python(
                p, include_docstrings_as_comments=include_docstrings_as_comments
            )
            lang = "python"
        else:
            comment_only = _count_comment_only_js_like(p)
            lang = "js/ts"

        total_code += code_sloc
        total_comments += comment_only

        prev = per_lang.get(lang, CommentDensity(0, 0))
        per_lang[lang] = CommentDensity(
            code_sloc=prev.code_sloc + code_sloc,
            comment_only_lines=prev.comment_only_lines + comment_only,
        )

    return (
        CommentDensity(code_sloc=total_code, comment_only_lines=total_comments),
        per_lang,
    )


@dataclass(frozen=True)
class DsqDensityResult:
    nodes: int
    edges: int
    density: float
    avg_out_degree: float
    cyclic_sccs: int
    largest_cycle_size: int


def _tarjan_scc(nodes: list[int], edges: dict[int, set[int]]) -> list[list[int]]:
    index = 0
    stack: list[int] = []
    on_stack: set[int] = set()
    indices: dict[int, int] = {}
    lowlink: dict[int, int] = {}
    sccs: list[list[int]] = []

    def strongconnect(v: int) -> None:
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in edges.get(v, set()):
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])

        if lowlink[v] == indices[v]:
            scc: list[int] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.append(w)
                if w == v:
                    break
            sccs.append(scc)

    for v in nodes:
        if v not in indices:
            strongconnect(v)

    return sccs


def _extract_python_import_edges(
    *,
    files: list[Path],
    root: Path,
) -> dict[Path, set[Path]]:
    py_files = [p for p in files if p.suffix.lower() == ".py"]
    if not py_files:
        return {}

    # Identify package dirs (directories containing __init__.py).
    package_dirs: set[Path] = set()
    for p in py_files:
        if p.name == "__init__.py":
            package_dirs.add(p.parent)

    def package_root_for(path: Path) -> Path | None:
        cur = path.parent
        top: Path | None = None
        while True:
            if cur in package_dirs:
                top = cur
                parent = cur.parent
                if parent in package_dirs:
                    cur = parent
                    continue
                return top
            if cur == root or cur.parent == cur:
                return None
            cur = cur.parent

    module_map: dict[str, Path] = {}
    file_to_module: dict[Path, str] = {}
    for p in py_files:
        pr = package_root_for(p)
        if pr is None:
            continue
        base = pr.name
        rel = p.relative_to(pr)
        parts = list(rel.parts)
        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        if parts[-1] == "__init__":
            parts = parts[:-1]
        module = ".".join([base, *parts]) if parts else base
        module_map[module] = p
        file_to_module[p] = module

    def resolve_module(mod: str) -> Path | None:
        if mod in module_map:
            return module_map[mod]
        return None

    def current_package(module: str) -> str:
        parts = module.split(".")
        return module if parts else module

    edges: dict[Path, set[Path]] = {p: set() for p in py_files}
    for src in py_files:
        if src not in file_to_module:
            continue
        src_module = file_to_module[src]
        if src.name == "__init__.py":
            pkg_module = src_module
        else:
            pkg_module = ".".join(src_module.split(".")[:-1])

        try:
            text = src.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text)
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = resolve_module(alias.name)
                    if target is not None and target != src:
                        edges[src].add(target)
            elif isinstance(node, ast.ImportFrom):
                level = int(getattr(node, "level", 0) or 0)
                mod = node.module
                base_mod: str | None = None
                if level > 0:
                    pkg_parts = pkg_module.split(".") if pkg_module else []
                    trim = max(0, level - 1)
                    base_parts = pkg_parts[: max(0, len(pkg_parts) - trim)]
                    if mod:
                        base_parts += mod.split(".")
                    base_mod = ".".join(base_parts) if base_parts else None
                else:
                    base_mod = mod

                if not base_mod:
                    continue

                for alias in node.names:
                    if alias.name == "*":
                        target = resolve_module(base_mod)
                        if target is not None and target != src:
                            edges[src].add(target)
                        continue
                    candidate = f"{base_mod}.{alias.name}"
                    target = resolve_module(candidate) or resolve_module(base_mod)
                    if target is not None and target != src:
                        edges[src].add(target)

    return edges


def _extract_js_import_edges(
    *,
    files: list[Path],
    root: Path,
) -> dict[Path, set[Path]]:
    js_files = [p for p in files if p.suffix.lower() in DEFAULT_INCLUDE_EXTS and p.suffix.lower() != ".py"]
    if not js_files:
        return {}

    file_set: set[Path] = set(js_files)
    rel_to_file: dict[str, Path] = {p.relative_to(root).as_posix(): p for p in js_files}

    def resolve_relative(src: Path, spec: str) -> Path | None:
        if not (spec.startswith("./") or spec.startswith("../") or spec == "." or spec == ".."):
            return None
        base = (src.parent / spec).resolve()
        candidates: list[Path] = []
        if base.suffix:
            candidates.append(base)
        else:
            for ext in DEFAULT_INCLUDE_EXTS:
                candidates.append(Path(str(base) + ext))
            for ext in DEFAULT_INCLUDE_EXTS:
                candidates.append(base / f"index{ext}")

        for c in candidates:
            try:
                rel = c.relative_to(root).as_posix()
            except Exception:
                continue
            if rel in rel_to_file:
                return rel_to_file[rel]
        return None

    def extract_specs(text: str) -> list[str]:
        specs: list[str] = []
        i = 0
        n = len(text)
        in_line = False
        in_block = False
        in_str: str | None = None
        escape = False

        def is_ident_char(ch: str) -> bool:
            return ch.isalnum() or ch in {"_", "$"}

        while i < n:
            ch = text[i]

            if in_line:
                if ch == "\n":
                    in_line = False
                i += 1
                continue
            if in_block:
                if ch == "*" and i + 1 < n and text[i + 1] == "/":
                    in_block = False
                    i += 2
                    continue
                i += 1
                continue
            if in_str is not None:
                if escape:
                    escape = False
                    i += 1
                    continue
                if ch == "\\":
                    escape = True
                    i += 1
                    continue
                if ch == in_str:
                    in_str = None
                i += 1
                continue

            if ch == "/" and i + 1 < n and text[i + 1] == "/":
                in_line = True
                i += 2
                continue
            if ch == "/" and i + 1 < n and text[i + 1] == "*":
                in_block = True
                i += 2
                continue
            if ch in {"'", '"', "`"}:
                in_str = ch
                i += 1
                continue

            if text.startswith("import", i) and (i == 0 or not is_ident_char(text[i - 1])):
                j = i + 6
                if j < n and is_ident_char(text[j]):
                    i += 1
                    continue
                # dynamic import(...)
                k = j
                while k < n and text[k].isspace():
                    k += 1
                if k < n and text[k] == "(":
                    k += 1
                    while k < n and text[k].isspace():
                        k += 1
                    if k < n and text[k] in {"'", '"'}:
                        quote = text[k]
                        k += 1
                        start = k
                        while k < n and text[k] != quote:
                            if text[k] == "\\":
                                k += 2
                                continue
                            k += 1
                        specs.append(text[start:k])
                else:
                    # import 'x' or import ... from 'x'
                    # scan ahead for first quote after "from" or directly after import.
                    scan = text[j : min(n, j + 300)]
                    from_idx = scan.find("from")
                    qpos = None
                    if from_idx != -1:
                        qpos = scan.find("'", from_idx)
                        qpos2 = scan.find('"', from_idx)
                    else:
                        qpos = scan.find("'")
                        qpos2 = scan.find('"')
                    if qpos is None:
                        qpos = -1
                    if qpos2 is None:
                        qpos2 = -1
                    pick = min([p for p in [qpos, qpos2] if p != -1], default=-1)
                    if pick != -1:
                        quote = scan[pick]
                        start = j + pick + 1
                        k2 = start
                        while k2 < n and text[k2] != quote:
                            if text[k2] == "\\":
                                k2 += 2
                                continue
                            k2 += 1
                        specs.append(text[start:k2])
                i = j
                continue

            if text.startswith("require", i) and (i == 0 or not is_ident_char(text[i - 1])):
                j = i + 7
                if j < n and is_ident_char(text[j]):
                    i += 1
                    continue
                k = j
                while k < n and text[k].isspace():
                    k += 1
                if k < n and text[k] == "(":
                    k += 1
                    while k < n and text[k].isspace():
                        k += 1
                    if k < n and text[k] in {"'", '"'}:
                        quote = text[k]
                        k += 1
                        start = k
                        while k < n and text[k] != quote:
                            if text[k] == "\\":
                                k += 2
                                continue
                            k += 1
                        specs.append(text[start:k])
                i = j
                continue

            i += 1

        return specs

    edges: dict[Path, set[Path]] = {p: set() for p in js_files}
    for src in js_files:
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for spec in extract_specs(text):
            target = resolve_relative(src, spec)
            if target is not None and target != src and target in file_set:
                edges[src].add(target)

    return edges


def compute_dsqd(
    *,
    files: list[Path],
    root: Path,
) -> DsqDensityResult:
    file_list = [p for p in files if p.suffix.lower() in DEFAULT_INCLUDE_EXTS]
    file_list = sorted(set(file_list))
    n = len(file_list)
    if n <= 1:
        return DsqDensityResult(nodes=n, edges=0, density=0.0, avg_out_degree=0.0, cyclic_sccs=0, largest_cycle_size=0)

    py_edges = _extract_python_import_edges(files=file_list, root=root)
    js_edges = _extract_js_import_edges(files=file_list, root=root)

    combined_edges: dict[Path, set[Path]] = {p: set() for p in file_list}
    for src, tgts in py_edges.items():
        combined_edges.setdefault(src, set()).update(tgts)
    for src, tgts in js_edges.items():
        combined_edges.setdefault(src, set()).update(tgts)

    edge_set: set[tuple[Path, Path]] = set()
    for src, tgts in combined_edges.items():
        for tgt in tgts:
            if src == tgt:
                continue
            edge_set.add((src, tgt))

    m = len(edge_set)
    density = float(m) / float(n * (n - 1))
    avg_out = float(m) / float(n) if n > 0 else 0.0

    idx_map = {p: i for i, p in enumerate(file_list)}
    graph: dict[int, set[int]] = {}
    nodes_idx = list(range(n))
    for src, tgt in edge_set:
        graph.setdefault(idx_map[src], set()).add(idx_map[tgt])

    sccs = _tarjan_scc(nodes_idx, graph)
    cyclic = [s for s in sccs if len(s) > 1]
    largest = max((len(s) for s in cyclic), default=0)

    return DsqDensityResult(
        nodes=n,
        edges=m,
        density=density,
        avg_out_degree=avg_out,
        cyclic_sccs=len(cyclic),
        largest_cycle_size=largest,
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compute Intermediate COCOMO'81 from repo SLOC while excluding vendor/generated/docs/config artifacts.\n"
            "By default this counts only tracked production code (excludes tests)."
        )
    )
    parser.add_argument("--mode", choices=sorted(COCOMO_COEFFICIENTS), default="organic")
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (default: exclude tests).",
    )
    parser.add_argument(
        "--include-docstrings",
        action="store_true",
        help="Include Python triple-quoted docstrings (default: excluded).",
    )
    parser.add_argument(
        "--root",
        default=str(PROJECT_ROOT),
        help="Project root to analyze (default: repo root).",
    )
    parser.add_argument(
        "--include-ext",
        action="append",
        default=[],
        help="Add an extension to include (repeatable), e.g. --include-ext .sh",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Add a directory-name to exclude (repeatable), e.g. --exclude-dir vendor",
    )
    parser.add_argument(
        "--eaf",
        type=float,
        default=None,
        help="Effort Adjustment Factor. If omitted, computed from --driver inputs or defaults to 1.0",
    )
    parser.add_argument(
        "--driver",
        action="append",
        default=[],
        help="Set a cost driver rating (repeatable), e.g. --driver RELY=H --driver CPLX=VH",
    )
    parser.add_argument(
        "--cost-per-pm",
        type=float,
        default=None,
        help="Optional cost per person-month (same currency), prints total cost.",
    )
    parser.add_argument(
        "--print-files",
        action="store_true",
        help="Print each counted file path.",
    )
    parser.add_argument(
        "--no-cocomo",
        action="store_true",
        help="Skip SLOC/COCOMO output (useful when running only --fpa/--cfd).",
    )
    parser.add_argument(
        "--halstead",
        action="store_true",
        help="Also compute Halstead metrics over the same filtered source set.",
    )
    parser.add_argument(
        "--fpa",
        action="store_true",
        help="Also compute Function Point Analysis (IFPUG-style) from provided counts.",
    )
    parser.add_argument(
        "--ei",
        nargs=3,
        type=int,
        default=[0, 0, 0],
        metavar=("LOW", "AVG", "HIGH"),
        help="FPA External Inputs counts (low avg high).",
    )
    parser.add_argument(
        "--eo",
        nargs=3,
        type=int,
        default=[0, 0, 0],
        metavar=("LOW", "AVG", "HIGH"),
        help="FPA External Outputs counts (low avg high).",
    )
    parser.add_argument(
        "--eq",
        nargs=3,
        type=int,
        default=[0, 0, 0],
        metavar=("LOW", "AVG", "HIGH"),
        help="FPA External Inquiries counts (low avg high).",
    )
    parser.add_argument(
        "--ilf",
        nargs=3,
        type=int,
        default=[0, 0, 0],
        metavar=("LOW", "AVG", "HIGH"),
        help="FPA Internal Logical Files counts (low avg high).",
    )
    parser.add_argument(
        "--eif",
        nargs=3,
        type=int,
        default=[0, 0, 0],
        metavar=("LOW", "AVG", "HIGH"),
        help="FPA External Interface Files counts (low avg high).",
    )
    parser.add_argument(
        "--gsc",
        nargs=14,
        type=int,
        default=None,
        metavar=(
            "R1",
            "R2",
            "R3",
            "R4",
            "R5",
            "R6",
            "R7",
            "R8",
            "R9",
            "R10",
            "R11",
            "R12",
            "R13",
            "R14",
        ),
        help="FPA General System Characteristics ratings (14 ints, each 0..5).",
    )
    parser.add_argument(
        "--vaf",
        type=float,
        default=None,
        help="FPA Value Adjustment Factor override (uses UFP * VAF). If set, overrides --gsc.",
    )
    parser.add_argument(
        "--sloc-per-fp",
        type=float,
        default=None,
        help="Optional conversion factor to estimate SLOC from FP (prints estimated SLOC/KLOC).",
    )
    parser.add_argument(
        "--cfd",
        action="store_true",
        help="Generate a Cumulative Flow Diagram (CFD) SVG from a CSV daily snapshot.",
    )
    parser.add_argument(
        "--cfd-input",
        default=None,
        help="Path to CFD CSV input (required with --cfd).",
    )
    parser.add_argument(
        "--cfd-output",
        default=None,
        help="Path to write CFD SVG (default: docs/cfd.svg).",
    )
    parser.add_argument(
        "--cfd-title",
        default="Cumulative Flow Diagram",
        help="Title to embed in the CFD SVG.",
    )
    parser.add_argument(
        "--cfd-width",
        type=int,
        default=1200,
        help="CFD SVG width in pixels (default: 1200).",
    )
    parser.add_argument(
        "--cfd-height",
        type=int,
        default=700,
        help="CFD SVG height in pixels (default: 700).",
    )
    parser.add_argument(
        "--throughput",
        action="store_true",
        help="Generate a throughput report (Markdown) from the same snapshot CSV as --cfd.",
    )
    parser.add_argument(
        "--tp-input",
        default=None,
        help="Path to throughput CSV input (defaults to --cfd-input when set).",
    )
    parser.add_argument(
        "--tp-output",
        default=None,
        help="Path to write throughput report Markdown (default: docs/throughput.md).",
    )
    parser.add_argument(
        "--tp-stage",
        default=None,
        help="Stage column to treat as 'done' (default: last stage column).",
    )
    parser.add_argument(
        "--tp-period",
        choices=["daily", "weekly"],
        default="daily",
        help="Aggregate throughput by day or week (default: daily).",
    )
    parser.add_argument(
        "--tp-allow-negative",
        action="store_true",
        help="Allow negative throughput if Done count decreases (default clips to 0).",
    )
    parser.add_argument(
        "--tp-title",
        default="Throughput Report",
        help="Title for the throughput report.",
    )
    parser.add_argument(
        "--burndown",
        action="store_true",
        help="Generate a sprint burndown chart (SVG) from the same snapshot CSV as --cfd.",
    )
    parser.add_argument(
        "--bd-input",
        default=None,
        help="Path to burndown CSV input (defaults to --cfd-input when set).",
    )
    parser.add_argument(
        "--bd-output",
        default=None,
        help="Path to write burndown SVG (default: docs/burndown.svg).",
    )
    parser.add_argument(
        "--bd-title",
        default="Sprint Burndown",
        help="Title to embed in the burndown SVG.",
    )
    parser.add_argument(
        "--bd-done-stage",
        default=None,
        help="Stage column to treat as 'done' (default: last stage column). Remaining = total - done.",
    )
    parser.add_argument(
        "--bd-width",
        type=int,
        default=1200,
        help="Burndown SVG width in pixels (default: 1200).",
    )
    parser.add_argument(
        "--bd-height",
        type=int,
        default=700,
        help="Burndown SVG height in pixels (default: 700).",
    )
    parser.add_argument(
        "--bd-no-ideal",
        action="store_true",
        help="Do not draw the ideal burndown line.",
    )
    parser.add_argument(
        "--burnup",
        action="store_true",
        help="Generate a sprint burnup chart (SVG) from the same snapshot CSV as --cfd.",
    )
    parser.add_argument(
        "--bu-input",
        default=None,
        help="Path to burnup CSV input (defaults to --cfd-input when set).",
    )
    parser.add_argument(
        "--bu-output",
        default=None,
        help="Path to write burnup SVG (default: docs/burnup.svg).",
    )
    parser.add_argument(
        "--bu-title",
        default="Sprint Burnup",
        help="Title to embed in the burnup SVG.",
    )
    parser.add_argument(
        "--bu-done-stage",
        default=None,
        help="Stage column to treat as 'done' (default: last stage column).",
    )
    parser.add_argument(
        "--bu-width",
        type=int,
        default=1200,
        help="Burnup SVG width in pixels (default: 1200).",
    )
    parser.add_argument(
        "--bu-height",
        type=int,
        default=700,
        help="Burnup SVG height in pixels (default: 700).",
    )
    parser.add_argument(
        "--bu-no-ideal",
        action="store_true",
        help="Do not draw the ideal burnup line.",
    )
    parser.add_argument(
        "--bu-no-scope",
        action="store_true",
        help="Do not draw the scope line.",
    )
    parser.add_argument(
        "--comment-density",
        action="store_true",
        help="Compute comment density over the same filtered code set (approx.).",
    )
    parser.add_argument(
        "--comment-docstrings",
        action="store_true",
        help="Count Python docstring lines as comment-only lines in comment density.",
    )
    parser.add_argument(
        "--dsqd",
        action="store_true",
        help="Compute Design Structure Quality Density (import-dependency density) over source files (approx.).",
    )
    parser.add_argument(
        "--dsqd-dir",
        action="append",
        default=[],
        help="Limit DSQD analysis to a directory (repeatable), e.g. --dsqd-dir node-server/src",
    )

    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    include_exts = set(DEFAULT_INCLUDE_EXTS)
    include_exts.update({e if e.startswith(".") else f".{e}" for e in args.include_ext})

    excluded_dir_parts = set(DEFAULT_EXCLUDE_DIR_PARTS)
    excluded_dir_parts.update({d.strip() for d in args.exclude_dir if d.strip()})

    run_cocomo = not bool(args.no_cocomo)
    run_halstead = bool(args.halstead)
    run_fpa = bool(args.fpa)
    run_cfd = bool(args.cfd)
    run_throughput = bool(args.throughput)
    run_burndown = bool(args.burndown)
    run_burnup = bool(args.burnup)
    run_comment_density = bool(args.comment_density)
    run_dsqd = bool(args.dsqd)

    need_code_scan = (
        run_cocomo
        or run_halstead
        or run_comment_density
        or run_dsqd
        or bool(args.print_files)
    )

    candidates: list[Path] = []
    per_file: list[tuple[Path, int]] = []
    total_sloc = 0
    kloc = 0.0
    drivers: dict[str, str] = {}
    result: CocomoResult | None = None

    if need_code_scan:
        candidates = _iter_candidate_files(
            root=root,
            include_exts=include_exts,
            excluded_dir_parts=excluded_dir_parts,
            excluded_paths=set(DEFAULT_EXCLUDE_PATHS),
            include_tests=bool(args.include_tests),
        )

        if run_cocomo or args.print_files:
            for p in candidates:
                sloc = count_sloc(p, exclude_docstrings=not bool(args.include_docstrings))
                if sloc <= 0:
                    continue
                per_file.append((p, sloc))
                total_sloc += sloc
            kloc = total_sloc / 1000.0

        if args.print_files and per_file:
            for p, sloc in sorted(per_file, key=lambda t: t[0].as_posix()):
                rel = p.relative_to(root).as_posix()
                print(f"{sloc:6d}  {rel}")

        if run_cocomo:
            drivers = _parse_driver_assignments(args.driver)
            eaf = float(args.eaf) if args.eaf is not None else (compute_eaf(drivers) if drivers else 1.0)
            result = compute_cocomo_intermediate(
                mode=args.mode, kloc=max(kloc, sys.float_info.epsilon), eaf=eaf
            )

            print()
            print("SLOC (approx., blank/comment-only lines excluded)")
            print(f"- Counted files: {len(per_file)}")
            print(f"- Total SLOC:    {total_sloc}")
            print(f"- Total KLOC:    {kloc:.3f}")
            if not args.include_tests:
                print("- Scope:         production-only (tests excluded)")
            else:
                print("- Scope:         includes tests")
            print()

            print("Intermediate COCOMO'81")
            print(f"- Mode:          {args.mode}")
            print(f"- EAF:           {result.eaf:.4f}")
            print(f"- Effort:        {result.effort_pm:.2f} person-months")
            print(f"- Schedule:      {result.tdev_months:.2f} months")
            print(f"- Avg staffing:  {result.avg_staff:.2f} persons")

            if args.cost_per_pm is not None:
                total_cost = result.effort_pm * float(args.cost_per_pm)
                print(
                    f"- Total cost:    {total_cost:.2f} (cost-per-pm={float(args.cost_per_pm):.2f})"
                )

            if drivers:
                print()
                print("Drivers used:")
                for k in sorted(drivers):
                    rating = drivers[k]
                    multiplier = COCOMO_DRIVERS[k][rating]
                    print(f"- {k}={rating} ({multiplier})")

    if args.fpa:
        fp_counts = FunctionPointCounts(
            ei=(int(args.ei[0]), int(args.ei[1]), int(args.ei[2])),
            eo=(int(args.eo[0]), int(args.eo[1]), int(args.eo[2])),
            eq=(int(args.eq[0]), int(args.eq[1]), int(args.eq[2])),
            ilf=(int(args.ilf[0]), int(args.ilf[1]), int(args.ilf[2])),
            eif=(int(args.eif[0]), int(args.eif[1]), int(args.eif[2])),
        )
        fp = compute_function_points(
            counts=fp_counts,
            gsc_ratings=list(args.gsc) if args.gsc is not None else None,
            vaf_override=args.vaf,
        )

        print()
        print("Function Point Analysis (IFPUG-style, manual counts)")
        print(f"- UFP:           {fp.ufp}")
        if fp.vaf is None:
            print("- VAF:           (not applied)")
            print(f"- FP:            {fp.afp:.2f}")
        else:
            if fp.tdi is not None:
                print(f"- TDI:           {fp.tdi} (sum of 14 GSC ratings)")
            print(f"- VAF:           {fp.vaf:.4f}")
            print(f"- AFP:           {fp.afp:.2f}")

        if args.sloc_per_fp is not None:
            factor = float(args.sloc_per_fp)
            if factor <= 0:
                raise ValueError("--sloc-per-fp must be > 0")
            est_sloc = fp.afp * factor
            print(f"- Est SLOC:      {est_sloc:.0f} (sloc-per-fp={factor:.2f})")
            print(f"- Est KLOC:      {est_sloc / 1000.0:.3f}")

    if args.halstead:
        if not candidates:
            # Halstead is computed over the same filtered code set; ensure we have it.
            candidates = _iter_candidate_files(
                root=root,
                include_exts=include_exts,
                excluded_dir_parts=excluded_dir_parts,
                excluded_paths=set(DEFAULT_EXCLUDE_PATHS),
                include_tests=bool(args.include_tests),
            )
        op_set_all: set[str] = set()
        operand_set_all: set[str] = set()
        total_ops_all = 0
        total_operands_all = 0

        op_set_py: set[str] = set()
        operand_set_py: set[str] = set()
        total_ops_py = 0
        total_operands_py = 0

        op_set_js: set[str] = set()
        operand_set_js: set[str] = set()
        total_ops_js = 0
        total_operands_js = 0

        include_docstrings = bool(args.include_docstrings)
        for p in candidates:
            ops, operands, total_ops, total_operands = halstead_tally(
                p, include_docstrings=include_docstrings
            )

            op_set_all.update(ops)
            operand_set_all.update(operands)
            total_ops_all += total_ops
            total_operands_all += total_operands

            if p.suffix.lower() == ".py":
                op_set_py.update(ops)
                operand_set_py.update(operands)
                total_ops_py += total_ops
                total_operands_py += total_operands
            else:
                op_set_js.update(ops)
                operand_set_js.update(operands)
                total_ops_js += total_ops
                total_operands_js += total_operands

        total_all = HalsteadCounts(
            distinct_operators=len(op_set_all),
            distinct_operands=len(operand_set_all),
            total_operators=total_ops_all,
            total_operands=total_operands_all,
        )
        metrics = compute_halstead_metrics(total_all)

        print()
        print("Halstead (approx., Python+JS/TS only)")
        print(f"- n1 (distinct operators): {metrics.n1}")
        print(f"- n2 (distinct operands):  {metrics.n2}")
        print(f"- N1 (total operators):    {metrics.N1}")
        print(f"- N2 (total operands):     {metrics.N2}")
        print(f"- Vocabulary (n):          {metrics.vocabulary}")
        print(f"- Length (N):              {metrics.length}")
        print(f"- Volume (V):              {metrics.volume:.2f}")
        print(f"- Difficulty (D):          {metrics.difficulty:.2f}")
        print(f"- Effort (E):              {metrics.effort:.2f}")
        print(f"- Time:                    {metrics.time_seconds:.2f} seconds")
        print(f"- Delivered bugs (B):      {metrics.delivered_bugs:.4f}")

        if total_ops_py + total_operands_py > 0 or total_ops_js + total_operands_js > 0:
            metrics_py = compute_halstead_metrics(
                HalsteadCounts(
                    distinct_operators=len(op_set_py),
                    distinct_operands=len(operand_set_py),
                    total_operators=total_ops_py,
                    total_operands=total_operands_py,
                )
            )
            metrics_js = compute_halstead_metrics(
                HalsteadCounts(
                    distinct_operators=len(op_set_js),
                    distinct_operands=len(operand_set_js),
                    total_operators=total_ops_js,
                    total_operands=total_operands_js,
                )
            )
            print()
            print("Halstead breakdown (approx.)")
            print(
                f"- Python: n={metrics_py.vocabulary}, N={metrics_py.length}, V={metrics_py.volume:.2f}"
            )
            print(
                f"- JS/TS:  n={metrics_js.vocabulary}, N={metrics_js.length}, V={metrics_js.volume:.2f}"
            )

    if run_comment_density:
        if not candidates:
            candidates = _iter_candidate_files(
                root=root,
                include_exts=include_exts,
                excluded_dir_parts=excluded_dir_parts,
                excluded_paths=set(DEFAULT_EXCLUDE_PATHS),
                include_tests=bool(args.include_tests),
            )

        include_docstrings_as_comments = bool(args.comment_docstrings) and not bool(
            args.include_docstrings
        )
        total_cd, by_lang = compute_comment_density(
            candidates,
            include_docstrings=bool(args.include_docstrings),
            include_docstrings_as_comments=include_docstrings_as_comments,
        )
        denom = total_cd.code_sloc + total_cd.comment_only_lines
        density = (float(total_cd.comment_only_lines) / float(denom)) if denom > 0 else 0.0
        ratio = (
            float(total_cd.comment_only_lines) / float(total_cd.code_sloc)
            if total_cd.code_sloc > 0
            else 0.0
        )

        print()
        print("Comment density (approx.)")
        print(f"- Code SLOC:     {total_cd.code_sloc}")
        print(f"- Comment lines: {total_cd.comment_only_lines} (comment-only lines)")
        print(f"- Density:       {density:.4f} (comments / (comments + code))")
        print(f"- Ratio:         {ratio:.4f} (comments / code)")
        if include_docstrings_as_comments:
            print("- Docstrings:    counted as comments")
        if by_lang:
            print()
            print("Comment density by language:")
            for lang in sorted(by_lang):
                cd = by_lang[lang]
                d_denom = cd.code_sloc + cd.comment_only_lines
                d = (float(cd.comment_only_lines) / float(d_denom)) if d_denom > 0 else 0.0
                print(
                    f"- {lang}: density={d:.4f}, code={cd.code_sloc}, comments={cd.comment_only_lines}"
                )

    if run_dsqd:
        if not candidates:
            candidates = _iter_candidate_files(
                root=root,
                include_exts=include_exts,
                excluded_dir_parts=excluded_dir_parts,
                excluded_paths=set(DEFAULT_EXCLUDE_PATHS),
                include_tests=bool(args.include_tests),
            )

        scope_dirs = [d for d in (args.dsqd_dir or []) if d.strip()]
        if not scope_dirs:
            defaults = ["python-server/app", "node-server/src", "frontend/src"]
            for d in defaults:
                if (root / d).exists():
                    scope_dirs.append(d)

        scope_files = candidates
        if scope_dirs:
            prefixes = [str((root / d).resolve()) for d in scope_dirs]
            scoped: list[Path] = []
            for p in candidates:
                ps = str(p)
                if any(ps.startswith(pref + "/") or ps == pref for pref in prefixes):
                    scoped.append(p)
            scope_files = scoped

        dsq = compute_dsqd(files=scope_files, root=root)
        print()
        print("Design Structure Quality Density (DSQD, approx.)")
        if scope_dirs:
            print(f"- Scope:         {', '.join(scope_dirs)}")
        print(f"- Nodes:         {dsq.nodes} files")
        print(f"- Edges:         {dsq.edges} internal dependencies")
        print(f"- Density:       {dsq.density:.6f} (edges / (n*(n-1)))")
        print(f"- Avg out-degree:{dsq.avg_out_degree:.3f}")
        print(f"- Cycles:        {dsq.cyclic_sccs} SCCs (largest size={dsq.largest_cycle_size})")

    if args.cfd:
        if args.cfd_input is None:
            raise ValueError("--cfd-input is required with --cfd")
        cfd_input = Path(args.cfd_input).resolve()
        dates, stages, rows = _parse_cfd_csv(cfd_input)
        svg = _render_cfd_svg(
            dates=dates,
            stages=stages,
            rows=rows,
            title=str(args.cfd_title),
            width=int(args.cfd_width),
            height=int(args.cfd_height),
        )
        out_path = Path(args.cfd_output).resolve() if args.cfd_output else (PROJECT_ROOT / "docs" / "cfd.svg")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(svg, encoding="utf-8")
        print()
        print("Cumulative Flow Diagram (CFD)")
        print(f"- Input:         {cfd_input.relative_to(PROJECT_ROOT) if cfd_input.is_relative_to(PROJECT_ROOT) else str(cfd_input)}")
        print(f"- Output:        {out_path.relative_to(PROJECT_ROOT) if out_path.is_relative_to(PROJECT_ROOT) else str(out_path)}")
        print(f"- Stages:        {', '.join(stages)}")
        print(f"- Date range:    {dates[0].isoformat()} .. {dates[-1].isoformat()}")

    if run_throughput:
        tp_input_raw = args.tp_input or args.cfd_input
        if tp_input_raw is None:
            raise ValueError("--tp-input is required (or set --cfd-input and omit --tp-input)")
        tp_input = Path(tp_input_raw).resolve()
        dates, stages, rows = _parse_cfd_csv(tp_input)
        done_stage = str(args.tp_stage) if args.tp_stage else stages[-1]

        daily_points = _compute_throughput_daily(
            dates=dates,
            stages=stages,
            rows=rows,
            done_stage=done_stage,
            allow_negative=bool(args.tp_allow_negative),
        )
        points = (
            daily_points
            if args.tp_period == "daily"
            else _compute_throughput_weekly(daily_points)
        )

        report = _render_throughput_markdown(
            title=str(args.tp_title),
            done_stage=done_stage,
            period=str(args.tp_period),
            points=points,
        )

        tp_out = Path(args.tp_output).resolve() if args.tp_output else (PROJECT_ROOT / "docs" / "throughput.md")
        tp_out.parent.mkdir(parents=True, exist_ok=True)
        tp_out.write_text(report, encoding="utf-8")

        print()
        print("Throughput report")
        print(f"- Input:         {tp_input.relative_to(PROJECT_ROOT) if tp_input.is_relative_to(PROJECT_ROOT) else str(tp_input)}")
        print(f"- Output:        {tp_out.relative_to(PROJECT_ROOT) if tp_out.is_relative_to(PROJECT_ROOT) else str(tp_out)}")
        print(f"- Done stage:    {done_stage}")
        print(f"- Period:        {args.tp_period}")

    if run_burndown:
        bd_input_raw = args.bd_input or args.cfd_input
        if bd_input_raw is None:
            raise ValueError("--bd-input is required (or set --cfd-input and omit --bd-input)")
        bd_input = Path(bd_input_raw).resolve()
        dates, stages, rows = _parse_cfd_csv(bd_input)
        done_stage = str(args.bd_done_stage) if args.bd_done_stage else stages[-1]
        done_idx = _stage_index(stages, done_stage)
        remaining = [max(0, int(sum(r) - int(r[done_idx]))) for r in rows]

        svg = _render_burndown_svg(
            dates=dates,
            remaining=remaining,
            title=str(args.bd_title),
            width=int(args.bd_width),
            height=int(args.bd_height),
            show_ideal=not bool(args.bd_no_ideal),
        )
        bd_out = Path(args.bd_output).resolve() if args.bd_output else (PROJECT_ROOT / "docs" / "burndown.svg")
        bd_out.parent.mkdir(parents=True, exist_ok=True)
        bd_out.write_text(svg, encoding="utf-8")

        print()
        print("Sprint burndown")
        print(f"- Input:         {bd_input.relative_to(PROJECT_ROOT) if bd_input.is_relative_to(PROJECT_ROOT) else str(bd_input)}")
        print(f"- Output:        {bd_out.relative_to(PROJECT_ROOT) if bd_out.is_relative_to(PROJECT_ROOT) else str(bd_out)}")
        print(f"- Done stage:    {done_stage}")
        print(f"- Date range:    {dates[0].isoformat()} .. {dates[-1].isoformat()}")

    if run_burnup:
        bu_input_raw = args.bu_input or args.cfd_input
        if bu_input_raw is None:
            raise ValueError("--bu-input is required (or set --cfd-input and omit --bu-input)")
        bu_input = Path(bu_input_raw).resolve()
        dates, stages, rows = _parse_cfd_csv(bu_input)
        done_stage = str(args.bu_done_stage) if args.bu_done_stage else stages[-1]
        done_idx = _stage_index(stages, done_stage)
        done_series = [int(r[done_idx]) for r in rows]
        scope_series = [int(sum(r)) for r in rows]

        svg = _render_burnup_svg(
            dates=dates,
            done=done_series,
            scope=scope_series,
            title=str(args.bu_title),
            width=int(args.bu_width),
            height=int(args.bu_height),
            show_ideal=not bool(args.bu_no_ideal),
            show_scope=not bool(args.bu_no_scope),
        )
        bu_out = Path(args.bu_output).resolve() if args.bu_output else (PROJECT_ROOT / "docs" / "burnup.svg")
        bu_out.parent.mkdir(parents=True, exist_ok=True)
        bu_out.write_text(svg, encoding="utf-8")

        print()
        print("Sprint burnup")
        print(f"- Input:         {bu_input.relative_to(PROJECT_ROOT) if bu_input.is_relative_to(PROJECT_ROOT) else str(bu_input)}")
        print(f"- Output:        {bu_out.relative_to(PROJECT_ROOT) if bu_out.is_relative_to(PROJECT_ROOT) else str(bu_out)}")
        print(f"- Done stage:    {done_stage}")
        print(f"- Date range:    {dates[0].isoformat()} .. {dates[-1].isoformat()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
