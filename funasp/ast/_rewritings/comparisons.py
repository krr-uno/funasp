"""
Rewriting of functional equalities into prefixed predicate literals.

The parser does not touch body occurrences of intensional functions: an
equality ``f(t) = v`` (written by the user or produced by unnesting) stays a
plain comparison. This step rewrites every such equality whose signature is
intensional into the predicate literal ``Ff(t,v)``, completing the encoding.
Comparisons over non-intensional functions are left untouched, so no
restoration step is needed afterwards.
"""

from functools import singledispatchmethod
from typing import AbstractSet, cast

from clingo_funasp import ast
from clingo_funasp.core import Library, Location
from clingo_funasp.symbol import SymbolType

from funasp.ast._rewritings.context import RewriteContext
from funasp.ast._rewritings.types import SymbolSignature
from funasp.util.ast import AST, function_arguments_ast, is_function


class ComparisonTransformer:
    """
    Rewrites intensional functional equalities into prefixed predicate literals.
    """

    def __init__(
        self,
        library: Library,
        intensional_functions: AbstractSet[SymbolSignature],
        prefix: str = "F",
    ) -> None:
        """
        Initialize the transformer with the set of intensional functions.
        """
        self.library = library
        self.intensional_functions = intensional_functions
        self.prefix = prefix

    def _build_intensional_function_to_term(
        self,
        assigned_function: ast.terms.TermFunction | ast.terms.TermSymbolic,
        value: ast.terms.TermOrProjection,
        location: Location,
    ) -> ast.terms.TermFunction:
        """Builds a function term given its assigned function and its value."""
        if isinstance(assigned_function, ast.terms.TermFunction):
            name = assigned_function.name
            pool = [
                ast.terms.ArgumentTuple(self.library, [*t.arguments, value])
                for t in assigned_function.pool
            ]
        elif assigned_function.symbol.type == SymbolType.Function:
            name = assigned_function.symbol.name
            pool = [
                ast.terms.ArgumentTuple(
                    self.library,
                    [
                        ast.terms.TermSymbolic(self.library, location, arg)
                        for arg in assigned_function.symbol.arguments
                    ]
                    + [value],
                )
            ]

        return ast.terms.TermFunction(
            self.library,
            location,
            f"{self.prefix}{name}",
            pool,
        )

    @singledispatchmethod
    def _dispatch(self, node: AST) -> AST | None:
        """
        Visit an AST node and recurse into its children.
        """
        return node.transform(self.library, self._dispatch)

    @_dispatch.register
    def _(self, node: ast.literals.LiteralComparison) -> ast.literals.LiteralSymbolic | None:
        """Rewrite functional equalities in literals into prefixed predicate literals."""
        assert len(node.right) >= 1, "Comparison must have at least one guard."
        if (
            not is_function(node.left)
            or len(node.right) != 1
            or node.right[0].relation != ast.literals.Relation.Equal
        ):
            return None
        name, arguments = function_arguments_ast(self.library, node.left)
        if isinstance(node.left, ast.terms.TermFunction):
            candidate_arities = {len(p.arguments) for p in node.left.pool}
        else:
            candidate_arities = {len(arguments)}
        if not any(
            SymbolSignature(name, arity) in self.intensional_functions
            for arity in candidate_arities
        ):
            return None
        return ast.literals.LiteralSymbolic(
            self.library,
            node.location,
            node.sign,
            self._build_intensional_function_to_term(
                node.left, node.right[0].term, node.location
            ),
        )

    def rewrite(self, node: ast.statements.Statement) -> ast.statements.Statement:
        """Rewrite all intensional functional equalities in a statement."""
        result = self._dispatch(node) or node
        return cast(ast.statements.Statement, result)


def prefix_comparisons(
    context: RewriteContext,
    statement: ast.statements.Statement,
) -> ast.statements.Statement:
    """Rewrite intensional functional equalities in a single statement."""
    transformer = ComparisonTransformer(
        context.lib.library, context.intensional_functions, context.prefix_function
    )
    return transformer.rewrite(statement)
