from multiplex import run, join


def receive(stream: str, key: str, data):
    print("receive data")


run("python", "-m", "http", "server", onData=receive)
join()
# EOF
