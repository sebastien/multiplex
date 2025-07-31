The command format should now be like so

```
[KEY][#COLOR][+DELAY…][:DEP…][|ACTIONS]=COMMAND`
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

