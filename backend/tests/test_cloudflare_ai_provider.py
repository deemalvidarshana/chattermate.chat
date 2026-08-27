from unittest.mock import patch

import pytest

from app.core.model_catalog import MODEL_CATALOG
from app.utils.agno_utils import (
    create_model,
    pack_cloudflare_credentials,
    unpack_cloudflare_credentials,
)


MODEL_ID = "@cf/google/gemma-4-26b-a4b-it"
ACCOUNT_ID = "0123456789abcdef0123456789abcdef"


def test_cloudflare_catalog_includes_gemma_4():
    provider = MODEL_CATALOG["CLOUDFLARE"]
    assert {model["value"] for model in provider["models"]} == {MODEL_ID}
    assert [field["name"] for field in provider["credential_fields"]] == [
        "account_id",
        "gateway_id",
    ]


def test_cloudflare_credentials_round_trip():
    packed = pack_cloudflare_credentials("secret-token", ACCOUNT_ID, "support")
    assert unpack_cloudflare_credentials(packed) == {
        "api_token": "secret-token",
        "account_id": ACCOUNT_ID,
        "gateway_id": "support",
    }


def test_cloudflare_model_uses_openai_compatible_endpoint():
    credentials = pack_cloudflare_credentials("secret-token", ACCOUNT_ID)
    with patch("app.utils.agno_utils.OpenAIChat") as model_class:
        create_model("CLOUDFLARE", credentials, MODEL_ID, max_tokens=512)

    model_class.assert_called_once_with(
        api_key="secret-token",
        id=MODEL_ID,
        max_completion_tokens=512,
        request_params={
            "extra_body": {
                "chat_template_kwargs": {"enable_thinking": False},
            }
        },
        base_url=f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1",
        default_headers={"cf-aig-gateway-id": "default"},
    )


def test_cloudflare_credentials_require_account_id():
    with pytest.raises(ValueError, match="Account ID"):
        unpack_cloudflare_credentials('{"api_token":"secret-token"}')
