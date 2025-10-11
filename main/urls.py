from django.urls import path
from .api import MapView, SensorsView, HealthView, FeedbackView, OverviewView

urlpatterns = [
    path("map", MapView.as_view(), name="api-map"),
    path("sensors", SensorsView.as_view(), name="api-sensors"),
    path("health", HealthView.as_view(), name="api-health"),
    path("feedback", FeedbackView.as_view(), name="api-feedback"),
    path("overview", OverviewView.as_view(), name="api-overview"),  # 便捷汇总
]
