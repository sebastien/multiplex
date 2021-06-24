```
              .__   __  .__       .__
  _____  __ __|  |_/  |_|__|_____ |  |   ____ ___  ___
 /     \|  |  \  |\   __\  \____ \|  | _/ __ \\  \/  /
|  Y Y  \  |  /  |_|  | |  |  |_> >  |_\  ___/ >    <
|__|_|  /____/|____/__| |__|   __/|____/\___  >__/\_ \
      \/                   |__|             \/      \/
```

# Installing

Quick, from the shell:

```
$ curl -o multiplex https://raw.githubusercontent.com/sebastien/multiplex/main/src/py/multiplex.py; chmod +x multiplex
$ ./multiplex --help
```

alternatively, using `pip`:

```
$ python -m pip install --user multiple
```
# Usage

## Commands

Here are some example commands that will help understand the syntax:
```
multiplex "python -m http.server"
```
Running a command after 5s delay:

```
multiplex "+5=python -m http.server"
```
Running a command after another
```
mutliplex "A=python -m http.server" "+A=ab -n1000 http://localhost:8000/"
```
Commands follow a simple structure:

- Prefix, before the `=`. If your command has an equal, start with an empty prefix (`=echo =`)
- Prefix has a name (`A=`)
- A potential delay (`+0.5`)
- A potential sequence of actions (`|silent|term`)


- Naming: `A=`, `B=` processes are named in `UPPER_CASE`
- Delay (seconds): `+1`  or `+1.5` waits delay seconds before starting the process
- Delay (after process): `+A` wait for `A` (or any other named process) to end before starting the process

Actions:
- `|end`, when the process ends, it terminate all other processes
- `|silent`, the process does not emit anything
- `|noout`, the process does not emit stdout data
- `|noerr`, the process does not emit stderr data
