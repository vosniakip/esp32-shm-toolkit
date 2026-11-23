# Analysis scripts for the TFC

These scripts process the records from specific experiments in the final project. Each workflow expects the original data layout and its own Python dependencies. For a new measurement, start with the general acquisition and analysis routines in [setups](../setups).

## MPU bench tests

Open [mpu-bench](mpu-bench) and install the dependencies in `requirements.txt`. Extract each sensor’s records under `entrada/<sensor>/dados/`, using the sensor folder names in `analisar.py`. Run `analisar.py` to process the records and `figuras.py` to draw the figures.

## ADXL355 wireless bench tests

In [adxl355-wireless](adxl355-wireless), run `analisar_wireless.py --dados PATH --calibracao-id ID --saida PATH`. Point `--dados` to the complete Wi-Fi acquisition directory, which must include the calibration that goes with the recordings. The ID is the directory name under `dados/calibracao/`. Use the [v3 bench package requirements](../setups/adxl355-esp32-s3/wifi-sd/requirements.txt).

## Shaker comparison

In [shaker](shaker), install `requirements_comparacao.txt` and run `analisar_shaker_comparativo.py --no ZIP --profissional ZIP --calibracao PATH --saida PATH`. Use the node and professional reference files from the same tests, along with the calibration for that node.

## Footbridge campaign

Use the reusable field routines in the [ADXL355 field guide](../setups/adxl355-esp32-s3/field/README.md). The campaign script `27_passarela_ufpr.py` acquires and checks each recording. Use `22_identificar_passarela.py` to review the spectrum and candidate frequencies for new records.

The repository contains the analysis code. The input datasets, fitted calibrations, and generated reports are kept separately.
