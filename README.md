# HA-Honeywell-Lyric-My
A modification of the built-in Home Assistant (HA) Honeywell Lyric integration that extends support for the WiFi Water Leak devices

This repository is a mash up of the Home Assistant Core integration [Honeywell](https://github.com/home-assistant/core/tree/dev/homeassistant/components/lyric). This includes custom support for the Resideo/First Alert Wifi Water Leak and Freeze devices. 

The Resideo app communicates over a Resideo API. This integration uses a Honeywell API. This means that there are some features that are not available since the functionality of the two are different. Even some of the fields presented from the [documentation](https://developer.honeywellhome.com/lyric/apis/get/devices/%7BdeviceType%7D/%7BdeviceId%7D) are out of sync.

I have been unable to get the reporting of temp/hum changed to more frequently than 3 times per day, even though the devices (in the API) mention supporting more frequent update intervals. 

For this code to be properly merged with the original intentions of the Honeywell integration, the backend library [AIO Lyric](https://github.com/timmo001/aiolyric) must be updated to support the water leak devices. 
Currently, there are some assumptions and patchwork things being done to enable support (e.g. the water leak devices don't expose a MAC).

This code is provided without dedicated support. While the climate portion of the integration should still function, I cannot test it and make no guarantees that it remains working. The domain of this integration is 'Lyric My', which should avoid collisions when running alongside the built-in Honeywell integration with domain 'Lyric'. 
