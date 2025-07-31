## Start on output

Commands can start only when another command outputs something:

- `>A` waits for `A` to output on stdout
- `>2A` waits for `A` to output on stderr
- `>(1A,2A)` waits for `A` to output on both stdout and tderr
- `>(A,B)`


