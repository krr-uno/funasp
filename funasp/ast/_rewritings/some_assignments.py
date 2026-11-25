"""
Rewriting of ``#some`` assignments.

The parser desugars ``f(t) := #some{ v1: c1; ... } :- B.`` into the head
aggregate ``FSf(t) = #sum { v1: NONE: c1; ... } :- B.`` where the ``FS``
prefix marks the ``#some``. This module rewrites it into a choice with the
"someness" semantics::

    { Ff(t,v1): c1; ... } = 1 :- #count{ v1: c1; ... } >= 1, B.

i.e. exactly one value is chosen whenever at least one candidate exists.
The ``FS`` marker is unambiguous: user-written function names cannot start
with an uppercase letter, so ``F`` + name never yields ``FS...``.

This step runs before the prefix renaming pass, so the marker is always the
parser's literal ``FS``.
"""

from typing import Sequence

from clingo_funasp import ast, symbol

from funasp.ast import PARSER_PREFIX, SOME_MARKER
from funasp.ast._rewritings.context import RewriteContext

#: The prefix the parser generates for ``#some`` assignments.
SOME_PREFIX = PARSER_PREFIX + SOME_MARKER


def rewrite_some_assignments(
    context: RewriteContext, statement: ast.statements.Statement
) -> list[ast.statements.Statement]:
    """Rewrite a ``#some`` assignment head into choices with a guard body.

    Returns one statement per pool entry on the left guard, so an unpooled
    term yields a single statement and ``f(a;b) := #some{...}`` yields one
    statement for ``f(a)`` and one for ``f(b)``. Non-``#some`` statements pass
    through unchanged as a one-element list.
    """

    if not isinstance(statement, ast.statements.StatementRule) or not isinstance(
        head := statement.head, ast.head.HeadAggregate
    ):
        return [statement]
    left = head.left
    if (
        left is None
        or not isinstance(left.term, ast.terms.TermFunction)
        or not left.term.name.startswith(SOME_PREFIX)
    ):
        return [statement]
    assert left.relation == ast.literals.Relation.Equal
    assert head.right is None

    name = PARSER_PREFIX + left.term.name[len(SOME_PREFIX) :]
    return [
        _rewrite_some_pool_entry(context, statement, head, name, entry.arguments)
        for entry in left.term.pool
    ]


def _rewrite_some_pool_entry(
    context: RewriteContext,
    statement: ast.statements.StatementRule,
    head: ast.head.HeadAggregate,
    name: str,
    arguments: Sequence[ast.terms.Term | ast.terms.Projection],
) -> ast.statements.Statement:
    """Build the choice statement for a single pool entry of a ``#some`` head."""

    library = context.lib.library

    choice_elements: list[ast.aggregates.SetAggregateElement] = []
    count_elements: list[ast.body.BodyAggregateElement] = []
    for element in head.elements:
        if len(element.tuple) == 1:
            value: ast.terms.Term = element.tuple[0]
        else:
            value = ast.terms.TermTuple(
                library,
                head.location,
                [ast.terms.ArgumentTuple(library, list(element.tuple))],
            )
        atom = ast.terms.TermFunction(
            library,
            head.location,
            name,
            [ast.terms.ArgumentTuple(library, [*arguments, value])],
        )
        literal = ast.literals.LiteralSymbolic(
            library, head.location, ast.literals.Sign.NoSign, atom
        )
        choice_elements.append(
            ast.aggregates.SetAggregateElement(
                library, element.location, literal, list(element.condition)
            )
        )
        count_elements.append(
            ast.body.BodyAggregateElement(
                library, element.location, list(element.tuple), list(element.condition)
            )
        )

    new_head = ast.head.HeadSetAggregate(
        library,
        head.location,
        None,
        choice_elements,
        ast.literals.RightGuard(
            library,
            ast.literals.Relation.Equal,
            ast.terms.TermSymbolic(library, head.location, symbol.Number(library, 1)),
        ),
    )
    count_aggregate = ast.body.BodyAggregate(
        library,
        head.location,
        ast.literals.Sign.NoSign,
        None,
        ast.aggregates.AggregateFunction.Count,
        count_elements,
        ast.literals.RightGuard(
            library,
            ast.literals.Relation.GreaterEqual,
            ast.terms.TermSymbolic(library, head.location, symbol.Number(library, 1)),
        ),
    )
    new_body: list[ast.body.BodyLiteral] = [count_aggregate, *statement.body]
    return statement.update(library, head=new_head, body=new_body)
