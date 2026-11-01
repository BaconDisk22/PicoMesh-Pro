# Pico MeshCore Companion Client

A lightweight MeshCore Companion client written in MMBasic for the PicoMite (Raspberry Pi Pico).  
It communicates with a Heltec V4 (or compatible MeshCore radio) over UART and provides a simple terminal-based interface.

## Features

- Send and receive direct messages
- Receive channel messages (including V3)
- Synchronize and list contacts
- Send channel messages (#public)
- Set node (advert) name
- Sync device time
- Configure radio parameters (frequency, bandwidth, SF, CR, TX power)
- Send advertisements (Zero Hop / Flood Routing)
- Basic diagnostics and raw frame tools

## Hardware Requirements

- Raspberry Pi Pico running PicoMite firmware
- Heltec V4 (or compatible MeshCore radio)
- UART connection between Pico and radio

## Wiring

Pico GP8 (UART1TX) → Heltec PIN 44 (U0RXD)
Pico GP9 (UART1RX) → Heltec PIN 43 (U0TXD)
Pico PIN 38 (GND) → Heltec GND
Pico PIN 36 (3V3 OUT) → Heltec 3V3

## Build MeshCode Companion Firmware for Serial Connection

Add the following section to `variants/heltec_v4/platformio.ini`:

```ini
[env:heltec_v4_companion_radio_uart]
extends = Heltec_lora32_v4
build_unflags =
    -D PIN_USER_BTN=0
build_flags =
    ${Heltec_lora32_v4.build_flags}
    -I examples/companion_radio/ui-new
    -D MAX_CONTACTS=350
    -D MAX_GROUP_CHANNELS=40
    -D SERIAL_RX=44
    -D SERIAL_TX=43
    -D ENV_INCLUDE_GPS=0
build_src_filter =
    ${Heltec_lora32_v4.build_src_filter}
    +<helpers/ui/MomentaryButton.cpp>
    +<../examples/companion_radio/*.cpp>
    +<../examples/companion_radio/ui-new/*.cpp>
lib_deps =
    ${Heltec_lora32_v4.lib_deps}
    densaugeo/base64 @ ~1.4.0
```

`-D ENV_INCLUDE_GPS=0` is important.
It took me 1 day to figure out why the UART stops working.

Build Firmware with

```bash
pio run -e heltec_v4_companion_radio_uart -t upload
```

## Accessing Radio in MMBasic

```basic
SETPIN GP9, GP8, COM2
OPEN "COM2:115200" AS #1
```

## Usage

The program provides a simple menu:

- Messages → read/send messages
- Contacts → sync and list contacts
- Device → status, radio settings, name, time, diagnostics

Contacts are loaded from the radio and stored locally.
Large contact lists are supported.


## Limitations

- No persistent storage (data is lost after restart)
- I don't know how to public channels other than #public (like #test or #ping)
- I don't know how to add private channels


## License

Provided as-is for educational and experimental use.
