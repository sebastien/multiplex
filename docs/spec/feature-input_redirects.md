## Redirects

Commands can support stdin to come from another process's stdout/stderr:

- `<A…` map stdin to `A` stdout
- `<2A…` map stdin to `A` stderr
- `<(1A,2A)…` map stdin to `A`'s stdout and stderr combined
- `<(A,B)…` map stdin to `A`'s stdout  and `B`s stdout


