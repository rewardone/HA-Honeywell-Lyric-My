"""Support for Honeywell Lyric binary sensor platform."""

from __future__ import annotations
import logging

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiolyric import Lyric
from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation
from aiolyric.objects.priority import LyricAccessory, LyricRoom

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    PRECISION_HALVES,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
)
from .entity import LyricAccessoryEntity, LyricDeviceEntity, LyricLeakEntity

_LOGGER = logging.getLogger(__name__)

class LyricLeakDevice(LyricDevice):
    """Attempt to extend a LyricDevice to provide Water Leak properties without
        changing AIOLyric or the value_fn/suitable_fn functionality"""

    @property 
    def waterPresent(self):
        """Return the waterPresent bool"""
        return self.attributes.get("waterPresent", None)

@dataclass(frozen=True, kw_only=True)
class LyricBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Honeywell Lyric binary sensor entities."""

    value_fn: Callable[[LyricLeakDevice], StateType | datetime]
    suitable_fn: Callable[[LyricLeakDevice], bool]


DEVICE_BINARY_SENSORS: list[LyricBinarySensorEntityDescription] = [
    LyricBinarySensorEntityDescription(
        key="Water Present",
        translation_key="waterPresent",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_fn=lambda device: bool(device.attributes.get("waterPresent")),
        suitable_fn=lambda device: device.attributes.get("waterPresent"),
    ),
    LyricBinarySensorEntityDescription(
        key="Alive",
        translation_key="isAlive",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda device: bool(device.attributes.get("isAlive")),
        suitable_fn=lambda device: device.attributes.get("isAlive"),
    ),
    # LyricBinarySensorEntityDescription(
    #     key="Firmware Update",
    #     translation_key="isFirmwareUpdateRequired",
    #     device_class=BinarySensorDeviceClass.PROBLEM,
    #     value_fn=lambda device: bool(device.attributes.get("isFirmwareUpdateRequired")),
    #     suitable_fn=lambda device: device.attributes.get("isFirmwareUpdateRequired"),
    # ),
]

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Honeywell Lyric binary sensor platform based on a config entry."""
    coordinator: DataUpdateCoordinator[Lyric] = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        LyricLeakBinarySensor(
            coordinator,
            device_sensor,
            location,
            device,
        )
        for location in coordinator.data.locations
        for device in location.devices
        for device_sensor in DEVICE_BINARY_SENSORS
        # if device_sensor.suitable_fn(device)
    )

class LyricLeakBinarySensor(LyricLeakEntity, BinarySensorEntity):
    """Defines a Honeywell Lyric water leak sensor entity."""

    coordinator: DataUpdateCoordinator[Lyric]
    entity_description: BinarySensorEntityDescription

    _attr_name = None

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Lyric],
        description: BinarySensorEntityDescription,
        location: LyricLocation,
        device: LyricLeakDevice,
    ) -> None:
        """Initialize Honeywell Lyric leak entity."""

        # Define type (wifi? freeze?)
        # if device.changeable_values.thermostat_setpoint_status:
        #     self._attr_thermostat_type = LyricThermostatType.LCC
        # else:
        #     self._attr_thermostat_type = LyricThermostatType.TCC

        # Use the native temperature unit from the device settings
        # Leak sensors seem to express values in C and don't expose a 'unit'
        # if device.units == "Fahrenheit":
        #     self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
        #     self._attr_precision = PRECISION_WHOLE
        # else:
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = PRECISION_HALVES 

        # Need to 'recreate' the location.devices_dict since AioLyric uses device.mac_id 

        _LOGGER.debug("device type: %s", type(device))

        for attr in device.attributes:
            _LOGGER.debug("device key and value: %s - %s", attr, device.attributes.get(attr))

        _LOGGER.debug("location.devices_dict type: %s", type(location.devices_dict))
        _LOGGER.debug("location:")
        _LOGGER.debug(location)

        _LOGGER.debug("device_dict:")
        _LOGGER.debug(location.devices_dict)

        for key in location.devices_dict.keys():
            _LOGGER.debug("location key and value: %s - %s", key, location.devices_dict[key])

        self._attr_sensor_id = f"{description.translation_key}"
        self._attr_unique_id = f"{device.attributes.get("deviceSettings", None)["userDefinedName"]}_{description.translation_key}"
        _LOGGER.debug("unique_id: %s", self._attr_unique_id)
        
        self.entity_id  = generate_entity_id("binary_sensor.{}", self._attr_unique_id, None, coordinator.hass)
        self._attr_entity_id = self.entity_id

        super().__init__(
            coordinator,
            location,
            device,
            f"{device.attributes.get("deviceSettings", None)["userDefinedName"]}_{description.translation_key}",
        )
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return self.entity_description.value_fn(self.device)

    @property
    def name(self) -> str | None:
        """Define name as description"""
        return f"{self.device.attributes.get("deviceSettings", None)["userDefinedName"]} {self.entity_description.key}"

    # @property
    # def icon(self) -> str | None:
    #     """Define the icon"""
    #     return self._attr_icon

    # @property
    # def temperature(self) -> float | None:
    #     """Return the current temperature"""
    #     return self.device.attributes.get("currentSensorReadings")["temperature"]

    # @property
    # def humidity(self) -> float | None:
    #     """Return the current humidity"""
    #     return self.device.attributes.get("currentSensorReadings")["humidity"]

    # @property
    # def battery(self) -> float | None:
    #     """Return the current battery level"""
    #     return self.device.attributes.get("batteryRemaining")

    # @property
    # def temp_warn_max(self) -> float | None:
    #     """Return the current high temp warning setting"""
    #     return self.device.attributes.get("deviceSettings")["temp"]["high"]["limit"]
    
    # @property
    # def temp_warn_min(self) -> float | None:
    #     """Return the current low temp warning setting"""
    #     return self.device.attributes.get("deviceSettings")["temp"]["low"]["limit"]

    # @property
    # def hum_warn_max(self) -> float | None:
    #     """Return the current high hum warning setting"""
    #     return self.device.attributes.get("deviceSettings")["humidity"]["high"]["limit"]

    # @property
    # def hum_warn_min(self) -> float | None:
    #     """Return the current low hum warning setting"""
    #     return self.device.attributes.get("deviceSettings")["humidity"]["low"]["limit"]
