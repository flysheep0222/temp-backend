from __future__ import annotations


from django.db import models

# Create your models here.
# app: main  ->  main/models.py

from datetime import timedelta
from django.utils import timezone


class Sensor(models.Model):
    """
    传感器实体（对应 2.1 Sensor）
    """
    sensor_id = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="业务侧的传感器ID，如 S-001"
    )
    # 本地坐标（0..1 或 SVG 单位）；不强制范围约束，由前端/业务保证
    x = models.FloatField(help_text="本地坐标 x（0..1 或 SVG 单位）")
    y = models.FloatField(help_text="本地坐标 y（0..1 或 SVG 单位）")

    temperature_c = models.FloatField(help_text="温度（摄氏度）")
    battery_pct = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="电量百分比，可为空"
    )
    last_seen_at = models.DateTimeField(
        help_text="最近一次上报时间（UTC ISO8601）",
        db_index=True
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sensor"
        ordering = ["sensor_id"]

    def __str__(self) -> str:
        return f"{self.sensor_id}"


class SensorHealth(models.Model):
    """
    传感器健康状态（派生）（对应 2.2 SensorHealth）
    如果你计划实时计算，也可以把它当作物化的快照表。
    """
    class Status(models.TextChoices):
        CONNECTED = "connected", "connected"
        DISCONNECTED = "disconnected", "disconnected"

    sensor = models.OneToOneField(
        Sensor,
        related_name="health",
        on_delete=models.CASCADE,
        help_text="关联的传感器"
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        db_index=True
    )
    last_seen_at = models.DateTimeField(
        help_text="最近一次上报时间（与 Sensor.last_seen_at 对齐）",
        db_index=True
    )
    latency_sec = models.PositiveIntegerField(
        help_text="当前估算的延迟（秒）"
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sensor_health"

    def __str__(self) -> str:
        return f"{self.sensor.sensor_id} - {self.status}"


class Feedback(models.Model):
    """
    反馈汇总（硬件来源，上游聚合）（对应 2.3 Feedback）
    sensor 可为空以支持“全局或分区”级别汇总。
    window 使用 DurationField 表示“过去 N 分钟窗口”，默认 15 分钟。
    """
    sensor = models.ForeignKey(
        Sensor,
        related_name="feedbacks",
        on_delete=models.CASCADE,
        null=True, blank=True,
        help_text="可选：按传感器维度的反馈聚合"
    )
    cold_count = models.PositiveIntegerField(default=0)
    hot_count = models.PositiveIntegerField(default=0)

    window = models.DurationField(
        default=timedelta(minutes=15),
        help_text="聚合窗口大小（默认15分钟）"
    )
    updated_at = models.DateTimeField(
        help_text="本条聚合的更新时间（UTC ISO8601）",
        db_index=True
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "feedback"
        indexes = [
            models.Index(fields=["updated_at"]),
            models.Index(fields=["sensor", "updated_at"]),
        ]

    def __str__(self) -> str:
        scope = self.sensor.sensor_id if self.sensor_id else "GLOBAL"
        return f"Feedback<{scope}> @ {self.updated_at.isoformat()}"


class MapAsset(models.Model):
    """
    地图资源（对应 2.4 MapAsset）
    viewBox 仅对 SVG 有意义，使用 JSONField 存 [x,y,w,h]。
    """
    class AssetType(models.TextChoices):
        SVG = "svg", "svg"
        PNG = "png", "png"
        JPG = "jpg", "jpg"

    asset_type = models.CharField(
        max_length=8,
        choices=AssetType.choices,
        db_index=True
    )
    view_box = models.JSONField(
        null=True, blank=True,
        help_text="仅 SVG 使用的视窗，如 [0,0,1000,700]"
    )
    # 资源地址：相对或绝对路径，保留为 CharField 以兼容相对URL
    url = models.CharField(max_length=512)

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "map_asset"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.asset_type} -> {self.url}"
