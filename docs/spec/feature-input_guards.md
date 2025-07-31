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


