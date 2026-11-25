"""
Term-level unnesting of intensional functions inside literals.

A nested intensional function term is replaced by a fresh ``FUN`` variable and
an equality comparison linking the term to the variable is recorded, to be
placed by the statement-level driver (``funasp.ast._rewritings.unnesting``).
"""

from functools import singledispatchmethod
from typing import List, Set, TypeVar

from clingo_funasp import ast, symbol
from clingo_funasp.core import Library, Location
from clingo_funasp.symbol import Symbol

from funasp.ast._rewritings.types import SymbolSignature
from funasp.util.ast import (
    FreshVariableGenerator,
    TermTransformer,
    make_equation,
    replace_term,
)
from funasp.util.iterables import map_none

AST_T = TypeVar(
    "AST_T",
    ast.terms.ArgumentTuple,
    ast.body.BodyAggregate,
    ast.body.BodyAggregateElement,
    ast.body.BodyConditionalLiteral,
    ast.body.BodySetAggregate,
    ast.body.BodySimpleLiteral,
    ast.head.HeadAggregate,
    ast.head.HeadAggregateElement,
    ast.head.HeadConditionalLiteral,
    ast.head.HeadDisjunction,
    ast.head.HeadSetAggregate,
    ast.head.HeadSimpleLiteral,
    ast.literals.LeftGuard,
    ast.literals.LiteralBoolean,
    ast.literals.LiteralComparison,
    ast.literals.LiteralSymbolic,
    ast.statements.OptimizeElement,
    ast.statements.OptimizeTuple,
    ast.literals.RightGuard,
    ast.aggregates.SetAggregateElement,
    ast.terms.TermAbsolute,
    ast.terms.TermBinaryOperation,
    ast.terms.TermFunction,
    ast.terms.TermSymbolic,
    ast.terms.TermTuple,
    ast.terms.TermUnaryOperation,
    ast.terms.TermVariable,
)


def unnest_functions[
    T: (ast.literals.LiteralBoolean | ast.literals.LiteralComparison | ast.literals.LiteralSymbolic)
](
    lib: Library,
    node: T,
    intensional_functions: Set[SymbolSignature],
    variable_generator: FreshVariableGenerator,
    *,
    outer: bool = True,
    sign: ast.literals.Sign | None = None,
    unnest_left_guard_equality: bool = False,
    allowed_in_negated_literals: bool = True,
) -> tuple[T | None, List[ast.literals.LiteralComparison]]:
    """
    Unnest intensional functions in a given rule and return the list of generated comparisons.
    """
    transformer = UnnestFunctionsInLiteralsTransformer(
        lib,
        intensional_functions,
        variable_generator,
        unnest_left_guard_equality,
        allowed_in_negated_literals,
    )

    new_node = transformer.unnest(
        node,
        outer,
        sign,
    )
    return new_node, transformer.unnested_functions


class UnnestFunctionsInLiteralsTransformer:
    """
    Recursively unnest intensional functions in Clingo AST.
    """

    def __init__(
        self,
        lib: Library,
        intensional_functions: Set[SymbolSignature],
        variable_generator: FreshVariableGenerator,
        unnest_left_guard_equality: bool = False,
        allowed_in_negated_literals: bool = True,
    ):
        """Initialize the literal unnesting transformer and its state."""
        self.lib = lib
        self.intensional_functions = intensional_functions
        self.var_gen = variable_generator
        self.unnested_functions: List[ast.literals.LiteralComparison] = []
        self.unnest_left_guard_equality = unnest_left_guard_equality
        self.allowed_in_negated_literals = allowed_in_negated_literals

    def pop_all_unnested_functions(self) -> List[ast.literals.LiteralComparison]:
        """Return and clear the comparisons generated during unnesting."""
        unnested = self.unnested_functions
        self.unnested_functions = []
        return unnested

    def _is_intensional(self, name: str, arity: int) -> bool:
        """Return whether the given function signature is intensional."""
        return SymbolSignature(name, arity) in self.intensional_functions

    def _is_intensional_term(self, term: ast.terms.TermOrProjection | Symbol) -> bool:
        """Return whether the given term is an intensional function term."""
        if isinstance(term, ast.terms.TermFunction):
            return any(
                self._is_intensional(term.name, len(p.arguments)) for p in term.pool
            )
        if isinstance(term, ast.terms.TermSymbolic):
            term = term.symbol
        if isinstance(term, symbol.Symbol) and term.type == symbol.SymbolType.Function:
            return self._is_intensional(str(term.name), len(term.arguments))
        return False

    @singledispatchmethod
    def unnest(
        self,
        node: AST_T,
        outer: bool = True,
        sign: ast.literals.Sign | None = None,
    ) -> AST_T | None:
        """
        Unnest intensional functions in the given AST node.
        It returns a new node if changes were made, or None otherwise.
        """
        return node.transform(self.lib, self.unnest, outer, sign)

    @unnest.register
    def _(
        self,
        node: ast.literals.LiteralSymbolic,
        outer: bool = True,
        sign: ast.literals.Sign | None = None,
    ) -> ast.literals.LiteralSymbolic | None:
        """Unnest intensional functions inside a symbolic literal."""
        return node.transform(self.lib, self.unnest, outer=True, sign=node.sign)

    def _flip_equality(
        self,
        node: ast.literals.LiteralComparison,
    ) -> ast.literals.LiteralComparison:
        """
        Flip sides of an equality comparison.
        """
        left = node.right[0].term
        right = [node.right[0].update(self.lib, term=node.left)]
        return node.update(self.lib, left=left, right=right)

    @unnest.register
    def _(
        self,
        node: ast.literals.LiteralComparison,
        outer: bool = True,
        sign: ast.literals.Sign | None = None,
    ) -> ast.literals.LiteralComparison | None:
        """
        Normalize comparisons to have intensional functions on the left side of equality only
        """
        outer_left = False
        is_new_node = False
        # Special case: equality with a single right guard
        if len(node.right) == 1 and node.right[0].relation == ast.literals.Relation.Equal:
            # Flip if intensional only on right-hand side
            if not self._is_intensional_term(node.left) and self._is_intensional_term(
                node.right[0].term
            ):
                node = self._flip_equality(node)
                is_new_node = True

            if not self.unnest_left_guard_equality:
                outer_left = True

        left = self.unnest(node.left, outer_left, sign=sign)
        right = map_none(
            lambda rg: rg.transform(self.lib, self.unnest, outer=False, sign=sign),
            node.right,
        )
        update = {}
        if left is not None:
            update["left"] = left
        if right is not None:
            update["right"] = right
        if not update:
            return node if is_new_node else None
        return node.update(self.lib, **update)

    @unnest.register
    def _(
        self,
        node: ast.terms.TermOrProjection,
        outer: bool = True,
        sign: ast.literals.Sign | None = None,
    ) -> ast.terms.TermOrProjection | None:
        """Unnest intensional function terms and replace inner calls with fresh variables."""

        def _replace_term_condition(
            term: ast.terms.TermOrProjection | Symbol, depth: int, /
        ) -> bool:
            """Return whether the term should be replaced."""
            if outer and depth <= 0:
                return False
            if self._is_intensional_term(term):
                if not self.allowed_in_negated_literals and sign == ast.literals.Sign.Single:
                    raise RuntimeError(
                        f"Intensional functions are not allowed in negated literals in conditions of aggregates and conditional literals. Found '{str(node)}' at {node.location}."
                    )
                return True
            return False

        return replace_term(
            self.lib,
            node,
            _replace_term_condition,
            self.unnested_functions.append,
            self.var_gen,
            sign or ast.literals.Sign.NoSign,
        )

    @unnest.register
    def _(
        self, node: ast.statements.OptimizeTuple, outer: bool = True, sign: ast.literals.Sign | None = None
    ) -> ast.statements.OptimizeTuple | None:
        """Unnest intensional functions that occur inside optimize tuples."""
        return node.transform(self.lib, self.unnest, outer=False, sign=sign)
