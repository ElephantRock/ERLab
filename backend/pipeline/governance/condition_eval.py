"""Condition evaluator — recursive descent parser for compound policy conditions.

DSL examples:
    "score > 0.8"
    "AND(score > 0.8, tokens < 500000)"
    "OR(risk = high, NOT(domain = safe))"
    "AND(budget_remaining < 10, run_count > 5)"
"""

from __future__ import annotations

import re
from typing import Any, Protocol


class ConditionNode(Protocol):
    def evaluate(self, context: dict[str, Any]) -> bool: ...


class AtomNode:
    __slots__ = ("operand_a", "operator", "operand_b")

    def __init__(self, operand_a: str, operator: str, operand_b: str):
        self.operand_a = operand_a
        self.operator = operator
        self.operand_b = operand_b

    def evaluate(self, context: dict[str, Any]) -> bool:
        a = _resolve(self.operand_a, context)
        b = _resolve(self.operand_b, context)
        op = self.operator

        if op == "=":
            return str(a) == str(b)
        if op == "!=":
            return str(a) != str(b)
        if op in ("<", ">", "<=", ">="):
            return _compare(a, b, op)
        if op == "contains":
            return str(b).lower() in str(a).lower()
        if op == "not_contains":
            return str(b).lower() not in str(a).lower()
        if op == "in":
            return str(a) in [s.strip() for s in str(b).split(",")]
        if op == "not_in":
            return str(a) not in [s.strip() for s in str(b).split(",")]
        return False

    def __repr__(self) -> str:
        return f"{self.operand_a} {self.operator} {self.operand_b}"


class AndNode:
    __slots__ = ("children",)

    def __init__(self, children: list[ConditionNode]):
        self.children = children

    def evaluate(self, context: dict[str, Any]) -> bool:
        return all(c.evaluate(context) for c in self.children)


class OrNode:
    __slots__ = ("children",)

    def __init__(self, children: list[ConditionNode]):
        self.children = children

    def evaluate(self, context: dict[str, Any]) -> bool:
        return any(c.evaluate(context) for c in self.children)


class NotNode:
    __slots__ = ("child",)

    def __init__(self, child: ConditionNode):
        self.child = child

    def evaluate(self, context: dict[str, Any]) -> bool:
        return not self.child.evaluate(context)


def _resolve(token: str, context: dict[str, Any]) -> Any:
    if token.startswith("{") and token.endswith("}"):
        key = token[1:-1]
        return context.get(key)
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    if token.lower() == "true":
        return True
    if token.lower() == "false":
        return False
    if token.lower() == "none":
        return None
    if token in context:
        return context[token]
    return token


def _compare(a: Any, b: Any, op: str) -> bool:
    if a is None or b is None:
        return False
    try:
        fa, fb = float(a), float(b)
    except (ValueError, TypeError):
        fa, fb = str(a), str(b)
    if op == "<":
        return fa < fb
    if op == ">":
        return fa > fb
    if op == "<=":
        return fa <= fb
    if op == ">=":
        return fa >= fb
    return False


_OP_PATTERN = re.compile(r"^\s*(\{?\w+\}?)\s*(!=|<=|>=|=|<|>|contains|not_contains|in|not_in)\s*(.+?)\s*$")


def parse(expression: str) -> ConditionNode:
    expr = expression.strip()

    if expr.upper().startswith("AND(") and expr.endswith(")"):
        inner = expr[4:-1]
        return AndNode(_split_and_parse(inner))

    if expr.upper().startswith("OR(") and expr.endswith(")"):
        inner = expr[3:-1]
        return OrNode(_split_and_parse(inner))

    if expr.upper().startswith("NOT(") and expr.endswith(")"):
        inner = expr[4:-1]
        return NotNode(parse(inner))

    m = _OP_PATTERN.match(expr)
    if m:
        return AtomNode(m.group(1).strip(), m.group(2), m.group(3).strip())

    raise ValueError(f"Cannot parse condition: {expression!r}")


def evaluate(expression: str, context: dict[str, Any]) -> bool:
    return parse(expression).evaluate(context)


def _split_and_parse(inner: str) -> list[ConditionNode]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in inner:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return [parse(p) for p in parts if p]
