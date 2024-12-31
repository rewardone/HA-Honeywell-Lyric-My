"""Support for Honeywell Lyric sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiolyric import Lyric
from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation
from aiolyric.objects.priority import LyricAccessory, LyricRoom

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    PRESET_HOLD_UNTIL,
    PRESET_NO_HOLD,
    PRESET_PERMANENT_HOLD,
    PRESET_TEMPORARY_HOLD,
    PRESET_VACATION_HOLD,
)
from .entity import LyricAccessoryEntity, LyricDeviceEntity, LyricLeakEntity

LYRIC_SETPOINT_STATUS_NAMES = {
    PRESET_NO_HOLD: "Following Schedule",
    PRESET_PERMANENT_HOLD: "Held Permanently",
    PRESET_TEMPORARY_HOLD: "Held Temporarily",
    PRESET_VACATION_HOLD: "Holiday",
}


@dataclass(frozen=True, kw_only=True)
class LyricSensorEntityDescription(SensorEntityDescription):
    """Class describing Honeywell Lyric sensor entities."""

    value_fn: Callable[[LyricDevice], StateType | datetime]
    suitable_fn: Callable[[LyricDevice], bool]


@dataclass(frozen=True, kw_only=True)
class LyricSensorAccessoryEntityDescription(SensorEntityDescription):
    """Class describing Honeywell Lyric room sensor entities."""

    value_fn: Callable[[LyricRoom, LyricAccessory], StateType | datetime]
    suitable_fn: Callable[[LyricRoom, LyricAccessory], bool]


DEVICE_SENSORS: list[LyricSensorEntityDescription] = [
    LyricSensorEntityDescription(
        key="indoor_temperature",
        translation_key="indoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.indoor_temperature,
        suitable_fn=lambda device: device.indoor_temperature,
    ),
    LyricSensorEntityDescription(
        key="indoor_humidity",
        translation_key="indoor_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.indoor_humidity,
        suitable_fn=lambda device: device.indoor_humidity,
    ),
    LyricSensorEntityDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.outdoor_temperature,
        suitable_fn=lambda device: device.outdoor_temperature,
    ),
    LyricSensorEntityDescription(
        key="outdoor_humidity",
        translation_key="outdoor_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.displayed_outdoor_humidity,
        suitable_fn=lambda device: device.displayed_outdoor_humidity,
    ),
    LyricSensorEntityDescription(
        key="next_period_time",
        translation_key="next_period_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda device: get_datetime_from_future_time(
            device.changeable_values.next_period_time
        ),
        suitable_fn=lambda device: (
            device.changeable_values and device.changeable_values.next_period_time
        ),
    ),
    LyricSensorEntityDescription(
        key="setpoint_status",
        translation_key="setpoint_status",
        value_fn=lambda device: get_setpoint_status(
            device.changeable_values.thermostat_setpoint_status,
            device.changeable_values.next_period_time,
        ),
        suitable_fn=lambda device: (
            device.changeable_values
            and device.changeable_values.thermostat_setpoint_status
        ),
    ),
]

ACCESSORY_SENSORS: list[LyricSensorAccessoryEntityDescription] = [
    LyricSensorAccessoryEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda _, accessory: accessory.temperature,
        suitable_fn=lambda _, accessory: accessory.type == "IndoorAirSensor",
    ),
    LyricSensorAccessoryEntityDescription(
        key="room_humidity",
        translation_key="room_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda room, _: room.room_avg_humidity,
        suitable_fn=lambda _, accessory: accessory.type == "IndoorAirSensor",
    ),
]

LEAK_SENSORS: list[LyricSensorEntityDescription] = [
    LyricSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.attributes.get("currentSensorReadings")["temperature"],
        suitable_fn=lambda device: device.attributes.get("currentSensorReadings"),
    ),
    LyricSensorEntityDescription(
        key="WarnTempMax",
        translation_key="warn_temp_max",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.attributes.get("deviceSettings")["temp"]["high"]["limit"],
        suitable_fn=lambda device: device.attributes.get("currentSensorReadings"),
    ),
    LyricSensorEntityDescription(
        key="WarnTempMin",
        translation_key="warn_temp_low",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.attributes.get("deviceSettings")["temp"]["low"]["limit"],
        suitable_fn=lambda device: device.attributes.get("currentSensorReadings"),
    ),
    LyricSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.attributes.get("currentSensorReadings")["humidity"],
        suitable_fn=lambda device: device.attributes.get("currentSensorReadings"),
    ),
    LyricSensorEntityDescription(
        key="WarnHumMax",
        translation_key="warn_hum_max",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.attributes.get("deviceSettings")["humidity"]["high"]["limit"],
        suitable_fn=lambda device: device.attributes.get("currentSensorReadings"),
    ),
    LyricSensorEntityDescription(
        key="WarnHumMin",
        translation_key="warn_hum_low",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.attributes.get("deviceSettings")["humidity"]["low"]["limit"],
        suitable_fn=lambda device: device.attributes.get("currentSensorReadings"),
    ),
    LyricSensorEntityDescription(
        key="Battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.attributes.get("batteryRemaining"),
        suitable_fn=lambda device: device.attributes.get("batteryRemaining"),
    ),
    LyricSensorEntityDescription(
        key="WiFi",
        translation_key="wifi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: abs(device.attributes.get("wifiSignalStrength")),
        suitable_fn=lambda device: abs(device.attributes.get("wifiSignalStrength")),
    ),
    LyricSensorEntityDescription(
        key="LastCheckin",
        translation_key="last_checkin",
        device_class=None,
        state_class=None,
        value_fn=lambda device: device.attributes.get("lastCheckin"),
        suitable_fn=lambda device: device.attributes.get("lastCheckin"),
    ),
    # LyricSensorEntityDescription(
    #     key="Firmware",
    #     translation_key="firmwareVer",
    #     device_class=None,
    #     state_class=None,
    #     value_fn=lambda device: device.attributes.get("firmwareVer"),
    #     suitable_fn=lambda device: device.attributes.get("firmwareVer"),
    # ),
]

def get_setpoint_status(status: str, time: str) -> str | None:
    """Get status of the setpoint."""
    if status == PRESET_HOLD_UNTIL:
        return f"Held until {time}"
    return LYRIC_SETPOINT_STATUS_NAMES.get(status)


def get_datetime_from_future_time(time_str: str) -> datetime:
    """Get datetime from future time provided."""
    time = dt_util.parse_time(time_str)
    if time is None:
        raise ValueError(f"Unable to parse time {time_str}")
    now = dt_util.utcnow()
    if time <= now.time():
        now = now + timedelta(days=1)
    return dt_util.as_utc(datetime.combine(now.date(), time))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Honeywell Lyric sensor platform based on a config entry."""
    coordinator: DataUpdateCoordinator[Lyric] = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        LyricSensor(
            coordinator,
            device_sensor,
            location,
            device,
        )
        for location in coordinator.data.locations
        for device in location.devices
        for device_sensor in DEVICE_SENSORS
        if device_sensor.suitable_fn(device)
    )

    async_add_entities(
        LyricLeakSensor(
            coordinator,
            device_sensor,
            location,
            device,
        )
        for location in coordinator.data.locations
        for device in location.devices
        for device_sensor in LEAK_SENSORS
    )

    async_add_entities(
        LyricAccessorySensor(
            coordinator, accessory_sensor, location, device, room, accessory
        )
        for location in coordinator.data.locations
        for device in location.devices
        for room in coordinator.data.rooms_dict.get(device.mac_id, {}).values()
        for accessory in room.accessories
        for accessory_sensor in ACCESSORY_SENSORS
        if accessory_sensor.suitable_fn(room, accessory)
    )


class LyricSensor(LyricDeviceEntity, SensorEntity):
    """Define a Honeywell Lyric sensor."""

    entity_description: LyricSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Lyric],
        description: LyricSensorEntityDescription,
        location: LyricLocation,
        device: LyricDevice,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            location,
            device,
            f"{device.mac_id}_{description.key}",
        )
        self.entity_description = description
        if description.device_class == SensorDeviceClass.TEMPERATURE:
            if device.units == "Fahrenheit":
                self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
            else:
                self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state."""
        return self.entity_description.value_fn(self.device)

class LyricLeakSensor(LyricLeakEntity, SensorEntity):
    """Define a Honeywell Lyric sensor."""

    entity_description: LyricSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Lyric],
        description: LyricSensorEntityDescription,
        location: LyricLocation,
        device: LyricDevice,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            location,
            device,
            f"{device.device_id}_{description.key}",
        )
        self.entity_description = description
        if description.device_class == SensorDeviceClass.TEMPERATURE:
            if device.units == "Fahrenheit":
                self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
            else:
                self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        
        if description.device_class == SensorDeviceClass.HUMIDITY:
            self._attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state."""
        return self.entity_description.value_fn(self.device)

    @property
    def name(self) -> str | None:
        """Define name as description"""
        return f"{self.device.attributes.get("deviceSettings", None)["userDefinedName"]} {self.entity_description.key}"

class LyricAccessorySensor(LyricAccessoryEntity, SensorEntity):
    """Define a Honeywell Lyric sensor."""

    entity_description: LyricSensorAccessoryEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Lyric],
        description: LyricSensorAccessoryEntityDescription,
        location: LyricLocation,
        parentDevice: LyricDevice,
        room: LyricRoom,
        accessory: LyricAccessory,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            location,
            parentDevice,
            room,
            accessory,
            f"{parentDevice.mac_id}_room{room.id}_acc{accessory.id}_{description.key}",
        )
        self.entity_description = description
        if description.device_class == SensorDeviceClass.TEMPERATURE:
            if parentDevice.units == "Fahrenheit":
                self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
            else:
                self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state."""
        return self.entity_description.value_fn(self.room, self.accessory)
