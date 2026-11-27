from services.api.atlas.explorer import (
    AdaptiveExplorer,
    ExplorationConstraints,
    canonical_config_hash,
    generate_exhaustive,
    generate_pairwise,
    measure_pairwise_coverage,
    validate_configuration,
)
from services.api.atlas.fingerprint import compute_fingerprint, normalize_observation


DOMAINS = {"checkout": [False, True], "theme": ["light", "dark"], "search": ["basic", "advanced"]}


def test_exhaustive_generation_and_constraints():
    constraints = ExplorationConstraints(
        forbidden_pairs=[{"if": {"checkout": False}, "forbid": {"search": "advanced"}}]
    )
    configs = generate_exhaustive(DOMAINS, constraints, limit=100)
    assert len(configs) == 6
    assert all(validate_configuration(config, DOMAINS, constraints)[0] for config in configs)


def test_pairwise_generation_reports_measured_coverage():
    configs, coverage = generate_pairwise(DOMAINS, budget=32)
    assert configs
    assert coverage == measure_pairwise_coverage(configs, DOMAINS)
    assert coverage == 1.0


def test_adaptive_explorer_is_deterministic_and_deduplicated():
    first = AdaptiveExplorer(DOMAINS, seed=7)
    second = AdaptiveExplorer(DOMAINS, seed=7)
    first_configs = [first.next_candidate() for _ in range(6)]
    second_configs = [second.next_candidate() for _ in range(6)]
    assert first_configs == second_configs
    hashes = [canonical_config_hash(config) for config in first_configs if config]
    assert len(hashes) == len(set(hashes))


def test_fingerprint_normalizes_runtime_identifiers():
    one = normalize_observation({
        "routes_visited": ["/orders/550e8400-e29b-41d4-a716-446655440000"],
        "visible_components": ["checkout"],
        "business_events": ["completed at 2026-11-26T12:30:00Z"],
        "outcome": "success",
    })
    two = normalize_observation({
        "routes_visited": ["/orders/123e4567-e89b-12d3-a456-426614174000"],
        "visible_components": ["checkout"],
        "business_events": ["completed at 2025-01-01T01:02:03Z"],
        "outcome": "success",
    })
    assert compute_fingerprint(one) == compute_fingerprint(two)
