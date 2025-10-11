from django.contrib import admin

# Register your models here.
from .models import Sensor, SensorHealth, Feedback, MapAsset

@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ("sensor_id", "x", "y", "temperature_c", "battery_pct", "last_seen_at")
    search_fields = ("sensor_id",)
    list_filter = ("battery_pct",)

@admin.register(SensorHealth)
class SensorHealthAdmin(admin.ModelAdmin):
    list_display = ("sensor", "status", "last_seen_at", "latency_sec", "updated_at")
    list_filter = ("status",)
    search_fields = ("sensor__sensor_id",)

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("sensor", "cold_count", "hot_count", "window", "updated_at")
    list_filter = ("sensor",)
    search_fields = ("sensor__sensor_id",)

@admin.register(MapAsset)
class MapAssetAdmin(admin.ModelAdmin):
    list_display = ("asset_type", "url", "view_box", "updated_at")
    list_filter = ("asset_type",)
    search_fields = ("url",)
