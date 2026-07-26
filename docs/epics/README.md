# Epics

Bead diagrams for the seven molecules filed in the `dxnvh` hive. See
[../ROADMAP.md](../ROADMAP.md) for sequencing and the decisions behind them.

| Molecule | Epic | Beads | Owner |
|---|---|---|---|
| [Foundation](./332-foundation.md) | `dxnvh-332` | 14 | shared |
| [GB10 spike](./bht-gb10-spike.md) | `dxnvh-bht` | 6 | infra |
| [C1 Infrastructure & sources](./0f2-infrastructure.md) | `dxnvh-0f2` | 6 | infra |
| [C2 Ingestion & storage](./2jb-ingestion.md) | `dxnvh-2jb` | 8 | data/backend |
| [C3 Refinement & processing](./0e6-processing.md) | `dxnvh-0e6` | 8 | ML/agent |
| [C4 UX & dashboard](./7t2-dashboard.md) | `dxnvh-7t2` | 7 | frontend |
| [Integration & demo](./xe5-integration.md) | `dxnvh-xe5` | 6 | shared |

Diagrams show dependency edges only. `bh work ready` is the live view.

```bash
bh plan show <epic>      # full decomposition with acceptance criteria
bh plan status           # kickoff state per molecule
bh work ready            # what is dispatchable now
```

Boxes drawn with a dashed border are gated on a verdict that does not exist yet.
