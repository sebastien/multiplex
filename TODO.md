Misc:
- Add an optional `s` for delays, so that it's more readable.

# Features

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

## Timestamp format

Add the `-t|--timestamp` option that adds a `HH:MM:SS|` prefix to every log
entry

```
12:31:20|$│A│echo hello from A
12:31:20|<│A│hello from A
12:31:21|=│A│0
12:31:21|$│B│cat
12:31:21|<│B│hello from A
```

And a `-r|-relative` option that then displays the time relative to the start:

```
00:00:00|$│A│echo hello from A
00:00:00|<│A│hello from A
00:00:01|=│A│0
00:00:01|$│B│cat
00:00:01|<│B│hello from A
```
