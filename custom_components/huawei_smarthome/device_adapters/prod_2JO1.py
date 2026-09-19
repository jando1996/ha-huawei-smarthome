"""User-contributed protocol for Huawei product 2JO1 (电小酷智能转换插座 CP1-HW).

设备类型: 转换插座 (Socket, deviceTypeId=01D)
制造商: 深圳市酷客智能 / cuco
型号: CP1-HW，协议: WiFi

Profile 来源:
    https://smarthome-drcn.dbankcdn.com/device/guide/2JO1/2JO1.json

核心服务与特征:
    switch.on                  bool RW  电源主开关 (1开 0关)
    indicator.on               bool RW  指示灯开关
    childLockSwitch.on          bool RW  童锁
    ProtectionSwitch.ProtectionSwitch bool RW  充电保护开关
    memorySwitch.status         enum RW  断电记忆 (0关 1开 2保持上次状态)
    power.current               int  R   当前功率 W (0~99999)
    electric.current            int  R   电流 mA
    electric.totalConsum        int  R   总用电量 kWh
    commonFaultDetection.code   enum R   故障码 (0正常 100过载 101过温 102过压)
    commonFaultDetection.status bool R   是否有故障
    ChargingProtection.ProtectionPower  int RW  保护功率 W (0~200, step2)
    ChargingProtection.ProtectDuration  int RW  保护时间 分 (0~300, step5)
    update.action / version     W/R      OTA
    netInfo.RSSI / IP          int/str R

本适配器暴露:
    switch ×4   电源 / 指示灯 / 童锁 / 充电保护
    select ×1   断电记忆
    number ×2   保护功率 / 保护时间
    sensor ×6   功率 / 电流 / 总用电量 / 故障码 / 固件版本 / 信号强度 / IP
    binary_sensor ×1  故障
    button ×1   检查固件更新
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


_FAULT_CODE = {
    0: "正常",
    100: "过载保护",
    101: "过温保护",
    102: "过压保护",
}
_MEMORY_OPTIONS = ["关", "开", "保持上次状态"]
_MEMORY_VALUE = {name: idx for idx, name in enumerate(_MEMORY_OPTIONS)}
_MEMORY_NAME = {idx: name for idx, name in enumerate(_MEMORY_OPTIONS)}


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


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.casefold() in {"1", "true", "on"}:
            return True
        if value.casefold() in {"0", "false", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class Product2JO1Adapter:
    """电小酷 CP1-HW 转换插座适配器。"""

    prod_id = "2JO1"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("switch"):
            return ()

        entities: list[EntitySpec] = []

        # ---- switch ----
        switch_fields: tuple[tuple[str, str, str], ...] = (
            ("switch", "on", "电源"),
            ("indicator", "on", "指示灯"),
            ("childLockSwitch", "on", "童锁"),
            ("ProtectionSwitch", "ProtectionSwitch", "充电保护"),
        )
        for sid, field, name in switch_fields:
            if not context.has_service(sid):
                continue

            def make_state(_sid: str, _field: str):
                def reader(device: DeviceContext) -> Mapping[str, Any]:
                    return {"is_on": _as_bool(device.value(_sid, _field))}
                return reader

            def make_on(_sid: str, _field: str, on: int):
                async def action(device: DeviceContext, _data: Mapping[str, Any]) -> None:
                    await device.async_send_service(_sid, {_field: on})
                return action

            entities.append(EntitySpec(
                platform="switch", key=f"{sid}_{field}", name=name,
                state=make_state(sid, field),
                actions={
                    "turn_on": make_on(sid, field, 1),
                    "turn_off": make_on(sid, field, 0),
                },
            ))

        # ---- select: 断电记忆 ----
        if context.has_service("memorySwitch"):
            def memory_state(device: DeviceContext) -> Mapping[str, Any]:
                val = _as_int(device.value("memorySwitch", "status"))
                return {"current_option": _MEMORY_NAME.get(val, "关")}

            async def set_memory(device: DeviceContext, data: Mapping[str, Any]) -> None:
                val = _MEMORY_VALUE.get(str(data.get("option")))
                if val is None:
                    raise ValueError(f"unsupported memory: {data.get('option')!r}")
                await device.async_send_service("memorySwitch", {"status": val})

            entities.append(EntitySpec(
                platform="select", key="memory_switch", name="断电记忆",
                state=memory_state,
                metadata={"options": list(_MEMORY_OPTIONS)},
                actions={"select_option": set_memory},
            ))

        # ---- sensor: 功率 / 电流 / 电量 ----
        if context.has_service("power"):
            entities.append(EntitySpec(
                platform="sensor", key="power_current", name="当前功率",
                state=lambda d: {"native_value": _as_int(d.value("power", "current"))},
                metadata={"unit": "W", "device_class": "power",
                          "state_class": "measurement"},
            ))
        if context.has_service("electric"):
            entities.append(EntitySpec(
                platform="sensor", key="electric_current", name="电流",
                state=lambda d: {"native_value": _as_int(d.value("electric", "current"))},
                metadata={"unit": "mA", "device_class": "current",
                          "state_class": "measurement"},
            ))
            entities.append(EntitySpec(
                platform="sensor", key="electric_total", name="总用电量",
                state=lambda d: {"native_value": _as_int(d.value("electric", "totalConsum"))},
                metadata={"unit": "kWh", "device_class": "energy",
                          "state_class": "total_increasing"},
            ))

        # ---- 故障 ----
        if context.has_service("commonFaultDetection"):
            entities.append(EntitySpec(
                platform="sensor", key="fault_code", name="故障码",
                state=lambda d: {"native_value": _FAULT_CODE.get(
                    _as_int(d.value("commonFaultDetection", "code")), "正常")},
            ))
            entities.append(EntitySpec(
                platform="binary_sensor", key="fault", name="故障",
                state=lambda d: {
                    "is_on": _as_int(d.value("commonFaultDetection", "status")) == 1},
                metadata={"device_class": "problem"},
            ))

        # ---- number: 充电保护参数 ----
        if context.has_service("ChargingProtection"):
            entities.append(EntitySpec(
                platform="number", key="protect_power", name="保护功率",
                state=lambda d: {"native_value": _as_int(
                    d.value("ChargingProtection", "ProtectionPower"))},
                metadata={"min": 0, "max": 200, "step": 2, "unit": "W"},
                actions={"set_value": lambda ctx, data: _set_protect(
                    ctx, data, "ProtectionPower", 0, 200)},
            ))
            entities.append(EntitySpec(
                platform="number", key="protect_duration", name="保护时间",
                state=lambda d: {"native_value": _as_int(
                    d.value("ChargingProtection", "ProtectDuration"))},
                metadata={"min": 0, "max": 300, "step": 5, "unit": "分"},
                actions={"set_value": lambda ctx, data: _set_protect(
                    ctx, data, "ProtectDuration", 0, 300)},
            ))

        # ---- OTA ----
        # 固件版本仅在设备实际上报过 version 时才建（很多插座初版不上报，否则恒为"未知"）
        if context.has_service("update"):
            if "version" in context.service_state("update"):
                entities.append(EntitySpec(
                    platform="sensor", key="firmware_version", name="固件版本",
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

        # ---- 网络信息（仅在设备实际上报过对应字段时生成）----
        if context.has_service("netInfo"):
            net_state = context.service_state("netInfo")
            if "RSSI" in net_state:
                entities.append(EntitySpec(
                    platform="sensor", key="netinfo_rssi", name="信号强度",
                    state=lambda d: {"native_value": _as_int(d.value("netInfo", "RSSI"))},
                    metadata={"unit": "dBm", "device_class": "signal_strength",
                              "state_class": "measurement"},
                ))
            if "IP" in net_state:
                entities.append(EntitySpec(
                    platform="sensor", key="netinfo_ip", name="设备 IP",
                    state=lambda d: {"native_value": _text(d.value("netInfo", "IP"))},
                ))

        return tuple(entities)


async def _set_protect(
    context: DeviceContext,
    data: Mapping[str, Any],
    field: str,
    lo: int,
    hi: int,
) -> None:
    value = _as_int(data.get("value"))
    if value is None:
        return
    value = max(lo, min(hi, value))
    await context.async_send_service("ChargingProtection", {field: value})


ADAPTER = Product2JO1Adapter()
#（注：内容由AI生成）
