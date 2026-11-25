"""
Renaming pass for the parser-generated function prefix.

The ``clingo_funasp`` parser desugars assignments at parse time using the
hardcoded prefix ``F`` (and ``FS`` for ``#some`` assignments). This pass
renames those parser-generated names to the prefix configured via
``--prefix-fun`` so that the rest of the pipeline (and model display) can use
a custom prefix.

This pass runs after the pass-1 desugaring and unnesting, so the parser's
aggregate and ``#some`` left-guard heads have already been rewritten into
other shapes. The positions still carrying a parser prefix are:

- ``HeadSimpleLiteral`` atoms (simple and normalized aggregate assignments),
- ``HeadSetAggregate`` element literals (choice and rewritten ``#some``
  assignments),
- ``HeadAggregate`` element literals (assignments inside head aggregates),
- ``StatementShowSignature`` names (``#showf p/n`` becomes ``#show Fp/n+1.``).

Body atoms are never touched: the parser does not prefix body occurrences.
The default prefix ``F`` is safe from collisions because user-written
function names cannot start with an uppercase letter (those are variables).
"""

from clingo_funasp import ast

from funasp.ast import PARSER_PREFIX
from funasp.ast._rewritings.context import RewriteContext


def _rename_term(
    context: RewriteContext, term: ast.terms.TermFunction
) -> ast.terms.TermFunction:
    """Rename a parser-prefixed function term to the configured prefix."""
    assert term.name.startswith(PARSER_PREFIX)
    new_name = context.prefix_function + term.name[len(PARSER_PREFIX) :]
    return term.update(context.lib.library, name=new_name)


def _rename_literal(
    context: RewriteContext, literal: ast.literals.LiteralSymbolic
) -> ast.literals.LiteralSymbolic:
    """Rename the atom of a parser-prefixed symbolic literal."""
    atom = literal.atom
    if not isinstance(atom, ast.terms.TermFunction) or not atom.name.startswith(
        PARSER_PREFIX
    ):
        return literal
    return literal.update(context.lib.library, atom=_rename_term(context, atom))


def _rename_head(
    context: RewriteContext, head: ast.head.HeadLiteral
) -> ast.head.HeadLiteral:
    """Rename parser-prefixed atoms in a rule head."""
    library = context.lib.library
    if isinstance(head, ast.head.HeadSimpleLiteral):
        literal = head.literal
        if not isinstance(literal, ast.literals.LiteralSymbolic):
            return head
        return ast.head.HeadSimpleLiteral(library, _rename_literal(context, literal))
    if isinstance(head, ast.head.HeadSetAggregate):
        elements = [
            (
                element.update(
                    library, literal=_rename_literal(context, element.literal)
                )
                if isinstance(element.literal, ast.literals.LiteralSymbolic)
                else element
            )
            for element in head.elements
        ]
        return head.update(library, elements=elements)
    if isinstance(head, ast.head.HeadAggregate):
        elements = [
            (
                element.update(
                    library, literal=_rename_literal(context, element.literal)
                )
                if isinstance(element.literal, ast.literals.LiteralSymbolic)
                else element
            )
            for element in head.elements
        ]
        return head.update(library, elements=elements)
    return head


def rename_prefixes(
    context: RewriteContext, statement: ast.statements.Statement
) -> ast.statements.Statement:
    """
    Rename parser-generated ``F``/``FS`` prefixes to the configured prefix.

    This is a no-op when the configured prefix is the parser default ``F``.
    """
    if context.prefix_function == PARSER_PREFIX:
        return statement
    library = context.lib.library
    if isinstance(statement, ast.statements.StatementRule):
        return statement.update(library, head=_rename_head(context, statement.head))
    if isinstance(
        statement, ast.statements.StatementShowSignature
    ) and statement.name.startswith(PARSER_PREFIX):
        new_name = context.prefix_function + statement.name[len(PARSER_PREFIX) :]
        return statement.update(library, name=new_name)
    return statement
