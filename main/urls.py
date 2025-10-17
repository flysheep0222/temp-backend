from django.urls import path
from .api import MapView, SensorsView, HealthView, FeedbackView, OverviewView

urlpatterns = [
    path("map", MapView.as_view(), name="api-map"),
    path("sensors", SensorsView.as_view(), name="api-sensors"),
    path("sensors/<str:sensor_id>", SensorsView.as_view(), name="sensor-update"),
    path("health", HealthView.as_view(), name="api-health"),
    path("feedback", FeedbackView.as_view(), name="feedback-list"),
    path("feedback/<int:pk>", FeedbackView.as_view(), name="feedback-detail"),
    path("overview", OverviewView.as_view(), name="api-overview"),  # 便捷汇总
]
