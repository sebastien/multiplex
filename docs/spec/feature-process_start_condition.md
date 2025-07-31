# Condition for process start

By default, a condition like `A` means that we wait for `A` to finish. To denote
that we want to wait for the start of `A` we add an `&`:

- `A&` means the we wait for `A` to start
- `A&+10s` means the we wait for `A` to start and then 10
