"""The edit-distance code listing is generated from the HOAS terms, so it is checked for currency here.

The committed LaTeX the paper inputs must be exactly what the generator produces (so a change to the
source terms cannot leave a stale listing), and the listing must read from the source: the curry-decorated
helpers' parameter names must survive rather than appear as curry's placeholder, and ``ed`` must be present.
"""

from __future__ import annotations

from co_lambda_examples._editdistance_code import _OUTPUT, code_listing


def test_committed_code_listing_is_current() -> None:
    assert _OUTPUT.read_text() == code_listing()


def test_listing_reads_from_the_source_terms() -> None:
    listing = code_listing()
    assert "\\mathtt{ed} =" in listing  # the edit-distance term is listed
    assert "\\begin{dmath*}" in listing  # rendered as breqn auto-breaking math
    assert "\\mathit{bit}" in listing  # a curry helper's parameter name survived
    assert "bound" not in listing  # curry's placeholder name never leaks in
