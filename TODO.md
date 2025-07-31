Misc:
- Add an optional `s` for delays, so that it's more readable.

# Features

## Optional suffix for delays

Delays can be written with different units for delays:

- `+1ms` for milliseconds
- `+1s` for seconds
- `+1m` for minutes
- `+1m10s` for minutes/seconds

## Upgraded command format

The command format should now be like so

```
[KEY][#COLOR][:DEP…][|ACTION…]=COMMAND
```

where:

- `#COLOR` for a given color, either by name or in hex
- `:DEP` is a dependency (see below, can be chained)
- `|ACTION` is an action (can be chained)

Dependencies are in the following form:

```
[KEY][&][+DELAY…]
```

- `KEY` for the process name we wait on, if it is followed by `&` then it
  indicates the process start instead of the end.
- `+DELAY` for a delay (can be chained)


## Condition from process start

By default, a condition like `A` means that we wait for `A` to finish. To denote
that we want to wait for the start of `A` we add an `&`:

- `A&` means the we wait for `A` to start
- `A&+10s` means the we wait for `A` to start and then 10s


## Redirects

Commands can support stdin to come from another process's stdout/stderr:

- `<A…` map stdin to `A` stdout
- `<2A…` map stdin to `A` stderr
- `<(1A,2A)…` map stdin to `A`'s stdout and stderr combined
- `<(A,B)…` map stdin to `A`'s stdout  and `B`s stdout

## Start on output

Commands can start only when another command outputs something:

- `>A` waits for `A` to output on stdout
- `>2A` waits for `A` to output on stderr
- `>(1A,2A)` waits for `A` to output on both stdout and tderr
- `>(A,B)`

## Input guards

Commands can wait for a given input to match a glob or regexp before
starting.

- `!GUARD` where `GUARD` is a name (`[A-Za-z0-9_-]+`)

And there is a corresponding guard defined in the arguments

- `@GUARD=EXPR` where `GUARD` is the guard name and `EXPR` is the glob to
  match. For instance `@start=*Ready!*`,

- `@GUARD:re=EXPR` the `:re` suffix can be used so that `EXPR` is a regexp.

Guards can be inserted along with delays on the commands, for instance:

- `+A!READY+10s` would mean: wait for A to finish, then wait for the `READY`
  guard to match on stdin, then wait 10s.


## Process Input Guards

Input guards can be mapped to processes, in which case they act like events:
as soon as a process stdout or stderr matches the guard, the guard is met
for all other processes:

- `+A|GUARD` means "wait for `GUARD` to match `A`'s output
- `+A(2)|GUARD` means "wait for `GUARD` to match `A`'s stderr
- `+A(1,2)|GUARD` means "wait for `GUARD` to match `A`'s stdout and stderr

