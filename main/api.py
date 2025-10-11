from datetime import timedelta
from django.db.models import Max, Sum, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Sensor, SensorHealth, Feedback, MapAsset
from .serializers import (
    SensorSerializer, SensorHealthSerializer, FeedbackSerializer,
    MapAssetSerializer, OverviewSerializer
)


# 统一错误输出：{"error":{"code":"...","message":"..."}}
def exception_handler(exc, context):
    from rest_framework.views import exception_handler as drf_handler
    resp = drf_handler(exc, context)
    if resp is None:
        return Response({"error": {"code": "INTERNAL_ERROR", "message": str(exc)}},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    # 覆盖为统一结构
    message = resp.data
    if isinstance(message, dict) and "detail" in message:
        message = message["detail"]
    return Response({"error": {"code": "BAD_REQUEST", "message": message}}, status=resp.status_code)


class MapView(APIView):
    """
    GET /api/map
    - 返回最新 MapAsset（按 updated_at）
    - 附带坐标系元数据（origin/axis）
    """
    def get(self, request):
        asset = MapAsset.objects.order_by("-updated_at", "-id").first()
        data = MapAssetSerializer(asset).data if asset else None
        meta = {
            "coordinateMeta": {
                "origin": "top-left",
                "xAxis": "right",
                "yAxis": "down"
            }
        }
        return Response({"map": data, **meta})


class SensorsView(APIView):
    """
    GET /api/sensors
    - 返回全部传感器（可按 ?updatedWithin=minutes 过滤）
    """
    def get(self, request):
        qs = Sensor.objects.all().order_by("sensor_id")
        minutes = request.query_params.get("updatedWithin")
        if minutes:
            try:
                m = int(minutes)
                since = timezone.now() - timedelta(minutes=m)
                qs = qs.filter(last_seen_at__gte=since)
            except ValueError:
                return Response({"error": {"code": "BAD_REQUEST", "message": "updatedWithin must be integer minutes"}},
                                status=status.HTTP_400_BAD_REQUEST)
        return Response(SensorSerializer(qs, many=True).data)


class HealthView(APIView):
    """
    GET /api/health
    - 默认返回所有 SensorHealth
    - ?aggregate=true 时返回聚合统计：{"connected": N, "disconnected": M}
    """
    def get(self, request):
        if request.query_params.get("aggregate") in ("1", "true", "True"):
            counts = (SensorHealth.objects
                      .values("status")
                      .order_by()
                      .annotate(n=models.Count("id")))
            agg = {"connected": 0, "disconnected": 0}
            for row in counts:
                agg[row["status"]] = row["n"]
            return Response({"counts": agg})
        qs = SensorHealth.objects.select_related("sensor").order_by("sensor__sensor_id")
        return Response(SensorHealthSerializer(qs, many=True).data)


class FeedbackView(APIView):
    """
    GET /api/feedback
    - 优先返回“全局聚合”的最新一条（sensor is NULL）
    - 若没有，则对“最近窗口”内的各传感器最新记录求和
    - 支持 ?window=15（分钟）
    """
    def get(self, request):
        # 先找全局聚合
        global_fb = (Feedback.objects
                     .filter(sensor__isnull=True)
                     .order_by("-updated_at", "-id")
                     .first())
        if global_fb:
            return Response(FeedbackSerializer(global_fb).data)

        # 没有全局记录 → 汇总计算
        minutes = request.query_params.get("window", 15)
        try:
            minutes = int(minutes)
        except ValueError:
            return Response({"error": {"code": "BAD_REQUEST", "message": "window must be integer minutes"}},
                            status=status.HTTP_400_BAD_REQUEST)

        since = timezone.now() - timedelta(minutes=minutes)

        # 取每个传感器在窗口内的“最新一条”并累加
        # 方案：先找每个传感器的最新时间，再二次过滤求和
        latest_per_sensor = (Feedback.objects
                             .filter(sensor__isnull=False, updated_at__gte=since)
                             .values("sensor_id")
                             .annotate(latest=Max("updated_at")))

        if not latest_per_sensor:
            # 空集也返回结构化数据
            payload = {
                "sensorId": None,
                "coldCount": 0,
                "hotCount": 0,
                "window": {"minutes": minutes},
                "updatedAt": timezone.now(),
            }
            return Response(payload)

        q_objects = Q()
        for row in latest_per_sensor:
            q_objects |= Q(sensor_id=row["sensor_id"], updated_at=row["latest"])

        selected = Feedback.objects.filter(q_objects)
        cold = selected.aggregate(s=Sum("cold_count"))["s"] or 0
        hot = selected.aggregate(s=Sum("hot_count"))["s"] or 0
        latest = selected.aggregate(m=Max("updated_at"))["m"] or timezone.now()

        payload = {
            "sensorId": None,
            "coldCount": cold,
            "hotCount": hot,
            "window": {"minutes": minutes},
            "updatedAt": latest,
        }
        return Response(payload)


class OverviewView(APIView):
    """
    GET /api/overview  （可选，方便前端一次拿全量）
    {
      "map": {...},
      "sensors": [...],
      "health": [...],
      "feedback": {...}
    }
    """
    def get(self, request):
        asset = MapAsset.objects.order_by("-updated_at", "-id").first()
        sensors = Sensor.objects.all().order_by("sensor_id")
        health = SensorHealth.objects.select_related("sensor").order_by("sensor__sensor_id")

        # 反馈：沿用 /api/feedback 的逻辑
        global_fb = (Feedback.objects
                     .filter(sensor__isnull=True)
                     .order_by("-updated_at", "-id")
                     .first())
        if global_fb:
            fb_payload = FeedbackSerializer(global_fb).data
        else:
            # 复用 FeedbackView 的“汇总计算”
            minutes = 15
            since = timezone.now() - timedelta(minutes=minutes)
            latest_per_sensor = (Feedback.objects
                                 .filter(sensor__isnull=False, updated_at__gte=since)
                                 .values("sensor_id")
                                 .annotate(latest=Max("updated_at")))
            if latest_per_sensor:
                q = Q()
                for row in latest_per_sensor:
                    q |= Q(sensor_id=row["sensor_id"], updated_at=row["latest"])
                selected = Feedback.objects.filter(q)
                cold = selected.aggregate(s=Sum("cold_count"))["s"] or 0
                hot = selected.aggregate(s=Sum("hot_count"))["s"] or 0
                latest = selected.aggregate(m=Max("updated_at"))["m"] or timezone.now()
                fb_payload = {
                    "sensorId": None,
                    "coldCount": cold,
                    "hotCount": hot,
                    "window": {"minutes": minutes},
                    "updatedAt": latest,
                }
            else:
                fb_payload = {
                    "sensorId": None,
                    "coldCount": 0,
                    "hotCount": 0,
                    "window": {"minutes": 15},
                    "updatedAt": timezone.now(),
                }

        data = OverviewSerializer({
            "map": MapAssetSerializer(asset).data if asset else None,
            "sensors": SensorSerializer(sensors, many=True).data,
            "health": SensorHealthSerializer(health, many=True).data,
            "feedback": fb_payload
        }).data

        # 附上坐标元数据
        data["coordinateMeta"] = {
            "origin": "top-left",
            "xAxis": "right",
            "yAxis": "down"
        }
        return Response(data)
