from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

from main.models import Sensor, SensorHealth, Feedback, MapAsset


class APISmokeTests(APITestCase):
    def setUp(self):
        # 基础时间
        self.now = timezone.now()

        # 地图
        self.asset = MapAsset.objects.create(
            asset_type="svg",
            view_box=[0, 0, 1000, 700],
            url="/assets/maps/placeholder.svg",
        )

        # 传感器
        self.s1 = Sensor.objects.create(
            sensor_id="S-001",
            x=0.12, y=0.45,
            temperature_c=23.5,
            battery_pct=85,
            last_seen_at=self.now - timedelta(seconds=20),
        )
        self.s2 = Sensor.objects.create(
            sensor_id="S-002",
            x=0.72, y=0.15,
            temperature_c=26.1,
            battery_pct=None,
            last_seen_at=self.now - timedelta(minutes=30),
        )

        # 健康
        SensorHealth.objects.create(
            sensor=self.s1,
            status="connected",
            last_seen_at=self.s1.last_seen_at,
            latency_sec=12,
        )
        SensorHealth.objects.create(
            sensor=self.s2,
            status="disconnected",
            last_seen_at=self.s2.last_seen_at,
            latency_sec=999,
        )

        # 反馈：每传感器最新一条
        Feedback.objects.create(
            sensor=self.s1,
            cold_count=2,
            hot_count=1,
            updated_at=self.now - timedelta(minutes=1),
        )
        Feedback.objects.create(
            sensor=self.s2,
            cold_count=1,
            hot_count=0,
            updated_at=self.now - timedelta(minutes=2),
        )
        # 可选：全局聚合一条（若存在，将优先被 /api/feedback 返回）
        # Feedback.objects.create(
        #     sensor=None,
        #     cold_count=10,
        #     hot_count=5,
        #     updated_at=self.now - timedelta(seconds=10),
        # )

    def test_map(self):
        url = "/api/map"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("map", resp.data)
        self.assertEqual(resp.data["map"]["assetType"], "svg")
        self.assertEqual(resp.data["map"]["viewBox"], [0, 0, 1000, 700])
        self.assertIn("coordinateMeta", resp.data)
        self.assertEqual(resp.data["coordinateMeta"]["origin"], "top-left")

    def test_sensors_all(self):
        url = "/api/sensors"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)
        # 字段风格校验（驼峰）
        s = resp.data[0]
        self.assertIn("sensorId", s)
        self.assertIn("temperatureC", s)
        self.assertIn("lastSeenAt", s)

    def test_sensors_filter_updated_within(self):
        # 只应返回 10 分钟内更新的传感器（S-001）
        url = "/api/sensors?updatedWithin=10"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {x["sensorId"] for x in resp.data}
        self.assertSetEqual(ids, {"S-001"})

    def test_health_list(self):
        url = "/api/health"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)
        # 字段风格
        self.assertIn("sensorId", resp.data[0])
        self.assertIn("latencySec", resp.data[0])

    def test_health_aggregate(self):
        url = "/api/health?aggregate=true"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("counts", resp.data)
        self.assertEqual(resp.data["counts"]["connected"], 1)
        self.assertEqual(resp.data["counts"]["disconnected"], 1)

    def test_feedback_auto_aggregate_without_global(self):
        # 未创建全局反馈时，应自动聚合各传感器“最新一条”
        url = "/api/feedback"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("coldCount", resp.data)
        self.assertIn("hotCount", resp.data)
        # 2+1 vs 1+0 → cold=3, hot=1
        self.assertEqual(resp.data["coldCount"], 3)
        self.assertEqual(resp.data["hotCount"], 1)
        self.assertEqual(resp.data["window"]["minutes"], 15)  # 默认

    def test_feedback_global_preferred(self):
        # 有全局聚合则优先生效
        Feedback.objects.create(
            sensor=None, cold_count=9, hot_count=9, updated_at=self.now
        )
        url = "/api/feedback"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["coldCount"], 9)
        self.assertEqual(resp.data["hotCount"], 9)

    def test_overview_bundle(self):
        url = "/api/overview"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("map", resp.data)
        self.assertIn("sensors", resp.data)
        self.assertIn("health", resp.data)
        self.assertIn("feedback", resp.data)
        # 坐标元数据
        self.assertIn("coordinateMeta", resp.data)
        self.assertEqual(resp.data["coordinateMeta"]["yAxis"], "down")
