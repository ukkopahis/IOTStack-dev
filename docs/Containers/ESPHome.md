# ESPHome

[ESPHome](https://esphome.io/) is a system to control your ESP8266/ESP32 by
simple yet powerful configuration files and control them remotely through Home
Automation systems.

Web UI is at: `http://raspberrypi.local:6052/`
Login username is `admin` and the password is automatically generated and can be
found and changed in your `docker-compose.yml`.

## USB serial programming from a docker-container

To support flashing an ESP device directly from your RPi, `/dev/ttyUSB0` is made
available to the container. This file usually auto-created when an
USB-to-serial-converter is plugged in. Docker needs the file to exist when the
container is started, even if an ESP is not plugged in at that time. Files in
created in /dev aren't persisted upon reboot. Thus a service is needed to create
it at startup. This service is usually added by install.sh or menu.sh. If it
somehow missing, just add the service manually:

```
bash .templates/esphome/create-systemd-ttyUSB0-service.sh
```
