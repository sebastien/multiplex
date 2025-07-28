from multiplex import run, join

def receive(stream: str, key: str, data):
	print("receive data")

run("python3", "-m", "http", "server", onData=receive)
join()
# EOF
