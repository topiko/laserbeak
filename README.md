# FORK FROM: [Laserbeak: Evolving Website Fingerprinting Attacks with Attention and Multi-Channel Feature Representation](https://github.com/notem/Laserbeak-WF-Classifier)


## Usage

### Training a LASERBEAK Model

To train a LASERBEAK model on a specified dataset, use the following command:

```bash
python benchmark.py \
    --data_dir /path/to/data \
    --ckpt_dir /path/to/checkpoints \
    --results_dir /path/to/results \
    --config ./laserbeak/model_configs/laserbeak.json \
    --dataset be-front \
    --epochs 20 \
    --multisamples 10 \
    --exp_name my_experiment
```

This command trains the model on the `be-front` dataset using x10 simulated samples for 20 epochs.

### Evaluation

To evaluate a pre-trained LASERBEAK model, use:

```bash
python benchmark.py \
    --data_dir /path/to/data \
    --ckpt /path/to/model_checkpoint.pth \
    --eval --dataset be-front
```

This command loads the model checkpoint and evaluates its performance on the `be-front` dataset.

## Available Datasets

The `benchmark.py` script supports various datasets for training and evaluation, including:

- `be`: Basic dataset
- `be-front`: Front-defended dataset
- `amazon`: Amazon traffic dataset
- `webmd`: WebMD traffic dataset
- `gong`: Gong dataset with Surakav defenses

Refer to the `--dataset` option in the command-line arguments for the full list of available datasets.

ORIGINAL AUTHORS provide these datasets as pre-packaged pickle files that can be downloaded from the this [Google drive directory](https://drive.google.com/drive/folders/1cRIujmDFUpVD0rA0U92bxeGaq5DMlzFm?usp=drive_link).
To load the provided files using the `benchmark.py` script, the `--data_dir` argument should be used to direct to the parent directory containing the `wf-*` subdirectories. The file and subdirectory names must be the same as provided in the Google drive to function correctly.

## Warnings

**This code is research-grade and may contain bugs or other issues.** Users are advised to carefully validate results and use the code at their own risk.
