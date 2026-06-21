"""Regenerate the committed defunctionalized bootstrap compiler for the running Python version.

The defunctionalization compiler ``DEFUN`` is self-compiled and committed under ``_generated`` as a
self-contained module exposing ``compiled``; the benchmark imports it to measure the compiled compiler
without triggering any in-process compilation. Running this script (or ``co-lambda-regen-compiler``)
regenerates the committed module for the running Python version.

Generation recurses as deep as the DEFUN term itself and overflows the C stack on Python 3.12+; it
therefore runs in a large-stack thread, and the resulting committed module is 3.11-only for the same
reason.
"""

from __future__ import annotations

from pathlib import Path

_GENERATED_DIR = Path(__file__).resolve().parent / "_generated"


def module_basename() -> str:
    """The committed module file stem for the running Python version."""
    from co_lambda._defun_runtime import _python_tag

    return f"_generated_defun_compiler_{_python_tag()}"


def module_dotted_name() -> str:
    """The importable dotted module name for the committed compiler artifact."""
    return f"co_lambda._generated.{module_basename()}"


def generate() -> Path:
    """Self-compile DEFUN and write the committed module for the running Python version."""
    from co_lambda._defun_runtime import run_in_large_stack
    from co_lambda._defunctionalize import defun_compiler_source

    source = run_in_large_stack(defun_compiler_source)
    path = _GENERATED_DIR / f"{module_basename()}.py"
    path.write_text(source)
    return path


def main() -> None:
    """Regenerate the committed bootstrap compiler module for the running Python version."""
    path = generate()
    print(f"wrote {path.name} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
