"""
Collection of intensional function signatures from the prefixed representation.

The ``clingo_funasp`` parser encodes an assignment ``f(t1,...,tn) := v`` as
the atom ``Ff(t1,...,tn,v)``: the function name gets the prefix and the
assigned value is appended as the last argument. Consequently, a prefixed
head atom of arity ``n+1`` declares the intensional function ``f/n``.

Collection must run after ``#some`` and aggregate assignments have been
normalized (see ``rewrite_statements.py``), so the only places where assignments
appear are:

- ``HeadSimpleLiteral`` atoms (``Ff(t,v) :- B.``),
- ``HeadSetAggregate`` element literals (``{ Ff(t,v) } :- B.``),
- ``HeadAggregate`` element literals (``#count{ ...: Ff(t,v): ... }.``).
"""

from clingo_funasp import ast

from funasp.ast import PARSER_PREFIX
from funasp.ast._rewritings.context import RewriteContext
from funasp.ast._rewritings.types import SymbolSignature
from funasp.util.ast import AST


def collect_variables(node: AST) -> set[str]:
    """Collect all variable names that occur in the given AST node."""
    collector = _VariableCollector()
    return collector.collect(node)


class _VariableCollector:
    """
    Class to collect variables from a list of AST statements.

    Usage:
        collector = VariableCollector()
        used_vars = collector.collect(statements)
    """

    def __init__(self) -> None:
        """Initialize the collector state for a new variable traversal."""
        self.used: set[str] = set()

    def collect(self, node: AST) -> set[str]:
        """Collect variable names from the given AST node."""
        self._collect_vars(node)
        return self.used

    def _collect_vars(self, node: AST) -> None:
        """Recursively collect variables from the given AST subtree."""
        if isinstance(node, ast.terms.TermVariable):
            self.used.add(node.name)
            return
        if isinstance(node, ast.terms.TermSymbolic):
            return
        node.visit(self._collect_vars)


def _signatures_from_literal(prefix: str, literal: ast.literals.Literal) -> set[SymbolSignature]:
    """Collect the signature declared by a prefixed head atom, if any."""
    if not isinstance(literal, ast.literals.LiteralSymbolic):
        return set()
    atom = literal.atom
    if not isinstance(atom, ast.terms.TermFunction) or not atom.name.startswith(prefix):
        return set()
    name = atom.name[len(prefix) :]
    return {
        SymbolSignature(name, len(arguments.arguments) - 1) for arguments in atom.pool
    }


def collect_intensional_function_signatures(
    context: RewriteContext, statement: ast.statements.Statement
) -> set[SymbolSignature]:
    """
    Collect the intensional function signatures declared by a statement head.
    """
    if not isinstance(statement, ast.statements.StatementRule):
        return set()
    prefix = PARSER_PREFIX
    head = statement.head
    signatures: set[SymbolSignature] = set()
    if isinstance(head, ast.head.HeadSimpleLiteral):
        signatures |= _signatures_from_literal(prefix, head.literal)
    elif isinstance(head, ast.head.HeadSetAggregate | ast.head.HeadAggregate):
        for element in head.elements:
            signatures |= _signatures_from_literal(prefix, element.literal)
    return signatures
