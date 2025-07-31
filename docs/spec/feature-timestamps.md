## Timestamp

Logging can be prefixed with a standard or relative timestamp using the `--time[=MODE]` opion.

The default `absolute` time mode adds a `HH:MM:SS|` prefix to every log entry

```
12:31:20|$│A│echo hello from A
12:31:20|<│A│hello from A
12:31:21|=│A│0
12:31:21|$│B│cat
12:31:21|<│B│hello from A
```

The `relative` mod then displays the time relative to the start:

```
00:00:00|$│A│echo hello from A
00:00:00|<│A│hello from A
00:00:01|=│A│0
00:00:01|$│B│cat
00:00:01|<│B│hello from A
```

