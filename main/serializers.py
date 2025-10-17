from rest_framework import serializers
from .models import Sensor, SensorHealth, Feedback, MapAsset
from django.utils import timezone

class SensorSerializer(serializers.ModelSerializer):
    sensorId = serializers.CharField(source="sensor_id")
    temperatureC = serializers.FloatField(source="temperature_c")
    batteryPct = serializers.IntegerField(source="battery_pct", required=False, allow_null=True)
    lastSeenAt = serializers.DateTimeField(source="last_seen_at", required=False)  # 可选

    class Meta:
        model = Sensor
        fields = ("sensorId", "x", "y", "temperatureC", "batteryPct", "lastSeenAt")
        extra_kwargs = {
            "sensorId": {"required": True},
            "x": {"required": True},
            "y": {"required": True},
            "temperatureC": {"required": True},
        }

    def create(self, validated_data):
        validated_data.setdefault("last_seen_at", timezone.now())
        return Sensor.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        # 不允许通过更新接口更改 sensorId
        validated_data.pop("sensor_id", None)
        return super().update(instance, validated_data)


class SensorHealthSerializer(serializers.ModelSerializer):
    sensorId = serializers.CharField(source="sensor.sensor_id")
    lastSeenAt = serializers.DateTimeField(source="last_seen_at")
    latencySec = serializers.IntegerField(source="latency_sec")

    class Meta:
        model = SensorHealth
        fields = ("sensorId", "status", "lastSeenAt", "latencySec")


class _WindowSerializer(serializers.Serializer):
    minutes = serializers.IntegerField()


class FeedbackSerializer(serializers.ModelSerializer):
    sensorId = serializers.CharField(source="sensor.sensor_id", required=False, allow_null=True)
    coldCount = serializers.IntegerField(source="cold_count")
    hotCount = serializers.IntegerField(source="hot_count")
    # 将 DurationField 转为 { "minutes": N }
    window = serializers.SerializerMethodField()
    updatedAt = serializers.DateTimeField(source="updated_at")

    class Meta:
        model = Feedback
        fields = ("sensorId", "coldCount", "hotCount", "window", "updatedAt")

    def get_window(self, obj):
        minutes = int(obj.window.total_seconds() // 60) if obj.window else 15
        return {"minutes": minutes}


class MapAssetSerializer(serializers.ModelSerializer):
    assetType = serializers.CharField(source="asset_type")
    viewBox = serializers.JSONField(source="view_box")

    class Meta:
        model = MapAsset
        fields = ("assetType", "viewBox", "url")


# 组合响应（/api/overview）
class OverviewSerializer(serializers.Serializer):
    map = MapAssetSerializer(allow_null=True)
    sensors = SensorSerializer(many=True)
    health = SensorHealthSerializer(many=True)
    feedback = FeedbackSerializer(allow_null=True)