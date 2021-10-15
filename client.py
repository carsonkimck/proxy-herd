import asyncio
import argparse

servers = {"Riley": 15310, "Jaquez": 15311, "Juzang": 15312, "Campbell": 15313, "Bernard": 15314}

server_relations = { "Riley" : ["Jaquez", "Juzang"],
                    "Bernard" : ["Jaquez", "Juzang", "Campbell"],
                    "Juzang": ["Campbell", "Riley", "Bernard"],
                    "Jaquez": ["Riley", "Juzang", "Bernard"],
                    "Campbell": ["Juzang", "Bernard"]
}


local = "127.0.0.1"

class Client:
    def __init__(self, ip='127.0.0.1', port=8888, name='client', message_max_length=1e6):
        """
        127.0.0.1 is the localhost
        port could be any port
        """
        self.ip = ip
        self.port = port
        self.name = name
        self.message_max_length = int(message_max_length)

    async def tcp_echo_client(self, message):
        """
        on client side send the message for echo
        """
        reader, writer = await asyncio.open_connection(self.ip, self.port)
        print(f'{self.name} send: {message!r}')
        writer.write(message.encode())

        data = await reader.read(self.message_max_length)
        print(f'{self.name} received: {data.decode()!r}')

        print('close the socket')
        # The following lines closes the stream properly
        # If there is any warning, it's due to a bug o Python 3.8: https://bugs.python.org/issue38529
        # Please ignore it
        writer.close()

    def run_until_quit(self):
        # start the loop
        while True:
            # collect the message to send
            message = input("Please input the next message to send: ")
            if message in ['quit', 'exit', ':q', 'exit;', 'quit;', 'exit()', '(exit)']:
                break
            else:
                asyncio.run(self.tcp_echo_client(message))


if __name__ == '__main__':
    parser = argparse.ArgumentParser('Client Argument Parser')
    parser.add_argument('server', type=str)
    args = parser.parse_args()
    if not args.server in servers:
        print("Sever {} does not exist!".format(args.server))
        sys.exit()
    client = Client(local, servers[args.server])
    client.run_until_quit()