# ReadMe

This is a simple script to run Hive MiniLlapLocalDriverTests in batch,
in order to avoid running 2800+ time consuming job in one batch and
causing failures.

The usage is simple:

```
python run_hive_qtests_in_batch.py --batch_size <batch_size> --test_dir <test root dir> --maven_repo <maven local repo>
```
