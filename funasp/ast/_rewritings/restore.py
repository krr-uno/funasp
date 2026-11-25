"""
Restoration of non-intensional prefixed function literals.

The comparisons step prefixes a pooled equality ``f(a;b,c) = V`` whenever any
of its candidate arities is intensional. After clingo's rewriting unpools the
statements, the entries whose arity is *not* intensional must be restored to
plain comparisons (e.g. ``Ff(b,c,V)`` back to ``f(b,c) = V`` when only ``f/1``
is intensional).
"""

from functools import singledispatchmethod
from typing import Any

from clingo_funasp import ast
from clingo_funasp.symbol import SymbolType

from funasp.ast._rewritings.context import RewriteContext
from funasp.ast._rewritings.types import SymbolSignature
from funasp.util.ast import function_arguments_ast


def _restore_literal(
    context: RewriteContext,
    node: ast.literals.LiteralSymbolic,
) -> ast.literals.LiteralComparison | None:
    """Restore prefixed function literals into equalities for non-intensional signatures."""
    atom = node.atom
    if isinstance(atom, ast.terms.TermFunction):
        prefixed_name = atom.name
    elif (
        isinstance(atom, ast.terms.TermSymbolic)
        and atom.symbol.type == SymbolType.Function
    ):
        prefixed_name = atom.symbol.name
    else:
        # TODO: Need to add test for this
        return None  # pragma: no cover

    prefix = context.prefix_function
    if not prefixed_name.startswith(prefix):
        return None

    base_name, arguments = function_arguments_ast(context.lib.library, atom)
    base_name = base_name[len(prefix) :]
    assert base_name is not None

    arguments = list(arguments)
    assert len(arguments) >= 1

    original_arity = len(arguments) - 1
    if SymbolSignature(base_name, original_arity) in context.intensional_functions:
        return None

    left = ast.terms.TermFunction(
        context.lib.library,
        node.location,
        base_name,
        [ast.terms.ArgumentTuple(context.lib.library, arguments[:-1])],
    )
    right_arg = (
        arguments[-1]
        if isinstance(arguments[-1], ast.terms.Term)
        else ast.terms.TermVariable(
            context.lib.library, node.location, "_", anonymous=True
        )
    )
    right = ast.literals.RightGuard(
        context.lib.library,
        ast.literals.Relation.Equal,
        right_arg,
    )
    return ast.literals.LiteralComparison(
        context.lib.library,
        node.location,
        node.sign,
        left,
        [right],
    )


class _RestoreNonIntensionalFunctionsTransformer:
    """Restore non-intensional prefixed literals throughout a statement AST."""

    def __init__(self, context: RewriteContext) -> None:
        """Initialize the transformer with the rewrite context."""
        self.context = context
        self.library = context.lib.library

    @singledispatchmethod
    def dispatch(self, node: Any) -> Any | None:  # pragma: no cover
        """Dispatch restoration recursively across AST nodes."""
        return node.transform(self.library, self.dispatch)

    @dispatch.register
    def _(
        self, node: ast.literals.LiteralSymbolic
    ) -> ast.literals.LiteralComparison | None:
        """Restore a prefixed literal when it maps to a non-intensional function."""
        return _restore_literal(self.context, node)

    @dispatch.register
    def _(
        self, node: ast.statements.StatementRule
    ) -> ast.statements.StatementRule | None:
        """Restore prefixed literals in both rule heads and bodies."""
        rewritten_head = self.dispatch(node.head)
        if rewritten_head is None:
            new_head = node.head
            head_changed = False
        else:
            assert isinstance(
                rewritten_head, (ast.head.HeadLiteral, ast.head.HeadDisjunction)
            )
            new_head = rewritten_head
            head_changed = True

        new_body: list[ast.body.BodyLiteral] = []
        changed = head_changed
        for literal in node.body:
            rewritten = self.dispatch(literal)
            if rewritten is None:
                new_body.append(literal)
            else:
                assert isinstance(rewritten, ast.body.BodyLiteral)
                new_body.append(rewritten)
                changed = True

        if not changed:
            return None
        return ast.statements.StatementRule(
            self.library, node.location, new_head, new_body
        )

    def rewrite(self, statement: ast.statements.Statement) -> ast.statements.Statement:
        """Apply restoration to one clingo statement."""
        rewritten = self.dispatch(statement)
        if rewritten is None:
            return statement
        assert isinstance(rewritten, ast.statements.Statement)
        return rewritten


def restore_non_intensional_functions(
    context: RewriteContext,
    statement: ast.statements.Statement,
) -> ast.statements.Statement:
    """Restore non-intensional prefixed function literals in a statement."""
    return _RestoreNonIntensionalFunctionsTransformer(context).rewrite(statement)
