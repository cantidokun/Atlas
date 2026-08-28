"""Tests for the explicit Unreal production planning trust boundary."""

import pytest

from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_planning_boundary import (
    UnrealAuthorizedProductionPlan,
    authorize_production_plan,
)
from tests.test_unreal_heterogeneous_production import _intent, _spec


def test_authorize_production_plan_binds_exact_concrete_plan():
    production = build_unreal_production_plan(_intent(), _spec())

    authorized = authorize_production_plan(production, "production-boundary-auth")

    assert isinstance(authorized, UnrealAuthorizedProductionPlan)
    assert authorized.production is production
    assert isinstance(authorized.authorization, UnrealPlanAuthorization)
    assert authorized.authorization.matches(production.plan)
    assert authorized.authorization.authorization_id == "production-boundary-auth"


def test_authorization_is_for_the_concrete_plan_not_a_reconstructed_variant():
    production = build_unreal_production_plan(_intent(), _spec())
    authorized = authorize_production_plan(production, "production-boundary-auth")

    other = build_unreal_production_plan(_intent(), _spec())

    assert authorized.authorization.matches(production.plan)
    assert authorized.authorization.matches(other.plan)

    # A same-value plan is intentionally equivalent at the authorization
    # boundary; any material change must produce a different digest.
    changed_spec = _spec()
    changed_spec = type(changed_spec)(
        composite=changed_spec.composite,
        start_frame=changed_spec.start_frame,
        end_frame=23,
        render_config=type(changed_spec.render_config)(
            width=changed_spec.render_config.width,
            height=changed_spec.render_config.height,
            start_frame=changed_spec.render_config.start_frame,
            end_frame=23,
            output_directory=changed_spec.render_config.output_directory,
            output_format=changed_spec.render_config.output_format,
        ),
        blueprint_asset_path=changed_spec.blueprint_asset_path,
    )
    changed = build_unreal_production_plan(_intent(), changed_spec)
    assert not authorized.authorization.matches(changed.plan)


def test_authorize_production_plan_rejects_invalid_inputs():
    with pytest.raises(TypeError):
        authorize_production_plan(object(), "auth")
    production = build_unreal_production_plan(_intent(), _spec())
    with pytest.raises(ValueError):
        authorize_production_plan(production, "   ")
