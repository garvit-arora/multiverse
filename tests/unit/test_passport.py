import pytest

from services.api.passport.service import PassportVerificationError, create_signed_passport, verify_passport_token


def test_passport_sign_verify_and_tamper_rejection():
    signed = create_signed_passport({"interface.density": "compact"}, audience=["demo-shop"])
    payload = verify_passport_token(signed["token"], expected_audience="demo-shop")
    assert payload["preferences"] == {"interface.density": "compact"}

    head, body, signature = signed["token"].split(".")
    tampered = f"{head}.{body[:-1]}{'A' if body[-1] != 'A' else 'B'}.{signature}"
    with pytest.raises(PassportVerificationError):
        verify_passport_token(tampered)


def test_project_workflow_scope_is_covered_by_signature():
    scope = {
        "application_id": "shop",
        "application_name": "Demo Shop",
        "build_id": "build-42",
        "workflow_id": "checkout",
        "workflow_name": "Checkout journey",
        "workflow_version": "1.0",
    }
    signed = create_signed_passport({"interface.density": "comfortable"}, scope=scope)
    payload = verify_passport_token(signed["token"])
    assert payload["scope"] == scope
