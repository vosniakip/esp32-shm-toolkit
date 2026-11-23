# ESP32 SHM Toolkit

Use these sketches and Python scripts to record acceleration, calibrate MEMS sensors, and analyze structural vibrations. The code accompanies Isaque Vosniak Passos’s Civil Engineering final project at Universidade Federal do Paraná (UFPR), *Desenvolvimento de um nó sensor de baixo custo para aplicação em monitoramento da integridade estrutural* (2026).

| Sensor and board | What the package covers | Guide |
| --- | --- | --- |
| MPU-6050 · ESP32 DevKit V1 | USB serial acquisition and bench tests | [MPU-6050 v1.0.1](setups/mpu6050-esp32-devkit-v1/README.md) |
| MPU-9250 / GY-9250 · ESP32 DevKit V1 | USB serial acquisition and bench tests | [GY-9250 v1.0.1](setups/mpu9250-esp32-devkit-v1/README.md) |
| ADXL355 · ESP32-S3 | USB serial acquisition and calibration | [ADXL355 USB v2.0.0](setups/adxl355-esp32-s3/usb/README.md) |
| ADXL355 · ESP32-S3 | Wi-Fi control and microSD storage for bench tests | [ADXL355 Wi-Fi + microSD v3.0.0](setups/adxl355-esp32-s3/wifi-sd/README.md) |
| ADXL355 · ESP32-S3 | Comparative tests and campaign | [ADXL355 field package v4.1.0](setups/adxl355-esp32-s3/field/README.md) |

## Getting started

1. Open the guide for your setup. It is written in Portuguese and explains the wiring, board settings, and commands for the first recording.
2. Check the pinout and sensor identification, then upload the matching Arduino sketch. For Wi-Fi builds, set the node’s access point credentials in `config.h` before uploading. If you use the GY-9250 package, check the electronic sensor ID in the recording metadata when interpreting the data.
3. Open a terminal in the selected package folder and install its Python dependencies. Python 3.12 is a good starting point:

   ```text
   python -m venv .venv
   # Activate .venv for your operating system before running the next command.
   python -m pip install -r requirements.txt
   ```

4. Make a short test recording to check that the node is working before you begin calibration or record structural vibrations.

The [TFC analysis scripts](analysis/README.md) reproduce the processing steps for the MPU bench tests, ADXL355 wireless bench tests, shaker comparison, and footbridge measurements. Each analysis needs its corresponding input records. Supply your own recordings and calibration files for the analyses. Test signals can be generated locally; this repository contains no measurement files, precomputed results, or reports.

The [enclosure v0.10](hardware/enclosure-v0.10/README.md) includes Bambu Studio projects, printable STL files, and the editable OpenSCAD model.

To cite the software, see [CITATION.cff](CITATION.cff). The code is distributed under the [MIT license](LICENSE). The Arduino ESP32 core and Python dependencies retain their own licenses.
