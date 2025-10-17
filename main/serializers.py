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
    sensorId  = serializers.CharField(source="sensor.sensor_id", required=False)
    hotCount  = serializers.IntegerField(source="hot_count",  required=False, min_value=0)
    coldCount = serializers.IntegerField(source="cold_count", required=False, min_value=0)

    class Meta:
        model  = Feedback
        fields = ("sensorId", "hotCount", "coldCount")

    def update(self, instance, validated_data):
        # 处理 sensorId（可选）
        sensor_data = validated_data.pop("sensor", None)  # 来自 source="sensor.sensor_id"
        if sensor_data and "sensor_id" in sensor_data:
            sid = sensor_data["sensor_id"]
            try:
                instance.sensor = Sensor.objects.get(sensor_id=sid)
            except Sensor.DoesNotExist:
                raise serializers.ValidationError({"sensorId": "Sensor not found."})

        # 处理计数
        if "hot_count" in validated_data:
            instance.hot_count = validated_data["hot_count"]
        if "cold_count" in validated_data:
            instance.cold_count = validated_data["cold_count"]

        instance.save()
        return instance


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