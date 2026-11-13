"""Working memory: the facts known during one consultation."""

from dataclasses import dataclass, field

from engine.certainty import combine


@dataclass
class Fact:
    """One fact: name, value, CF, the rules that gave it and extra data."""
    name: str
    value: object
    cf: float = 1.0
    source_rules: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)


class WorkingMemory:
    """All facts, warnings, notes and decisions of one consultation."""
    def __init__(self):
        """Start with empty memory."""
        self.facts = {}
        self.ignored = {}      # inputs removed by sanity rules, kept for the warning text
        self.warnings = []     # list of (rule_id, text)
        self.notes = []        # list of (rule_id, field_or_None, text)
        self.halted = False
        self.result = {}       # decisions made by G8 and DS06

    def get(self, name):
        """The fact with this name, or None."""
        return self.facts.get(name)

    def has(self, name):
        """True if the fact exists."""
        return name in self.facts

    def value(self, name, default=None):
        """The value of a fact, or a default."""
        f = self.facts.get(name)
        return f.value if f else default

    def add(self, name, value, cf, rule_id, meta=None):
        """Add a fact. If it already exists, combine CFs (agreeing evidence).

        Returns a short text describing what happened, for the trace.
        """
        old = self.facts.get(name)
        if old is None:
            self.facts[name] = Fact(name, value, cf, [rule_id], dict(meta or {}))
            return None
        before = old.cf
        old.cf = combine(old.cf, cf)
        old.source_rules.append(rule_id)
        if meta:
            old.meta.update(meta)
        return f"combined {before:.3f} with {cf:.3f} -> {old.cf:.3f}"

    def put(self, name, value, cf, rule_id, meta=None):
        """Set a fact without CF combining (used for decision facts)."""
        old = self.facts.get(name)
        sources = (old.source_rules if old else []) + [rule_id]
        self.facts[name] = Fact(name, value, cf, sources, dict(meta or {}))

    def ignore(self, name, reason, rule_id):
        """Move an input fact out of working memory (rules then see it as missing)."""
        f = self.facts.pop(name, None)
        if f is not None:
            self.ignored[name] = (f.value, reason, rule_id)
        return f

    def snapshot(self):
        """Facts as a simple dict (for debugging and tests)."""
        return {n: (f.value, round(f.cf, 4)) for n, f in self.facts.items()}
