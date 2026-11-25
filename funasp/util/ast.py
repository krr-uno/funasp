import sys
from functools import singledispatchmethod
from typing import (
    AbstractSet,
    Any,
    Callable,
    Concatenate,
    NamedTuple,
    Optional,
    Sequence,
    TypeIs,
    TypeVar,
)

from clingo_funasp import ast
from clingo_funasp.core import Library, Location, Position
from clingo_funasp.symbol import Symbol, SymbolType

AST = (
    ast.statements.Statement
    | ast.terms.Term
    | ast.literals.Literal
    | ast.terms.ArgumentTuple
    | ast.body.BodyLiteral
    | ast.body.BodyAggregateElement
    | ast.statements.Edge
    | ast.head.HeadAggregateElement
    | ast.head.HeadLiteral
    | ast.literals.LeftGuard
    | ast.statements.OptimizeElement
    | ast.statements.OptimizeTuple
    | ast.statements.ProgramPart
    | ast.terms.Projection
    | ast.literals.RightGuard
    | ast.aggregates.SetAggregateElement
    | ast.statements.TheoryAtomDefinition
    | ast.theory.TheoryAtomElement
    | ast.statements.TheoryGuardDefinition
    | ast.statements.TheoryOperatorDefinition
    | ast.theory.TheoryRightGuard
    | ast.statements.TheoryTermDefinition
    | ast.theory.TheoryTermFunction
    | ast.theory.TheoryTermSymbolic
    | ast.theory.TheoryTermTuple
    | ast.theory.TheoryTermUnparsed
    | ast.theory.TheoryTermVariable
    | ast.theory.UnparsedElement
)


# AST_T = TypeVar(
#     "AST_T",
#     ast.terms.ArgumentTuple,
#     ast.body.BodyAggregate,
#     ast.body.BodyAggregateElement,
#     ast.body.BodyConditionalLiteral,
#     ast.body.BodySetAggregate,
#     ast.body.BodySimpleLiteral,
#     ast.body.BodyTheoryAtom,
#     ast.statements.Edge,
#     ast.head.HeadAggregate,
#     ast.head.HeadAggregateElement,
#     ast.head.HeadConditionalLiteral,
#     ast.head.HeadDisjunction,
#     ast.head.HeadSetAggregate,
#     ast.head.HeadSimpleLiteral,
#     ast.head.HeadTheoryAtom,
#     ast.literals.LeftGuard,
#     ast.literals.LiteralBoolean,
#     ast.literals.LiteralComparison,
#     ast.literals.LiteralSymbolic,
#     ast.statements.OptimizeElement,
#     ast.statements.OptimizeTuple,
#     ast.statements.ProgramPart,
#     ast.terms.Projection,
#     ast.literals.RightGuard,
#     ast.aggregates.SetAggregateElement,
#     ast.statements.StatementComment,
#     ast.statements.StatementConst,
#     ast.statements.StatementDefined,
#     ast.statements.StatementEdge,
#     ast.statements.StatementExternal,
#     ast.statements.StatementHeuristic,
#     ast.statements.StatementInclude,
#     ast.statements.StatementOptimize,
#     ast.statements.StatementParts,
#     ast.statements.StatementProgram,
#     ast.statements.StatementProject,
#     ast.statements.StatementProjectSignature,
#     ast.statements.StatementRule,
#     ast.statements.StatementScript,
#     ast.statements.StatementShow,
#     ast.statements.StatementShowNothing,
#     ast.statements.StatementShowSignature,
#     ast.statements.StatementTheory,
#     ast.statements.StatementWeakConstraint,
#     ast.terms.TermAbsolute,
#     ast.terms.TermBinaryOperation,
#     ast.terms.TermFunction,
#     ast.terms.TermSymbolic,
#     ast.terms.TermTuple,
#     ast.terms.TermUnaryOperation,
#     ast.terms.TermVariable,
#     ast.statements.TheoryAtomDefinition,
#     ast.theory.TheoryAtomElement,
#     ast.statements.TheoryGuardDefinition,
#     ast.statements.TheoryOperatorDefinition,
#     ast.theory.TheoryRightGuard,
#     ast.statements.TheoryTermDefinition,
#     ast.theory.TheoryTermFunction,
#     ast.theory.TheoryTermSymbolic,
#     ast.theory.TheoryTermTuple,
#     ast.theory.TheoryTermUnparsed,
#     ast.theory.TheoryTermVariable,
#     ast.theory.UnparsedElement,
# )

FunctionLikeAST = ast.terms.TermFunction | ast.terms.TermSymbolic | ast.terms.TermTuple | Symbol


class SyntacticError(NamedTuple):
    """
    Represents a syntactic error in the AST.

    Attributes:
        location: The location in the source code where the error occurred.
        message (str): The error message.
        information (any): Additional information about the error.
    """

    location: Location
    message: str
    information: Optional[Any] = None

    def __str__(self) -> str:  # pragma: no cover
        """Return the clingo-style string representation of this syntax error."""
        return f"{self.location}: error: syntax error, {self.message}"


# class HeadBodyVisitor:

#     def __init__(self, library: Library):
#         self.lib = library

#     @singledispatchmethod
#     def _dispatch(self, expr: AST) -> None:
#         """
#         Order bodies of statements.
#         """
#         expr.visit(self.lib, self._dispatch)

#     @_dispatch.register
#     def _(self, node: ast.statements.StatementRule, *args: Any, **kwargs: Any) -> None:
#         """
#         Visit the Rule node, setting the 'head' flag accordingly for children.

#         Parameters
#         ----------
#         node : AST
#             The Rule node.

#         Returns
#         -------
#         AST
#             The (potentially transformed) Rule node.
#         """
#         kwargs["head"] = True
#         node.head.visit(self._lib, self._dispatch)
#         kwargs["head"] = False
#         for element in node.body:
#             element.visit(self._lib, self._dispatch)


class SyntacticCheckVisitor:
    """
    A visitor that checks for syntactic errors in the AST.

    This visitor does not perform any transformations but can be used to
    traverse the AST and check for specific syntactic conditions.
    """

    def __init__(self, invalid_ASTTypes: AbstractSet[type[AST]]) -> None:
        """
        Initializes the SyntacticCheckVisitor.

        Args:
            invalid_ASTTypes (set[ASTType]): A set of AST types that are considered invalid.
        """
        self.invalid_ASTTypes = invalid_ASTTypes
        self.errors: list[SyntacticError] = []

    def visit(self, node: AST, *args: Any, **kwargs: Any) -> None:
        """
        Visit the given AST node and check for invalid AST types.

        Parameters
        ----------
        node : AST
            The AST node to visit.
        """
        if type(node) in self.invalid_ASTTypes:
            assert hasattr(node, "location"), f"Node {node} has no location"
            self.errors.append(
                SyntacticError(node.location, f"unexpected {node}", type(node))
            )
        else:
            node.visit(self, args, kwargs)

    def __call__(self, node: AST, *args: Any, **kwargs: Any) -> None:
        """Visit the given node when the visitor is used as a callable."""
        self.visit(node, *args, **kwargs)


def create_literal(
    library: Library,
    atom: ast.terms.Term,
    sign: ast.literals.Sign = ast.literals.Sign.NoSign,
) -> ast.literals.Literal:
    """Create a symbolic literal from the given term."""
    if hasattr(atom, "location"):
        location = atom.location
    else:  # pragma: no cover
        position = Position(library, "<aux>", 0, 0)
        location = Location(position, position)
    return ast.literals.LiteralSymbolic(library, location, sign, atom)


# def create_head_literal(
#     library: Library,
#     atom: ast.terms.Term,
#     sign: ast.literals.Sign = ast.literals.Sign.NoSign,
# ) -> HeadSimpleLiteral:
#     """
#     Create a head literal from a term AST.

#     Args:
#         library (Library): The library to use for creating the literal.
#         atom (ast.terms.Term): The term AST to create the literal from.
#         sign (ast.literals.Sign): The sign of the literal.

#     Returns:
#         HeadSimpleLiteral: The created head literal.
#     """
#     return ast.head.HeadSimpleLiteral(library, create_literal(library, atom, sign))


def create_body_literal(
    library: Library,
    atom: ast.terms.Term,
    sign: ast.literals.Sign = ast.literals.Sign.NoSign,
) -> ast.body.BodySimpleLiteral:
    """
    Create a body literal from a term AST.

    Args:
        library (Library): The library to use for creating the literal.
        atom (ast.terms.Term): The term AST to create the literal from.
        sign (ast.literals.Sign): The sign of the literal.

    Returns:
        BodySimpleLiteral: The created body literal.
    """
    return ast.body.BodySimpleLiteral(library, create_literal(library, atom, sign))


def is_function(node: AST) -> TypeIs[ast.terms.TermFunction | ast.terms.TermSymbolic]:
    """Return whether the given AST node represents a function term."""
    return isinstance(node, ast.terms.TermFunction) or (
        isinstance(node, ast.terms.TermSymbolic) and node.symbol.type == SymbolType.Function
    )


def function_arguments(
    node: FunctionLikeAST,
) -> tuple[str, Sequence[ast.terms.TermOrProjection] | Sequence[Symbol]]:
    """Return the function name and positional arguments for a function-like node."""
    if isinstance(node, ast.terms.TermTuple):
        name = ""
        assert len(node.pool) == 1 and isinstance(
            node.pool[0], ast.terms.ArgumentTuple
        ), f"Terms must be unpooled {node}"
        arguments = node.pool[0].arguments
    elif isinstance(node, ast.terms.TermFunction):
        name = node.name
        assert len(node.pool) == 1, f"Terms must be unpooled {node}"
        arguments = node.pool[0].arguments
    else:
        if isinstance(node, ast.terms.TermSymbolic):
            node = node.symbol
        if node.type == SymbolType.Tuple:  # pragma: no cover
            name = ""
        else:
            assert (
                node.type == SymbolType.Function
            ), f"Expected a symbol function, got {node}: {node.type}"
            name = node.name
        arguments = node.arguments
    return name, arguments


def function_arguments_ast(
    library: Library,
    node: ast.terms.TermFunction | ast.terms.TermSymbolic,
) -> tuple[str, Sequence[ast.terms.TermOrProjection]]:
    """Return function arguments as AST terms for the given function-like node."""
    if isinstance(node, ast.terms.TermFunction) and len(node.pool) > 1:
        # Preserve pooled alternatives as one tuple argument: f(1;a,b) -> f((1;a,b)).
        return node.name, [ast.terms.TermTuple(library, node.location, list(node.pool))]

    name, arguments = function_arguments(node)
    new_arguments: list[ast.terms.TermOrProjection] = []
    for a in arguments:
        if isinstance(a, Symbol):
            new_arguments.append(ast.terms.TermSymbolic(library, node.location, a))
        else:
            new_arguments.append(a)

    return name, new_arguments

    # if arguments and isinstance(arguments[0], ast.terms.Term):
    #     return name, cast(Sequence[ast.terms.Term], arguments)
    # return name, [
    #     ast.terms.TermSymbolic(library, node.location, cast(Symbol, a)) for a in arguments
    # ]


class FreshVariableGenerator:
    """
    Class to generate fresh variables given a set of already-used names.

    Usage:
        gen = FreshVariableGenerator(used_vars)
        v1 = gen.fresh_variable(lib, loc, "X")
    """

    def __init__(self, used: set[str] | None = None):
        """Initialize the generator with the set of already-used variable names."""
        self.used: set[str] = set(used) if used else set()

    def fresh_variable(
        self, lib: Library, location: Location, name: str = "V"
    ) -> ast.terms.TermVariable:
        """Create a fresh variable name that does not clash with previously used names."""
        if name not in self.used:
            self.used.add(name)
            return ast.terms.TermVariable(lib, location, name, False)

        for i in range(2, sys.maxsize):
            candidate = f"{name}{i}"
            if candidate not in self.used:
                self.used.add(candidate)
                return ast.terms.TermVariable(lib, location, candidate, False)

        assert False, "This will never happen, but makes mypy happy"  # pragma: no cover


class ParsingException(Exception):
    """
    Exception raised when parsing fails.
    """

    def __init__(self, errors: list[SyntacticError]) -> None:
        """Initialize the exception with the collected syntactic errors."""
        self.errors = errors
        messages = "\n".join(str(error) for error in errors)
        super().__init__(f"Parsing failed with {len(errors)} error(s):\n{messages}")


TERM_OR_ARGTUPLE_T = TypeVar(
    "TERM_OR_ARGTUPLE_T",
    ast.terms.TermOrProjection,
    ast.terms.ArgumentTuple,
)


class TermTransformer[T2: ast.terms.TermOrProjection, **P]:

    def __init__(
        self,
        library: Library,
        transform_func: Callable[
            Concatenate[
                ast.terms.TermOrProjection | Symbol,
                int,
                Location,
                Callable[
                    Concatenate[ast.terms.TermOrProjection, int, P],
                    ast.terms.TermOrProjection | None,
                ],
                P,
            ],
            T2 | None,
        ],
    ):
        """
        Transform a term AST node using the provided transformation function. If a Symbol is replaced by a Term, it will be wrapped in a TermSymbolic node and the tree will be accordingly transformed.

        Args:
            library (Library): The library to use for creating new AST nodes.
            term (ast.terms.Term): The term AST node to transform.
            transform_func (callable): A function that takes a term, integer representing the depth of recursion and a recursive function, and returns a transformed term. The function may have additional parameters, which will be passed through to the recursive function. The transform_func should return None if no transformation is needed, or a new term if a transformation is applied. If a transformation happens, the transformer will not recurse into the children of the term, as it is assumed that the transform_func has already handled them. The recursive function passed to transform_func can be used to apply the transformation to child nodes.

        The resulting object is callable and can be used to transform a term AST node by calling it with the term and any additional parameters required by the transform_func.
        """
        self.library = library
        self.transform_func = transform_func

    def apply_to_symbol(
        self, symbol: Symbol, location: Location, depth: int, *args: Any, **kwargs: Any
    ) -> T2 | ast.terms.TermFunction | None:
        """
        Apply the transformation to a Symbol node.
        """
        transformed = self.transform_func(
            symbol, depth, location, self._apply_recursive, *args, **kwargs
        )
        if transformed is not None or symbol.type != SymbolType.Function:
            return transformed
        return self._transform_symbol_arguments(
            symbol, location, depth + 1, *args, **kwargs
        )

    def _transform_symbol_arguments(
        self,
        symbol: Symbol,
        location: Location,
        child_depth: int,
        *args: Any,
        **kwargs: Any,
    ) -> ast.terms.TermFunction | None:
        """
        Recurse into a function symbol's arguments at ``child_depth`` and rebuild
        it as a ``TermFunction`` if any argument was transformed, otherwise return
        ``None``. The rebuilt node carries the (possibly) transformed arguments so
        that callers see the substitutions rather than the original symbol.
        """
        all_none = True
        new_arguments: list[ast.terms.TermOrProjection | Symbol | None] = []
        for arg in symbol.arguments:
            transformed_arg = self.apply_to_symbol(
                arg, location, child_depth, *args, **kwargs
            )
            new_arguments.append(transformed_arg)
            if transformed_arg is not None:
                all_none = False
        if all_none:
            return None
        new_arguments2: list[ast.terms.TermOrProjection] = []
        for new, old in zip(new_arguments, symbol.arguments):
            new = new or old
            if isinstance(new, Symbol):
                new = ast.terms.TermSymbolic(self.library, location, new)
            new_arguments2.append(new)
        arguments_tuple = ast.terms.ArgumentTuple(self.library, new_arguments2)
        return ast.terms.TermFunction(self.library, location, symbol.name, [arguments_tuple])

    @singledispatchmethod
    def _apply(
        self,
        term: TERM_OR_ARGTUPLE_T,
        depth: int,
        *args: Any,
        **kwargs: Any,
    ) -> TERM_OR_ARGTUPLE_T | None:
        """
        Apply the transformation to a term or argument tuple node.
        """
        assert False, f"Unhandled term type {type(term)}"  # pragma: no cover

    @_apply.register(ast.terms.TermOrProjection)
    def _(
        self, term: ast.terms.TermOrProjection, depth: int, *args: Any, **kwargs: Any
    ) -> ast.terms.TermOrProjection | None:
        if isinstance(term, ast.terms.TermSymbolic):
            return self.apply_to_symbol(
                term.symbol, term.location, depth, *args, **kwargs
            )
        new_term = self.transform_func(
            term, depth, term.location, self._apply_recursive, *args, **kwargs
        )
        if new_term is not None:
            return new_term

        return term.transform(self.library, self._apply, depth + 1, *args, **kwargs)

    @_apply.register(ast.terms.ArgumentTuple)
    def _(
        self, term: ast.terms.ArgumentTuple, depth: int, *args: Any, **kwargs: Any
    ) -> ast.terms.ArgumentTuple | None:
        return term.transform(self.library, self._apply, depth, *args, **kwargs)

    def __call__(
        self,
        term: ast.terms.TermOrProjection | ast.terms.ArgumentTuple,
        depth: int = 0,
        *args: Any,
        **kwargs: Any,
    ) -> T2 | None:
        """Transform the given term AST node using the provided transformation function."""
        return self._apply(term, depth, *args, **kwargs)

    def _apply_recursive(
        self, term: ast.terms.TermOrProjection, depth: int, /, *args: Any, **kwargs: Any
    ) -> ast.terms.TermOrProjection | None:
        """Recursively transform the given term AST node using the provided transformation function."""
        if isinstance(term, ast.terms.TermSymbolic):
            if term.symbol.type != SymbolType.Function:
                return None
            return self._transform_symbol_arguments(
                term.symbol, term.location, depth, *args, **kwargs
            )
        return term.transform(self.library, self._apply, depth, *args, **kwargs)


def make_equation(
    library: Library,
    loc: Location,
    left: ast.terms.Term,
    right: ast.terms.Term,
    sign: ast.literals.Sign | None = None,
) -> ast.literals.LiteralComparison:
    """Build an equality comparison linking an unnested function to a fresh variable."""
    return ast.literals.LiteralComparison(
        library,
        loc,
        ast.literals.Sign.Double if sign == ast.literals.Sign.Double else ast.literals.Sign.NoSign,
        left,
        [ast.literals.RightGuard(library, ast.literals.Relation.Equal, right)],
    )


class TermReplacer[**P]:

    def __init__(
        self,
        library: Library,
        condition: Callable[Concatenate[ast.terms.Term | Symbol, int, P], bool],
        callback: Callable[[ast.literals.LiteralComparison], None],
        variable_generator: FreshVariableGenerator,
        sign: ast.literals.Sign = ast.literals.Sign.NoSign,
        *args: P.args,
        **kwargs: P.kwargs,
    ):
        """
        Initialize the TermReplacer with the given parameters.

        Args:
            library (Library): The library to use for creating new AST nodes.
            condition (callable): A function that takes a term and the recursion depth and returns True if it should be replaced.
            callback (callable): A function that takes a LiteralComparison and is called when a replacement occurs.
            variable_generator (FreshVariableGenerator): A generator for creating fresh variable names.
        """
        self.library = library
        self.condition = condition
        self.callback = callback
        self.variable_generator = variable_generator
        self.sign = sign
        self.args = args
        self.kwargs = kwargs

    def replace_term(
        self,
        node: ast.terms.TermOrProjection | Symbol,
        depth: int,
        location: Location,
        recursive_function: Callable[
            [ast.terms.TermOrProjection, int], ast.terms.TermOrProjection | None
        ],
    ) -> ast.terms.TermVariable | None:
        if isinstance(node, ast.terms.Projection) or not self.condition(
            node, depth, *self.args, **self.kwargs
        ):
            return None
        if isinstance(node, Symbol):
            node = ast.terms.TermSymbolic(self.library, location, node)
        new_node = recursive_function(node, depth + 1)
        if new_node is not None:
            assert not isinstance(
                new_node, ast.terms.Projection
            ), f"Cannot replace a projection with a projection: {new_node}"
            node = new_node
        fresh: ast.terms.TermVariable = self.variable_generator.fresh_variable(
            self.library, location, "FUN"
        )
        comp = make_equation(self.library, location, node, fresh, self.sign)
        self.callback(comp)
        return fresh


def replace_term[**P](
    library: Library,
    node: ast.terms.TermOrProjection,
    condition: Callable[Concatenate[ast.terms.Term | Symbol, int, P], bool],
    callback: Callable[[ast.literals.LiteralComparison], None],
    variable_generator: FreshVariableGenerator,
    sign: ast.literals.Sign,
    *args: P.args,
    **kwargs: P.kwargs,
) -> ast.terms.TermOrProjection | None:
    """
    Replace a term in the AST with a fresh variable if it satisfies the given condition.

    Args:
        library (Library): The library to use for creating new AST nodes.
        node (ast.terms.TermOrProjection): The term AST node to transform.
        condition (callable): A function that takes a term and the recursion depth and returns True if it should be replaced.
        callback (callable): A function that takes a LiteralComparison and is called when a replacement occurs.
        variable_generator (FreshVariableGenerator): A generator for creating fresh variable names.
    Returns:
        ast.terms.TermOrProjection | None: The transformed term AST node, or None if no transformation occurred.
    """
    term_replacer = TermReplacer(
        library,
        condition,
        callback,
        variable_generator,
        sign,
        *args,
        **kwargs,
    )
    transformer = TermTransformer(
        library,
        term_replacer.replace_term,
    )
    return transformer(node, 0)
