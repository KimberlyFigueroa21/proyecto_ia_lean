#!/usr/bin/env python3
"""Extrae (nombre, firma, docstring) de teoremas/lemas de fuentes .lean (Mathlib).

Es una extracción por texto: rápida y suficiente para RAG. No resuelve `open`/`variable`
ni el nombre completo con 100% de exactitud; el rastreo de `namespace` cubre la mayoría.
Uso: python extract_mathlib.py <carpeta Mathlib/> salida.jsonl
"""
import json, re, sys
from pathlib import Path

DECL = re.compile(r"^(?:@\[[^\]]*\]\s*)?(?:protected\s+|private\s+|nonrec\s+)*(theorem|lemma)\s+([^\s:({\[]+)", re.M)
NS_OPEN = re.compile(r"^namespace\s+(\S+)", re.M)
NS_END = re.compile(r"^end\s+(\S+)", re.M)


def signature(text: str, start: int) -> str:
    """Desde el inicio de la declaración hasta ':=' / 'where' / '|' de nivel superior."""
    chunk = text[start:start + 1500]
    depth, i = 0, 0
    while i < len(chunk):
        ch = chunk[i]
        if ch in "([{⟨": depth += 1
        elif ch in ")]}⟩": depth -= 1
        elif depth <= 0 and chunk.startswith(":=", i):
            break
        elif depth <= 0 and chunk.startswith("\n\n", i):
            break
        i += 1
    return re.sub(r"\s+", " ", chunk[:i]).strip()


def extract_file(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    events = sorted([(m.start(), "open", m.group(1)) for m in NS_OPEN.finditer(text)] +
                    [(m.start(), "end", m.group(1)) for m in NS_END.finditer(text)] +
                    [(m.start(), "decl", m) for m in DECL.finditer(text)], key=lambda e: e[0])
    stack = []
    for pos, kind, val in events:
        if kind == "open":
            stack.append(val)
        elif kind == "end":
            if stack and stack[-1] == val:
                stack.pop()
        else:
            m = val
            name = m.group(2)
            full = ".".join(stack + [name]) if stack and not name.startswith("_root_") else name.replace("_root_.", "")
            before = text[:pos].rstrip()
            doc = ""
            if before.endswith("-/"):                      # docstring inmediatamente anterior
                s0 = before.rfind("/--")
                if s0 != -1 and "-/" not in before[s0 + 3:-2]:
                    doc = re.sub(r"\s+", " ", before[s0 + 3:-2]).strip()
            yield {"name": full, "signature": signature(text, m.start()), "docstring": doc, "file": str(path)}


def main(root, out):
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for p in sorted(Path(root).rglob("*.lean")):
            for rec in extract_file(p):
                f.write(json.dumps(rec, ensure_ascii=False) + "\n"); n += 1
    print(f"{n} declaraciones -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
