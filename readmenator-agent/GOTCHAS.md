# Gotchas

## God Nodes (high connectivity)

These files have the most connections. Changes here have high blast radius.

- `app.py` (score: 0.90)
- `install.sh` (score: 0.00)

## Hotspots (complexity + centrality)

- `app.py` -- complexity: 1.0, centrality: 1.0, combined: 1.0
- `install.sh` -- complexity: 0.0, centrality: 0.0, combined: 0.0

## Dataflow Issues (INFERRED, review each lead)

- `app.py:100` `run_fake_ftp` [UNCHECKED_ALLOC] `server`: Result of allocator stored in `server` is never checked against NULL.
- `app.py:143` `sniffer_loop` [UNCHECKED_ALLOC] `raw_sock`: Result of allocator stored in `raw_sock` is never checked against NULL.
