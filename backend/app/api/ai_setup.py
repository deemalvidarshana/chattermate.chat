"""
Copyright 2024-2026 ChatterMate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import traceback
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from app.core import config
from app.core.logger import get_logger
from app.core.security import decrypt_api_key
from app.database import get_db
from app.models.user import User
from app.core.auth import get_current_user, require_permissions
from app.repositories.ai_config import AIConfigRepository
from app.agents.chat_agent import ChatAgent
from app.models.schemas.ai_config import AIConfigCreate, AIConfigResponse, AISetupResponse, AIConfigUpdate
from sqlalchemy.orm import Session
import os

from app.models.ai_config import AIModelType
from app.core.model_catalog import is_known_provider, list_providers
from app.utils.agno_utils import pack_cloudflare_credentials, unpack_cloudflare_credentials

# Try to import enterprise modules
try:
    from app.enterprise.repositories.plan import PlanRepository
    from app.enterprise.services.feature_access import require_accessible_subscription
    HAS_ENTERPRISE = True
except ImportError:
    HAS_ENTERPRISE = False

router = APIRouter()
logger = get_logger(__name__)

OPENROUTER_MODEL_API = "https://openrouter.ai/api/v1/model"
OPENROUTER_REQUIRED_PARAMETERS = {"tools", "structured_outputs"}


def _cloudflare_settings(account_id: str, gateway_id: str | None) -> dict:
    account_id = (account_id or "").strip()
    if len(account_id) != 32 or not all(char in "0123456789abcdefABCDEF" for char in account_id):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid Cloudflare Account ID",
                "type": "invalid_account_id",
                "details": "Enter the 32-character hexadecimal Account ID from your Cloudflare dashboard.",
            },
        )
    return {"account_id": account_id, "gateway_id": (gateway_id or "default").strip() or "default"}


def _cloudflare_credential(api_token: str, account_id: str, gateway_id: str | None) -> tuple[str, dict]:
    provider_settings = _cloudflare_settings(account_id, gateway_id)
    return (
        pack_cloudflare_credentials(api_token, provider_settings["account_id"], provider_settings["gateway_id"]),
        provider_settings,
    )


async def _validate_openrouter_capabilities(api_key: str, model_name: str) -> None:
    """Reject OpenRouter models that cannot run ChatterMate's agent contract."""
    encoded_model = quote(model_name.strip(), safe="/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{OPENROUTER_MODEL_API}/{encoded_model}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
    except httpx.HTTPError as exc:
        logger.warning(f"Could not read OpenRouter model capabilities for {model_name}: {exc}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Could not verify model capabilities",
                "type": "model_capability_check_failed",
                "details": "OpenRouter model details could not be loaded. Try again shortly.",
            },
        ) from exc

    if response.status_code == 401:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid API key",
                "type": "invalid_api_key",
                "details": "OpenRouter rejected the API key. Enter a new key and try again.",
            },
        )
    if response.status_code == 404:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Model unavailable",
                "type": "model_not_found",
                "details": f"The OpenRouter model '{model_name}' is unavailable.",
            },
        )
    try:
        response.raise_for_status()
        model_data = response.json()["data"]
        supported = set(model_data.get("supported_parameters") or [])
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        logger.warning(f"Invalid OpenRouter model metadata for {model_name}: {exc}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Could not verify model capabilities",
                "type": "model_capability_check_failed",
                "details": "OpenRouter returned incomplete model details. Try a different model.",
            },
        ) from exc

    missing = sorted(OPENROUTER_REQUIRED_PARAMETERS - supported)
    if missing:
        labels = {"tools": "tool calling", "structured_outputs": "structured JSON output"}
        missing_labels = ", ".join(labels[item] for item in missing)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Incompatible OpenRouter model",
                "type": "incompatible_model",
                "details": (
                    f"The model '{model_name}' does not support {missing_labels}, "
                    "which ChatterMate requires. Choose a compatible model."
                ),
            },
        )


def _provider_validation_error(
    exc: Exception,
    model_type: str,
    model_name: str,
) -> HTTPException:
    """Turn provider failures into accurate, safe UI errors.

    Providers often use the same 404 response for a retired model and a model
    blocked by project permissions. Neither case means the API key is invalid.
    """
    message = str(exc).lower()

    if "model_not_found" in message or "does not exist or you do not have access" in message:
        replacement = (
            " Use openai/gpt-oss-20b instead."
            if model_type.upper() == "GROQ" and model_name == "llama-3.1-8b-instant"
            else " Choose a model available to this provider account."
        )
        return HTTPException(
            status_code=400,
            detail={
                "error": "Model unavailable",
                "type": "model_not_found",
                "details": f"The model '{model_name}' is unavailable or not enabled for this API key.{replacement}",
            },
        )

    if "invalid_api_key" in message or "invalid api key" in message or "authentication" in message:
        return HTTPException(
            status_code=400,
            detail={
                "error": "Invalid API key",
                "type": "invalid_api_key",
                "details": "The provider rejected the API key. Enter a new key and try again.",
            },
        )

    if "rate_limit" in message or "too many requests" in message or "request too large" in message:
        return HTTPException(
            status_code=400,
            detail={
                "error": "Provider rate limit reached",
                "type": "provider_rate_limit",
                "details": "The provider rejected the validation request because this account's rate limit was exceeded. Try again later or choose a smaller model.",
            },
        )

    return HTTPException(
        status_code=400,
        detail={
            "error": "Model validation failed",
            "type": "model_validation_error",
            "details": "The provider could not validate this API key and model combination.",
        },
    )


async def _validate_provider_model(api_key: str, model_type: str, model_name: str) -> None:
    if model_type.upper() == "OPENROUTER":
        await _validate_openrouter_capabilities(api_key, model_name)

    try:
        is_valid = await ChatAgent.test_api_key(
            api_key=api_key,
            model_type=model_type,
            model_name=model_name,
            raise_on_error=True,
        )
    except Exception as exc:
        raise _provider_validation_error(exc, model_type, model_name) from exc

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid API key",
                "type": "invalid_api_key",
                "details": "The provider rejected this API key and model combination.",
            },
        )


def check_custom_models_feature_access(current_user: User, db: Session):
    """Check if user has access to custom models feature"""
    if not HAS_ENTERPRISE:
        return  # Allow access in non-enterprise mode
    
    # Accessible = active/trial/past-due-in-period OR cancelled-but-still-in-
    # paid-period; raises 403 when the org has no accessible plan.
    subscription = require_accessible_subscription(db, current_user.organization_id)
    plan_repo = PlanRepository(db)

    # Check if custom models feature is available in the plan
    if not plan_repo.check_feature_availability(str(subscription.plan_id), 'custom_models'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Custom Models feature is not available in your current plan. Please upgrade to access this feature."
        )


# Providers and their suggested models live in app.core.model_catalog (single
# source of truth, also served by GET /ai/providers). Model IDs are not hard-coded
# here anymore: orgs may enter a custom model ID, so validation only checks that the
# provider is known — the live API-key test rejects a bad model ID.


@router.get("/providers")
async def get_providers(
    current_user: User = Depends(require_permissions("manage_ai_config")),
):
    """Return the catalog of selectable providers and their suggested models."""
    return {"providers": list_providers()}


# Override model validation in the schemas
@router.post("/setup", response_model=AISetupResponse)
async def setup_ai(
    config_data: AIConfigCreate,
    current_user: User = Depends(require_permissions("manage_ai_config")),
    db: Session = Depends(get_db)
):
    """Setup AI configuration for the current user's organization"""
    try:
        logger.info("Setting up AI config")
        
        # Validate model selection based on provider
        validate_model_selection(config_data.model_type, config_data.model_name)
        
        # Check if this is a custom model setup (not ChatterMate)
        is_custom_model = not (config_data.model_type.lower() == 'chattermate' and config_data.model_name.lower() == 'chattermate')
        
        # Check feature access for custom models
        if is_custom_model:
            check_custom_models_feature_access(current_user, db)
        
        # Check if using ChatterMate model
        if HAS_ENTERPRISE and config_data.model_type.lower() == 'chattermate' and config_data.model_name.lower() == 'chattermate':
            # Use Groq as provider with keys from env
            model_type = AIModelType.CHATTERMATE
            model_name = os.getenv('CHATTERMATE_MODEL_NAME', 'gpt-4o-mini')
            api_key = os.getenv('CHATTERMATE_API_KEY', '')
        
            if not api_key:
                logger.error("ChatterMate API key not found in environment")
                raise HTTPException(
                        status_code=500,
                        detail="ChatterMate API configuration missing"
                )
                
            # Create AI configuration
            ai_config_repo = AIConfigRepository(db)
            ai_config = ai_config_repo.create_config(
                org_id=current_user.organization_id,
                model_type=model_type,
                model_name=model_name,
                api_key=api_key
            )
            
            # Prepare response
            response = AISetupResponse(
                message="AI configuration completed successfully",
                config=AIConfigResponse(
                    id=ai_config.id,
                    organization_id=ai_config.organization_id,
                    model_type=ai_config.model_type,
                    model_name=ai_config.model_name,
                    is_active=ai_config.is_active,
                    has_api_key=bool(ai_config.encrypted_api_key),
                    settings=ai_config.settings
                )
            )
            
            logger.debug(
                f"ChatterMate AI setup completed for org {current_user.organization_id}")
            return response
        
        # Regular custom model setup
        # Test API key before creating config
        # Live-validate the key+model for any BYO-key provider. Provider errors
        # are classified so a retired model is not mislabeled as a bad key.
        model_type_upper = config_data.model_type.upper()
        stored_api_key = config_data.api_key.get_secret_value()
        provider_settings = dict(config_data.settings or {})
        if model_type_upper == "CLOUDFLARE":
            stored_api_key, cloudflare_settings = _cloudflare_credential(
                stored_api_key,
                config_data.account_id,
                config_data.gateway_id,
            )
            provider_settings.update(cloudflare_settings)
        if is_known_provider(model_type_upper):
            await _validate_provider_model(
                stored_api_key,
                config_data.model_type,
                config_data.model_name,
            )


        # Create AI configuration
        ai_config_repo = AIConfigRepository(db)
        ai_config = ai_config_repo.create_config(
            org_id=current_user.organization_id,
            model_type=config_data.model_type,
            model_name=config_data.model_name,
            api_key=stored_api_key
        )
        ai_config.settings = provider_settings
        db.commit()
        db.refresh(ai_config)

        # Prepare response
        response = AISetupResponse(
            message="AI configuration completed successfully",
            config=AIConfigResponse(
                id=ai_config.id,
                organization_id=ai_config.organization_id,
                model_type=ai_config.model_type,
                model_name=ai_config.model_name,
                is_active=ai_config.is_active,
                has_api_key=bool(ai_config.encrypted_api_key),
                settings=ai_config.settings
            )
        )

        logger.info(
            f"AI setup completed for org {current_user.organization_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        logger.error(f"AI setup error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to setup AI configuration"
        )


@router.get("/config", response_model=AIConfigResponse)
async def get_organization_ai_config(
    current_user: User = Depends(require_permissions("view_ai_config")),
    db: Session = Depends(get_db)
):
    """Get active AI configuration for the current user's organization"""
    try:
        ai_config_repo = AIConfigRepository(db)
        ai_config = ai_config_repo.get_active_config(
            current_user.organization_id)

        if not ai_config:
            raise HTTPException(
                status_code=404,
                detail="No active AI configuration found"
            )

        return AIConfigResponse(
            id=ai_config.id,
            organization_id=ai_config.organization_id,
            model_type=ai_config.model_type,
            model_name=ai_config.model_name,
            is_active=ai_config.is_active,
            has_api_key=bool(ai_config.encrypted_api_key),
            settings=ai_config.settings
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting AI config: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get AI configuration"
        )


@router.put("/config", response_model=AISetupResponse)
async def update_ai_config(
    config_data: AIConfigUpdate,
    current_user: User = Depends(require_permissions("manage_ai_config")),
    db: Session = Depends(get_db)
):
    """Update AI configuration for the current user's organization"""
    try:
        logger.info(f"Updating AI config for org {current_user.organization_id}")
        
        # Validate model selection based on provider
        validate_model_selection(config_data.model_type, config_data.model_name)
        
        # Check if this is a custom model setup (not ChatterMate)
        is_custom_model = not (config_data.model_type.lower() == 'chattermate' and config_data.model_name.lower() == 'chattermate')
        
        # Check feature access for custom models
        if is_custom_model:
            check_custom_models_feature_access(current_user, db)
        
        # Get current config
        ai_config_repo = AIConfigRepository(db)
        current_config = ai_config_repo.get_active_config(current_user.organization_id)
        
        if not current_config:
            raise HTTPException(
                status_code=404,
                detail="No active AI configuration found to update"
            )
        
        # Check if using ChatterMate model
        if HAS_ENTERPRISE and config_data.model_type.lower() == 'chattermate' and config_data.model_name.lower() == 'chattermate':
            # Use Groq as provider with keys from env
            model_type = AIModelType.CHATTERMATE
            model_name = os.getenv('CHATTERMATE_MODEL_NAME', 'gpt-4o-mini')
            api_key = os.getenv('CHATTERMATE_API_KEY', '')
            
            if not api_key:
                logger.error("ChatterMate API key not found in environment")
                raise HTTPException(
                    status_code=500,
                    detail="ChatterMate API configuration missing"
                )
                
            # Update AI configuration
            updated_config = ai_config_repo.update_config(
                config_id=current_config.id,
                model_type=model_type,
                model_name=model_name,
                api_key=api_key
            )
            
            logger.info(f"ChatterMate AI config updated for org {current_user.organization_id}")
        else:
            # Validate every provider/model change. When the user keeps the
            # masked saved credential, decrypt it server-side for validation;
            # the secret is never returned to or resubmitted by the browser.
            api_key = (
                config_data.api_key.get_secret_value()
                if config_data.api_key
                else None
            )
            validation_key = api_key
            if validation_key is None and current_config.encrypted_api_key:
                validation_key = decrypt_api_key(current_config.encrypted_api_key)

            updated_settings = dict(current_config.settings or {})
            if config_data.settings:
                updated_settings.update(config_data.settings)

            model_type_upper = config_data.model_type.upper()
            if model_type_upper == "CLOUDFLARE":
                current_credentials = None
                if current_config.model_type == AIModelType.CLOUDFLARE and current_config.encrypted_api_key:
                    try:
                        current_credentials = unpack_cloudflare_credentials(
                            decrypt_api_key(current_config.encrypted_api_key)
                        )
                    except ValueError:
                        current_credentials = None
                token = api_key or (current_credentials or {}).get("api_token")
                account_id = config_data.account_id or updated_settings.get("account_id") or (current_credentials or {}).get("account_id")
                gateway_id = config_data.gateway_id or updated_settings.get("gateway_id") or (current_credentials or {}).get("gateway_id") or "default"
                if not token:
                    raise HTTPException(
                        status_code=400,
                        detail={"error": "API token required", "type": "missing_api_key", "details": "Enter a Cloudflare API token."},
                    )
                validation_key, cloudflare_settings = _cloudflare_credential(token, account_id, gateway_id)
                updated_settings.update(cloudflare_settings)
                api_key = validation_key

            if not validation_key:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "API key required",
                        "type": "missing_api_key",
                        "details": "Enter an API key for the selected provider.",
                    },
                )

            if is_known_provider(model_type_upper):
                await _validate_provider_model(
                    validation_key,
                    config_data.model_type,
                    config_data.model_name,
                )
            
            # Update AI configuration
            updated_config = ai_config_repo.update_config(
                config_id=current_config.id,
                model_type=config_data.model_type,
                model_name=config_data.model_name,
                api_key=api_key,
                settings=updated_settings,
            )
            
            logger.info(f"AI config updated for org {current_user.organization_id}")
        
        # Prepare response
        response = AISetupResponse(
            message="AI configuration updated successfully",
            config=AIConfigResponse(
                id=updated_config.id,
                organization_id=updated_config.organization_id,
                model_type=updated_config.model_type,
                model_name=updated_config.model_name,
                is_active=updated_config.is_active,
                has_api_key=bool(updated_config.encrypted_api_key),
                settings=updated_config.settings
            )
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI config update error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update AI configuration"
        )


def validate_model_selection(model_type: str, model_name: str):
    """Validate the chosen provider and that a model name is present.

    The catalog models are suggestions, not a hard allowlist — an org may enter a
    custom model ID for any known provider. So we only enforce that the provider is
    known and the model name is non-empty; the live API-key test (see setup/update)
    is what actually rejects a bad model ID.
    """

    # ChatterMate is a special case handled separately
    if model_type.upper() == "CHATTERMATE" and model_name.lower() == "chattermate":
        return True

    if not is_known_provider(model_type):
        valid_providers = ", ".join(p["value"] for p in list_providers())
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Unsupported provider",
                "type": "invalid_provider",
                "details": f"Currently only these providers are supported: {valid_providers}"
            }
        )

    if not model_name or not model_name.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid model selection",
                "type": "invalid_model",
                "details": "A model ID is required for the selected provider."
            }
        )

    return True
