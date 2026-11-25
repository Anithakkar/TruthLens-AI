import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings


def validate() -> dict[str, object]:
    database_configured = (
        settings.database_provider == "sqlite"
        or bool(settings.supabase_url.strip() and settings.supabase_service_role_key.strip())
    )
    result = {
        "database": {
            "provider": settings.database_provider,
            "configured": database_configured,
        },
        "model": {
            "provider": settings.model_provider,
            "configured": (
                settings.model_provider == "traditional"
                or (
                    settings.model_provider == "transformer"
                    and (
                        Path(settings.transformer_model_path)
                        if Path(settings.transformer_model_path).is_absolute()
                        else Path(__file__).resolve().parents[2] / settings.transformer_model_path
                    ).joinpath("config.json").is_file()
                )
            ),
        },
        "fact_check": {
            "configured": bool(settings.google_fact_check_api_key.strip()),
        },
        "secrets": {
            "supabase_values_present": bool(settings.supabase_url.strip()),
            "service_role_key_present": bool(settings.supabase_service_role_key.strip()),
            "fact_check_key_present": bool(settings.google_fact_check_api_key.strip()),
        },
    }
    return result


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
