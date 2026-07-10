# backend/tests/bi/test_registry.py
"""
Unit tests for the declarative KPI registry (app_modules/bi/registry.py).

Pure Python — no DB. These pin the 1b contract:
- registering a KPI is a single declaration (no compute code),
- the registry is introspectable (get / all_kpis / keys),
- the KPIDefinition validates its own shape (scopes, breakdown dimension,
  decoupled target),
- duplicate / unknown keys fail loudly.
"""

import pytest

from app_modules.bi import registry
from app_modules.bi.registry import KPIDefinition, register, get, all_kpis, keys
from app_modules.bi.types import OutputShape, KPIResult


@pytest.fixture(autouse=True)
def _clean_registry():
    """Isolate each test — the registry is a module-level singleton."""
    registry.clear()
    yield
    registry.clear()


def _defn(key='k', shape=OutputShape.SCALAR, **kw):
    base = dict(
        key=key,
        label='Label',
        source=lambda: None,          # opaque to the registry (no compute here)
        aggregation=object(),          # opaque ORM expression placeholder
        scope_module='activities',
        period_field='created_at',
        output_shape=shape,
    )
    base.update(kw)
    return KPIDefinition(**base)


# =============================================================================
# Registration + introspection
# =============================================================================

def test_register_and_get():
    d = _defn(key='dc_pipeline_value')
    assert register(d) is d
    assert get('dc_pipeline_value') is d
    assert registry.is_registered('dc_pipeline_value')


def test_all_and_keys_reflect_registration_order():
    a = _defn(key='a')
    b = _defn(key='b')
    register(a)
    register(b)
    assert keys() == ['a', 'b']
    assert all_kpis() == [a, b]


def test_duplicate_key_raises():
    register(_defn(key='dup'))
    with pytest.raises(ValueError, match="already registered"):
        register(_defn(key='dup'))


def test_get_unknown_raises():
    with pytest.raises(KeyError, match="No KPI registered"):
        get('missing')


def test_register_rejects_non_definition():
    with pytest.raises(TypeError):
        register(object())  # type: ignore[arg-type]


# =============================================================================
# KPIDefinition self-validation
# =============================================================================

def test_scalar_ok_without_dimension():
    d = _defn(shape=OutputShape.SCALAR)
    assert d.dimension is None
    assert d.default_period == 'fiscal_year'  # sensible default
    assert d.allowed_scopes == ('mine', 'team', 'client')


def test_breakdown_requires_dimension():
    with pytest.raises(ValueError, match="BREAKDOWN output requires"):
        _defn(shape=OutputShape.BREAKDOWN)  # no dimension
    # ...and is accepted with one
    d = _defn(shape=OutputShape.BREAKDOWN, dimension='outcome')
    assert d.dimension == 'outcome'


def test_invalid_scope_rejected():
    with pytest.raises(ValueError, match="invalid allowed_scopes"):
        _defn(allowed_scopes=('mine', 'galaxy'))


def test_empty_scopes_rejected():
    with pytest.raises(ValueError, match="allowed_scopes must not be empty"):
        _defn(allowed_scopes=())


def test_empty_key_rejected():
    with pytest.raises(ValueError, match="key must be"):
        _defn(key='')


def test_non_callable_source_rejected():
    with pytest.raises(TypeError, match="source must be callable"):
        _defn(source=123)


def test_bad_output_shape_rejected():
    with pytest.raises(TypeError, match="output_shape must be an OutputShape"):
        _defn(shape='scalar')  # raw string, not the enum


# =============================================================================
# Target is optional and decoupled (V2 milestones attach here later)
# =============================================================================

def test_target_optional_and_decoupled():
    d = _defn(key='no_target')
    assert d.target is None  # decoupled: metric works with no target

    resolver = lambda auth_ctx, period: 100
    d2 = _defn(key='with_target', target=resolver)
    assert d2.target is resolver
    # target lives beside aggregation, not inside it
    assert d2.aggregation is not d2.target


def test_non_callable_target_rejected():
    with pytest.raises(TypeError, match="target must be callable or None"):
        _defn(target=42)


# =============================================================================
# KPIResult shape container (types.py)
# =============================================================================

def test_kpi_result_defaults():
    r = KPIResult(key='k', shape=OutputShape.SCALAR, value=12, scope='mine')
    assert r.value == 12
    assert r.target is None and r.attainment is None
    assert r.meta == {}
    assert r.period_start is None and r.period_end is None
