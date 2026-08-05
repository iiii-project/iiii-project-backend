import json
import os

from django.http import JsonResponse

from .engine.paths import DATA_DIR, LIVE2D_MODELS_DIR


def live2d_models_info(request):
    """Port of upstream open_llm_vtuber's `GET /live2d-models/info` (routes.py)."""
    if not LIVE2D_MODELS_DIR.exists():
        return JsonResponse({"error": "Live2D models directory not found"}, status=404)

    configured_models = {}
    model_dict_path = DATA_DIR / "model_dict.json"
    if model_dict_path.exists():
        try:
            with open(model_dict_path, encoding="utf-8") as f:
                configured_models = {model["url"]: model for model in json.load(f)}
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            pass

    characters = []
    for root, _dirs, files in os.walk(LIVE2D_MODELS_DIR):
        for filename in files:
            if not filename.endswith(".model3.json"):
                continue
            model3_file = os.path.join(root, filename)
            relative_model_path = os.path.relpath(model3_file, LIVE2D_MODELS_DIR).replace("\\", "/")
            model_name = relative_model_path.removesuffix(".model3.json")
            model_url = f"/live2d-models/{relative_model_path}"

            model_info = dict(
                configured_models.get(
                    model_url,
                    {
                        "name": model_name,
                        "description": os.path.dirname(relative_model_path),
                        "url": model_url,
                        "kScale": 0.5,
                        "initialXshift": 0,
                        "initialYshift": 0,
                        "idleMotionGroupName": "Idle",
                        "emotionMap": {},
                    },
                )
            )
            model_info["name"] = model_name
            model_info["url"] = model_url

            try:
                with open(model3_file, encoding="utf-8") as f:
                    model3_data = json.load(f)
                expressions = model3_data.get("FileReferences", {}).get("Expressions", [])
                model_info["emotionMap"] = {
                    expr.get("Name", f"expression_{i}"): i for i, expr in enumerate(expressions)
                }
            except (OSError, json.JSONDecodeError):
                pass

            characters.append(
                {"name": model_name, "avatar": None, "model_path": model_url, "model_info": model_info}
            )

    return JsonResponse({"type": "live2d-models/info", "count": len(characters), "characters": characters})
