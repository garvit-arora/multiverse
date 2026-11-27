"""Atlas configuration domain validation and exploration strategies (Exhaustive, Pairwise, Adaptive)."""
from __future__ import annotations

import hashlib
import heapq
import itertools
import random
from dataclasses import dataclass, field
from typing import Any

import rfc8785
from allpairspy import AllPairs


@dataclass
class FlagDomain:
    key: str
    values: list[Any]
    flag_type: str = "boolean"


@dataclass
class ExplorationConstraints:
    forbidden_pairs: list[dict[str, Any]] = field(default_factory=list)
    requires: list[dict[str, Any]] = field(default_factory=list)


def canonical_config_hash(assignments: dict[str, Any]) -> str:
    return hashlib.sha256(rfc8785.dumps(assignments)).hexdigest()


def validate_configuration(
    assignments: dict[str, Any],
    domains: dict[str, list[Any]],
    constraints: ExplorationConstraints | None = None,
) -> tuple[bool, list[str]]:
    """Validate that all assignments belong to declared finite domains and satisfy constraints."""
    errors: list[str] = []
    for key, allowed in domains.items():
        if key not in assignments:
            errors.append(f"Missing required flag '{key}'")
            continue
        if assignments[key] not in allowed:
            errors.append(f"Value {assignments[key]!r} for '{key}' not in allowed domain {allowed}")

    if constraints:
        for rule in constraints.forbidden_pairs:
            # e.g. {"if": {"lite_mode": True}, "forbid": {"animations": True}}
            cond = rule.get("if", {})
            forbid = rule.get("forbid", {})
            if all(assignments.get(k) == v for k, v in cond.items()):
                for fk, fv in forbid.items():
                    if assignments.get(fk) == fv:
                        errors.append(f"Forbidden combination: {cond} with {fk}={fv}")
        for rule in constraints.requires:
            cond = rule.get("if", {})
            req = rule.get("require", {})
            if all(assignments.get(k) == v for k, v in cond.items()):
                for rk, rv in req.items():
                    if assignments.get(rk) != rv:
                        errors.append(f"Constraint violation: {cond} requires {rk}={rv}")

    return len(errors) == 0, errors


def compute_finite_space_size(domains: dict[str, list[Any]]) -> int:
    total = 1
    for vals in domains.values():
        total *= max(len(vals), 1)
    return total


def all_pairs_set(domains: dict[str, list[Any]]) -> set[tuple[str, Any, str, Any]]:
    keys = sorted(domains.keys())
    pairs: set[tuple[str, Any, str, Any]] = set()
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            k1, k2 = keys[i], keys[j]
            for v1 in domains[k1]:
                for v2 in domains[k2]:
                    pairs.add((k1, repr(v1), k2, repr(v2)))
    return pairs


def measure_pairwise_coverage(configs: list[dict[str, Any]], domains: dict[str, list[Any]]) -> float:
    universe = all_pairs_set(domains)
    if not universe:
        return 1.0
    keys = sorted(domains.keys())
    covered: set[tuple[str, Any, str, Any]] = set()
    for cfg in configs:
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                k1, k2 = keys[i], keys[j]
                if k1 in cfg and k2 in cfg:
                    covered.add((k1, repr(cfg[k1]), k2, repr(cfg[k2])))
    return len(covered & universe) / len(universe)


def generate_exhaustive(
    domains: dict[str, list[Any]],
    constraints: ExplorationConstraints | None = None,
    limit: int = 256,
) -> list[dict[str, Any]]:
    keys = sorted(domains.keys())
    if not keys:
        return [{}]
    value_lists = [domains[k] for k in keys]
    results: list[dict[str, Any]] = []
    for combo in itertools.product(*value_lists):
        cfg = dict(zip(keys, combo))
        valid, _ = validate_configuration(cfg, domains, constraints)
        if valid:
            results.append(cfg)
            if len(results) >= limit:
                break
    return results


def generate_pairwise(
    domains: dict[str, list[Any]],
    constraints: ExplorationConstraints | None = None,
    budget: int = 64,
) -> tuple[list[dict[str, Any]], float]:
    keys = sorted(domains.keys())
    if not keys:
        return [{}], 1.0
    if len(keys) == 1:
        k = keys[0]
        cfgs = [{k: v} for v in domains[k][:budget]]
        return cfgs, 1.0

    # AllPairsPy requires >= 2 parameters with >= 1 value each
    parameters = [domains[k] for k in keys]
    raw_configs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pair_row in AllPairs(parameters):
        cfg = dict(zip(keys, pair_row))
        valid, _ = validate_configuration(cfg, domains, constraints)
        if valid:
            h = canonical_config_hash(cfg)
            if h not in seen:
                seen.add(h)
                raw_configs.append(cfg)
                if len(raw_configs) >= budget:
                    break

    coverage = measure_pairwise_coverage(raw_configs, domains)
    return raw_configs, coverage


class AdaptiveExplorer:
    """Custom adaptive configuration explorer with normalized priority scoring and neighbour expansion."""

    def __init__(
        self,
        domains: dict[str, list[Any]],
        baseline: dict[str, Any] | None = None,
        constraints: ExplorationConstraints | None = None,
        seed: int = 42,
        weights: tuple[float, float, float, float] = (0.4, 0.3, 0.2, 0.1),
    ) -> None:
        self.domains = domains
        self.keys = sorted(domains.keys())
        self.constraints = constraints
        self.rng = random.Random(seed)
        self.weights = weights  # (novelty, interaction_cov, config_cov, uncertainty)
        self.baseline = baseline or {k: domains[k][0] for k in self.keys}

        self.seen_hashes: set[str] = set()
        self.executed: list[dict[str, Any]] = []
        self.observed_fingerprints: dict[str, str] = {}  # config_hash -> fingerprint
        self.flag_value_counts: dict[tuple[str, str], int] = {}
        self.covered_pairs: set[tuple[str, Any, str, Any]] = set()
        self.total_pairs = all_pairs_set(domains)

        # Max-heap via negative priority: (-priority, tie_breaker, config)
        self._queue: list[tuple[float, int, dict[str, Any]]] = []
        self._counter = 0

        self._seed_initial_candidates()

    def _enqueue(self, cfg: dict[str, Any], boost: float = 0.0) -> None:
        valid, _ = validate_configuration(cfg, self.domains, self.constraints)
        if not valid:
            return
        h = canonical_config_hash(cfg)
        if h in self.seen_hashes:
            return
        self.seen_hashes.add(h)
        score = min(1.0, self._score_candidate(cfg) + boost)
        self._counter += 1
        heapq.heappush(self._queue, (-score, self._counter, cfg))

    def _score_candidate(self, cfg: dict[str, Any]) -> float:
        w_nov, w_int, w_cfg, w_unc = self.weights

        # 1. Predicted novelty: fraction of flag-value pairs not yet seen in distinct behaviours
        unseen_vals = 0
        for k, v in cfg.items():
            if self.flag_value_counts.get((k, repr(v)), 0) == 0:
                unseen_vals += 1
        predicted_novelty = unseen_vals / max(len(self.keys), 1)

        # 2. Interaction coverage gain: fraction of new 2-way pairs this candidate would cover
        new_pairs = 0
        possible_pairs = max(len(self.keys) * (len(self.keys) - 1) // 2, 1)
        for i in range(len(self.keys)):
            for j in range(i + 1, len(self.keys)):
                k1, k2 = self.keys[i], self.keys[j]
                pair = (k1, repr(cfg[k1]), k2, repr(cfg[k2]))
                if pair not in self.covered_pairs:
                    new_pairs += 1
        interaction_coverage = new_pairs / possible_pairs

        # 3. Configuration coverage: normalized Hamming distance from nearest executed config
        if not self.executed:
            config_coverage = 1.0
        else:
            min_dist = min(
                sum(1 for k in self.keys if cfg[k] != ex[k]) / max(len(self.keys), 1)
                for ex in self.executed
            )
            config_coverage = min_dist

        # 4. Uncertainty: higher when fewer observations exist in local neighbourhood
        total_obs_for_vals = sum(self.flag_value_counts.get((k, repr(cfg[k])), 0) for k in self.keys)
        uncertainty = 1.0 / (1.0 + total_obs_for_vals / max(len(self.keys), 1))

        return (
            w_nov * predicted_novelty
            + w_int * interaction_coverage
            + w_cfg * config_coverage
            + w_unc * uncertainty
        )

    def _seed_initial_candidates(self) -> None:
        # 1. Baseline
        self._enqueue(dict(self.baseline), boost=0.5)
        # 2. Single-feature deltas
        for k in self.keys:
            for val in self.domains[k]:
                if val != self.baseline.get(k):
                    cand = dict(self.baseline)
                    cand[k] = val
                    self._enqueue(cand, boost=0.2)
        # 3. Pairwise subset
        pw, _ = generate_pairwise(self.domains, self.constraints, budget=32)
        for cfg in pw:
            self._enqueue(cfg, boost=0.1)
        # 4. Seeded random candidates
        for _ in range(min(32, compute_finite_space_size(self.domains))):
            cand = {k: self.rng.choice(self.domains[k]) for k in self.keys}
            self._enqueue(cand)

    def has_next(self) -> bool:
        return len(self._queue) > 0

    def next_candidate(self) -> dict[str, Any] | None:
        if not self._queue:
            return None
        _, _, cfg = heapq.heappop(self._queue)
        return cfg

    def record_observation(self, cfg: dict[str, Any], fingerprint: str, is_novel_behaviour: bool) -> None:
        h = canonical_config_hash(cfg)
        self.executed.append(cfg)
        self.observed_fingerprints[h] = fingerprint
        for k, v in cfg.items():
            self.flag_value_counts[(k, repr(v))] = self.flag_value_counts.get((k, repr(v)), 0) + 1
        for i in range(len(self.keys)):
            for j in range(i + 1, len(self.keys)):
                k1, k2 = self.keys[i], self.keys[j]
                self.covered_pairs.add((k1, repr(cfg[k1]), k2, repr(cfg[k2])))

        # Expand 1-hop neighbours around newly discovered distinct behaviours
        if is_novel_behaviour:
            for k in self.keys:
                for val in self.domains[k]:
                    if val != cfg[k]:
                        neighbour = dict(cfg)
                        neighbour[k] = val
                        self._enqueue(neighbour, boost=0.25)
