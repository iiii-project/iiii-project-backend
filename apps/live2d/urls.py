from django.urls import path, re_path
from django.views.static import serve

from . import views
from .engine.paths import AVATARS_DIR, BACKGROUNDS_DIR, LIVE2D_MODELS_DIR, RUNTIME_CACHE_DIR

# Static serving here mirrors upstream open_llm_vtuber's StaticFiles mounts
# (server.py). Fine for the current dev/single-instance deployment; production
# should eventually have nginx (or whitenoise) serve these paths directly.
urlpatterns = [
    path("live2d-models/info", views.live2d_models_info),
    re_path(r"^live2d-models/(?P<path>.*)$", serve, {"document_root": LIVE2D_MODELS_DIR}),
    re_path(r"^avatars/(?P<path>.*)$", serve, {"document_root": AVATARS_DIR}),
    re_path(r"^bg/(?P<path>.*)$", serve, {"document_root": BACKGROUNDS_DIR}),
    re_path(r"^cache/(?P<path>.*)$", serve, {"document_root": RUNTIME_CACHE_DIR}),
]
