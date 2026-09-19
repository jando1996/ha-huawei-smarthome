"""User-contributed protocol for Huawei product 2AOQ (杜亚智能窗帘 DH6).

设备类型: 开合帘 (Curtain, deviceTypeId=01C)
制造商: 杜亚 / dooya
型号: DH6，协议: WiFi

Profile 来源:
    https://smarthome-drcn.dbankcdn.com/device/guide/2AOQ/2AOQ.json

核心服务与特征:
    mode.mode        enum RW  电机模式 (0=关/Close, 1=开/Open, 2=暂停/Pause)
    opener.target    int  RW  目标开合度 % (0~100, 100=全开)
    opener.current   int  R   当前开合度 % (0~100)
    update.action    enum W   触发升级 (0=检查新版本, 1=启动升级)
    update.version   str  R   固件版本
    netInfo.RSSI     int  R   信号强度 dB (-100~0)
    netInfo.IP       str  R   设备 IP

本适配器暴露:
    cover ×1    窗帘（开合度 + 开/关/停/定位）
    sensor ×2   固件版本 / 信号强度
    button ×1   检查固件更新
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None if value is None else int(value)
    if isinstance(value, str):
        try:
            return int(round(float(value.strip())))
        except (TypeError, ValueError):
            return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class Product2AOQAdapter:
    """杜亚 DH6 开合帘适配器。"""

    prod_id = "2AOQ"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None:
            return ()
        # cover 至少需要 opener（位置）；mode（电机命令）缺失时降级为只读位置
        if not context.has_service("opener"):
            return ()

        def cover_state(device: DeviceContext) -> Mapping[str, Any]:
            current = _as_int(device.value("opener", "current"))
            position = (
                min(max(current, 0), 100) if current is not None else None
            )
            return {
                "current_position": position,
                "is_closed": position == 0 if position is not None else None,
            }

        async def open_cover(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("mode", {"mode": 1})

        async def close_cover(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("mode", {"mode": 0})

        async def stop_cover(device: DeviceContext, _data: Mapping[str, Any]) -> None:
            await device.async_send_service("mode", {"mode": 2})

        async def set_position(device: DeviceContext, data: Mapping[str, Any]) -> None:
            position = _as_int(data.get("position"))
            if position is None:
                raise ValueError("position is required")
            position = min(max(position, 0), 100)
            await device.async_send_service("opener", {"target": position})

        entities: list[EntitySpec] = [
            EntitySpec(
                platform="cover",
                key="curtain",
                name="窗帘",
                state=cover_state,
                actions={
                    "open": open_cover,
                    "close": close_cover,
                    "stop": stop_cover,
                    "set_position": set_position,
                },
            )
        ]

        # 固件版本
        if context.has_service("update"):
            entities.append(EntitySpec(
                platform="sensor", key="update_version", name="固件版本",
                state=lambda d: {"native_value": _text(d.value("update", "version"))},
            ))

            async def _check_update(
                device: DeviceContext, _data: Mapping[str, Any]
            ) -> None:
                await device.async_send_service("update", {"action": 0})

            entities.append(EntitySpec(
                platform="button", key="update_check", name="检查固件更新",
                state=lambda d: {},
                actions={"press": _check_update},
            ))

        # 网络信息
        if context.has_service("netInfo"):
            entities.append(EntitySpec(
                platform="sensor", key="netinfo_rssi", name="信号强度",
                state=lambda d: {"native_value": _as_int(d.value("netInfo", "RSSI"))},
                metadata={"unit": "dBm", "device_class": "signal_strength",
                          "state_class": "measurement"},
            ))
            entities.append(EntitySpec(
                platform="sensor", key="netinfo_ip", name="设备 IP",
                state=lambda d: {"native_value": _text(d.value("netInfo", "IP"))},
            ))

        return tuple(entities)


ADAPTER = Product2AOQAdapter()
#（注：内容由AI生成）
