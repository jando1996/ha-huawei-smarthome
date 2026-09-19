"""User-contributed protocol for Huawei product 20KX (海曼 HEIMAN 空气质量检测仪).

设备类型: 空气检测器 (Air Detector, deviceTypeId=006)
制造商: 海曼科技 / HEIMAN
型号: WS2AQ，协议: WiFi

Profile 来源:
    https://smarthome-drcn.dbankcdn.com/device/guide/20KX/20KX.json

核心服务与特征:
    temperature.current      int  R   当前温度 ℃ (-40~100)
    temperature.level        enum R   温度等级 (1寒冷 2冷 3舒适 4热 5酷热)
    humidity.current         int  R   当前湿度 % (0~100)
    humidity.level           enum R   湿度等级 (1干燥 2略干 3舒适 4潮湿)
    pm25.current             int  R   PM2.5 µg/m³ (0~1000)
    pm25.level               enum R   PM2.5等级 (1优 2良 3轻 4中 5重 6严重)
    hcho.current             int  R   甲醛 µg/m³ (0~1000)
    hcho.level               enum R   甲醛等级 (1理想 2一般 3有害 4严重有害)
    noise.current            int  R   噪音 dB (0~500)
    power.current            int  R   电量 % (0~100)
    power.mode               enum R   充电状态 (0未充电 1充电中 2充电完成)
    AlarmState.AlarmState    enum R   报警状态 (0正常 .. 9甲醛轻度报警)
    netInfo.RSSI             int  R   信号强度 dB (-100~0)
    netInfo.IP               str  R   设备 IP
    update.version           str  R   固件版本
    Identify.time            enum RW  闪烁时间 (0~4 -> 0/30/60/90/120s)
    Istempc.Istempc          enum RW  温度单位 (0℉ 1℃)
    Language.Language        enum RW  设备语言 (0中文 1英文)
    Disturb.Disturb          bool RW  勿扰模式
    TemperatureThr.MaxEn    bool RW  高温报警使能
    TemperatureThr.MinEn     bool RW  低温报警使能
    TemperatureThr.MaxThr   int  RW  高温报警值 ℃ (-50~100)
    TemperatureThr.MinThr   int  RW  低温报警值 ℃ (-50~100)
    HumidityThr.MaxEn       bool RW  潮湿报警使能
    HumidityThr.MinEn       bool RW  干燥报警使能
    HumidityThr.MaxThr      int  RW  潮湿报警值 % (0~100)
    HumidityThr.MinThr      int  RW  干燥报警值 % (0~100)
    update.action            enum W   触发升级检查 (0检查新版本 1启动升级)

本适配器暴露:
    sensor ×15  温度/湿度/PM2.5/甲醛/噪音/电量/各等级/报警/充电/信号/IP/版本
    select ×3   温度单位 / 设备语言 / 闪烁时间
    switch ×5   勿扰 / 高温报警 / 低温报警 / 潮湿报警 / 干燥报警
    number ×4   高低温报警值 / 潮干燥报警值
    button ×1   检查固件更新
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


# ---- 枚举映射（设备上报值 -> 中文显示名） --------------------------------

_TEMP_LEVEL = {1: "寒冷", 2: "冷", 3: "舒适", 4: "热", 5: "酷热"}
_HUM_LEVEL = {1: "干燥", 2: "略干", 3: "舒适", 4: "潮湿"}
_PM25_LEVEL = {1: "优", 2: "良", 3: "轻度污染", 4: "中度污染",
               5: "重度污染", 6: "严重污染"}
_HCHO_LEVEL = {1: "理想", 2: "一般", 3: "有害", 4: "严重有害"}
_CHARGE_MODE = {0: "未充电", 1: "充电中", 2: "充电完成"}
_ALARM_STATE = {
    0: "正常",
    1: "PM2.5超标报警",
    2: "甲醛超标报警",
    3: "温度过高报警",
    4: "温度过低报警",
    5: "湿度过高报警",
    6: "湿度过低报警",
    7: "低压报警",
    8: "PM2.5轻度报警",
    9: "甲醛轻度报警",
}

# select 选项（显示名 <-> 设备枚举值）
_TEMP_UNIT_OPTIONS = ["℉", "℃"]
_TEMP_UNIT_VALUE = {"℉": 0, "℃": 1}
_TEMP_UNIT_NAME = {0: "℉", 1: "℃"}

_LANG_OPTIONS = ["中文", "English"]
_LANG_VALUE = {"中文": 0, "English": 1}
_LANG_NAME = {0: "中文", 1: "English"}

_IDENTIFY_OPTIONS = ["0s", "30s", "60s", "90s", "120s"]
_IDENTIFY_VALUE = {name: idx for idx, name in enumerate(_IDENTIFY_OPTIONS)}
_IDENTIFY_NAME = {idx: name for idx, name in enumerate(_IDENTIFY_OPTIONS)}


# ---- 工具函数 ------------------------------------------------------------

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


# ---- 通用 state 读取闭包 ------------------------------------------------

def _num_state(sid: str, field: str):
    def reader(device: DeviceContext) -> Mapping[str, Any]:
        return {"native_value": _as_int(device.value(sid, field))}
    return reader


def _enum_text_state(sid: str, field: str, mapping: dict[int, str], fallback: str = "未知"):
    def reader(device: DeviceContext) -> Mapping[str, Any]:
        val = _as_int(device.value(sid, field))
        return {"native_value": mapping.get(val, fallback if val is None else str(val))}
    return reader


def _str_state(sid: str, field: str):
    def reader(device: DeviceContext) -> Mapping[str, Any]:
        return {"native_value": _text(device.value(sid, field))}
    return reader


def _switch_state(sid: str, field: str):
    def reader(device: DeviceContext) -> Mapping[str, Any]:
        return {"is_on": _as_bool(device.value(sid, field))}
    return reader


# ---- 动作函数 ------------------------------------------------------------

async def _set_bool(context: DeviceContext, data: Mapping[str, Any],
                    sid: str, field: str) -> None:
    is_on = data.get("is_on")
    if is_on is None:
        return
    await context.async_send_service(sid, {field: 1 if is_on else 0})


def _make_set_bool(sid: str, field: str):
    async def action(context: DeviceContext, data: Mapping[str, Any]) -> None:
        await _set_bool(context, data, sid, field)
    return action


def _make_toggle(sid: str, field: str, on: int):
    async def action(context: DeviceContext, _data: Mapping[str, Any]) -> None:
        await context.async_send_service(sid, {field: on})
    return action


def _make_set_number(sid: str, field: str, lo: int, hi: int):
    async def action(context: DeviceContext, data: Mapping[str, Any]) -> None:
        value = _as_int(data.get("value"))
        if value is None:
            return
        value = max(lo, min(hi, value))
        await context.async_send_service(sid, {field: value})
    return action


def _make_select_option(value_map: dict[str, int], sid: str, field: str):
    async def action(context: DeviceContext, data: Mapping[str, Any]) -> None:
        val = value_map.get(str(data.get("option")))
        if val is None:
            raise ValueError(f"unsupported option: {data.get('option')!r}")
        await context.async_send_service(sid, {field: val})
    return action


# ---- 适配器 ---------------------------------------------------------------

class Product20KXAdapter:
    """海曼 WS2AQ 空气质量检测仪适配器。"""

    prod_id = "20KX"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None:
            return ()

        entities: list[EntitySpec] = []

        def add_sensor(sid, field, name, *, mapping=None, unit=None,
                       device_class=None, text=False):
            if not context.has_service(sid):
                return
            if mapping is not None:
                state = _enum_text_state(sid, field, mapping)
            elif text:
                state = _str_state(sid, field)
            else:
                state = _num_state(sid, field)
            metadata: dict[str, Any] = {}
            if unit:
                metadata["unit"] = unit
            if device_class:
                metadata["device_class"] = device_class
            if not (mapping is not None or text):
                metadata["state_class"] = "measurement"
            entities.append(
                EntitySpec(platform="sensor", key=f"{sid}_{field}",
                           name=name, state=state, metadata=metadata)
            )

        # 温湿度
        add_sensor("temperature", "current", "温度",
                   unit="°C", device_class="temperature")
        add_sensor("temperature", "level", "温度等级", mapping=_TEMP_LEVEL)
        add_sensor("humidity", "current", "湿度",
                   unit="%", device_class="humidity")
        add_sensor("humidity", "level", "湿度等级", mapping=_HUM_LEVEL)
        # 空气质量
        add_sensor("pm25", "current", "PM2.5",
                   unit="µg/m³", device_class="pm25")
        add_sensor("pm25", "level", "PM2.5等级", mapping=_PM25_LEVEL)
        add_sensor("hcho", "current", "甲醛", unit="µg/m³")
        add_sensor("hcho", "level", "甲醛等级", mapping=_HCHO_LEVEL)
        add_sensor("noise", "current", "噪音",
                   unit="dB", device_class="sound_pressure")
        # 电量 / 充电
        add_sensor("power", "current", "电量",
                   unit="%", device_class="battery")
        add_sensor("power", "mode", "充电状态", mapping=_CHARGE_MODE)
        # 报警
        add_sensor("AlarmState", "AlarmState", "报警状态", mapping=_ALARM_STATE)
        # 网络
        add_sensor("netInfo", "RSSI", "信号强度",
                   unit="dBm", device_class="signal_strength")
        add_sensor("netInfo", "IP", "设备 IP", text=True)
        # 固件
        add_sensor("update", "version", "固件版本", text=True)

        # ---- select：可写枚举 ----
        if context.has_service("Istempc"):
            entities.append(EntitySpec(
                platform="select", key="istempc", name="温度单位",
                state=lambda d: {"current_option": _TEMP_UNIT_NAME.get(
                    _as_int(d.value("Istempc", "Istempc")), "℃")},
                metadata={"options": _TEMP_UNIT_OPTIONS},
                actions={"select_option": _make_select_option(
                    _TEMP_UNIT_VALUE, "Istempc", "Istempc")},
            ))
        if context.has_service("Language"):
            entities.append(EntitySpec(
                platform="select", key="language", name="设备语言",
                state=lambda d: {"current_option": _LANG_NAME.get(
                    _as_int(d.value("Language", "Language")), "中文")},
                metadata={"options": _LANG_OPTIONS},
                actions={"select_option": _make_select_option(
                    _LANG_VALUE, "Language", "Language")},
            ))
        if context.has_service("Identify"):
            entities.append(EntitySpec(
                platform="select", key="identify_time", name="闪烁时间",
                state=lambda d: {"current_option": _IDENTIFY_NAME.get(
                    _as_int(d.value("Identify", "time")), "0s")},
                metadata={"options": _IDENTIFY_OPTIONS},
                actions={"select_option": _make_select_option(
                    _IDENTIFY_VALUE, "Identify", "time")},
            ))

        # ---- switch：可写布尔 ----
        bool_switches: tuple[tuple[str, str, str], ...] = (
            ("Disturb", "Disturb", "勿扰模式"),
            ("TemperatureThr", "MaxEn", "高温报警"),
            ("TemperatureThr", "MinEn", "低温报警"),
            ("HumidityThr", "MaxEn", "潮湿报警"),
            ("HumidityThr", "MinEn", "干燥报警"),
        )
        for sid, field, name in bool_switches:
            if not context.has_service(sid):
                continue
            entities.append(EntitySpec(
                platform="switch", key=f"{sid}_{field}", name=name,
                state=_switch_state(sid, field),
                actions={
                    "turn_on": _make_toggle(sid, field, 1),
                    "turn_off": _make_toggle(sid, field, 0),
                },
            ))

        # ---- number：可写整数阈值 ----
        number_fields: tuple[tuple[str, str, str, int, int, str], ...] = (
            ("TemperatureThr", "MaxThr", "高温报警值", -50, 100, "°C"),
            ("TemperatureThr", "MinThr", "低温报警值", -50, 100, "°C"),
            ("HumidityThr", "MaxThr", "潮湿报警值", 0, 100, "%"),
            ("HumidityThr", "MinThr", "干燥报警值", 0, 100, "%"),
        )
        for sid, field, name, lo, hi, unit in number_fields:
            if not context.has_service(sid):
                continue
            entities.append(EntitySpec(
                platform="number", key=f"{sid}_{field}", name=name,
                state=_num_state(sid, field),
                metadata={"min": lo, "max": hi, "step": 2, "unit": unit},
                actions={"set_value": _make_set_number(sid, field, lo, hi)},
            ))

        # ---- button：检查固件更新 ----
        if context.has_service("update"):
            async def _check_update(device: DeviceContext, _data: Mapping[str, Any]) -> None:
                await device.async_send_service("update", {"action": 0})

            entities.append(EntitySpec(
                platform="button", key="update_check", name="检查固件更新",
                state=lambda d: {},
                actions={"press": _check_update},
            ))

        return tuple(entities)


ADAPTER = Product20KXAdapter()
#（注：内容由AI生成）
