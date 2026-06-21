# co_lambda

[![CI](https://github.com/Atry/co-lambda/actions/workflows/ci.yml/badge.svg)](https://github.com/Atry/co-lambda/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/co-lambda)](https://pypi.org/project/co-lambda/)
[![Python versions](https://img.shields.io/pypi/pyversions/co-lambda)](https://pypi.org/project/co-lambda/)
![License: MIT](https://img.shields.io/pypi/l/co-lambda)

A pure lambda-calculus interpreter and compiler, realizing the semantics of the
paper `paper/co-lambda.tex` and depending on `fixpoints`.

```sh
pip install co-lambda
```

You write ordinary pure lambda terms, and the interpreter gives them powers a
pure language normally lacks:

- Cyclic and infinite data structures, built and transformed directly, with no
  `letrec`, no added recursion construct, and no mutable references.
- Automatic memoization and dynamic programming: repeated subproblems are shared
  for you, with no cache written by hand.
- A diverging loop is detected and returns a meaningless value in finite time
  instead of hanging.

The companion compiler turns a term into a standalone Python module, so a program
written once as a lambda term can also run as compiled code.

No parser is provided: terms are built directly in Python, with a small prelude
of the usual combinators, Church numerals, and Scott-encoded lists.
