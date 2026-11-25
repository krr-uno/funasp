"""
Rewriting of negated body literals.

Single-negation body literals ``not l`` are rewritten into the conditional
literal ``#false : l`` so that later unnesting of intensional functions inside
them can use anonymous projections.
"""

from clingo_funasp import ast
from clingo_funasp.core import Library

from funasp.ast import transform_iterable
from funasp.ast._rewritings.context import RewriteContext


def _rewrite_body_literal(
    library: Library, literal: ast.body.BodyLiteral
) -> None | ast.body.BodyConditionalLiteral:
    """Rewrite a negated body literal into an equivalent conditional literal when needed."""
    if (
        not isinstance(literal, ast.body.BodySimpleLiteral)
        or isinstance(literal.literal, ast.literals.LiteralBoolean)
        or literal.literal.sign != ast.literals.Sign.Single
    ):
        return None

    lit = literal.literal

    # Build #false
    false_lit = ast.literals.LiteralBoolean(library, lit.location, ast.literals.Sign.NoSign, False)

    # Create conditional literal: #false : r(X)
    return ast.body.BodyConditionalLiteral(
        library, lit.location, false_lit, [lit.update(library, sign=ast.literals.Sign.NoSign)]
    )


def rewrite_negated_body_literals(
    context: RewriteContext, statement: ast.statements.Statement
) -> ast.statements.Statement:
    """Rewrite eligible negated body literals inside a single statement."""
    if not isinstance(statement, ast.statements.StatementRule):
        return statement
    new_body = transform_iterable(
        context.lib.library, statement.body, _rewrite_body_literal
    )
    if new_body is None:
        return statement
    return statement.update(context.lib.library, body=new_body)
