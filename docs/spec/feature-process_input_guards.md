## Process Input Guards

Input guards can be mapped to processes, in which case they act like events:
as soon as a process stdout or stderr matches the guard, the guard is met
for all other processes:

- `+A|GUARD` means "wait for `GUARD` to match `A`'s output
- `+A(2)|GUARD` means "wait for `GUARD` to match `A`'s stderr
- `+A(1,2)|GUARD` means "wait for `GUARD` to match `A`'s stdout and stderr


