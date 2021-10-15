# Carson Kim
# CS 131 - Final Project
# Winter 2021

import aiohttp
import asyncio
import argparse
import json
import logging
import re
import sys
import time
import config 

# Globals
servers = {"Riley": 15310, "Jaquez": 15311, "Juzang": 15312, "Campbell": 15313, "Bernard": 15314}

server_relations = { "Riley" : ["Jaquez", "Juzang"],
                    "Bernard" : ["Jaquez", "Juzang", "Campbell"],
                    "Juzang": ["Campbell", "Riley", "Bernard"],
                    "Jaquez": ["Riley", "Juzang", "Bernard"],
                    "Campbell": ["Juzang", "Bernard"]
                    }

local = "127.0.0.1"
nsr_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
api_key = config.api_key

# Helpers for parsing client messages

def parse_message(message):
    z = re.split(r"(-|\+| )", message)
    filtered = (filter(removeSpaces, z))
    return (list(filtered))

def removeSpaces(var):
    if (var.isspace()):
        return False
    if not var:
        return False
    else:
      return True

def is_number(string):
    if type(string) == int or float:
        return True
    else:
        return False

# Server Class

class Server:
    def __init__(self, name, ip=local, message_max_length=1e6):
        self.name = name
        self.ip = ip
        self.port = servers[name]
        self.message_max_length = int(message_max_length)
        self.client_timestamp = dict()
        self.client_coords = dict()
        logging.info("Start of log file for server {} \n".format(self.name))

    async def handle_client_input(self, reader, writer):

        # server side stuff
        data = await reader.read(self.message_max_length)
        message = data.decode()
        args = parse_message(message)
        sendback_message = ""
        logging.info("{} received the following message: {}".format(self.name, message.rstrip('\n')))

        if args[0] == "IAMAT":
            if (len (args) == 7):
                client_id = args[1]
                # stores client info into server
                self.client_timestamp[client_id] = float(args[6])
                self.client_coords[client_id] = ["{}{}".format(args[2], args[3]), "{}{}".format(args[4], args[5])]
                # gets time diff, prepares message for sendback
                diff = (time.time()) - (float(args[6]))
                sendback_message = "AT {} +{} {}".format(self.name, diff, message[6:])
                logging.info("Sending message back to {}: {}".format(client_id, sendback_message))
                # send to other servers
                await self.propagate_messages(sendback_message)

            else:
                # invalid request
                client_id = args[1]
                sendback_message = "? {}".format(message)
                logging.info("Sending invalid message back to {}: {}".format(client_id, sendback_message))
        
        elif args[0] == "WHATSAT":
            if self.validWHATSAT(args):
                client_id = args[1]
                # returns JSON response, as string
                response = await self.nearby_search_request(self.client_coords[client_id], args[2], args[3])
                # prepares message for sendback
                recent_time = self.client_timestamp[client_id]
                diff = (time.time()) - (recent_time)
                response.replace("\n\n", "\n")
                sendback_message = "AT {name} +{t_diff} {id} {lat} {lon} {time} \n{json}\n\n".format(name=self.name,t_diff=diff,id=client_id,
                                                                                                    lat=args[2],lon=args[3], time=recent_time,
                                                                                                    json=response.rstrip('\n'))
              
                logging.info("Sending message back to {}: {}".format(client_id, sendback_message))
            else:
                # invalid request
                client_id = args[1]
                sendback_message = "? {}".format(message)
                logging.info("Sending invalid message back to {}: {}".format(client_id, sendback_message))

        elif args[0] == "AT":
            if len(args) == 10:
                client_id = args[4]
                timestamp = float(args[9])
                if client_id not in self.client_timestamp:
                    # add new client timestamp and coordinates
                    self.client_timestamp[client_id] = timestamp
                    self.client_coords[client_id] = ["{}{}".format(args[5], args[6]), "{}{}".format(args[7], args[8])]
                    logging.info("New client {} received! Timestamp: {} Coordinates: {}".format(client_id, timestamp, self.client_coords[client_id]))
                    # send to other servers
                    await self.propagate_messages(message)
                elif float(timestamp) > self.client_timestamp[client_id]:
                    # must update client info!
                    self.client_timestamp[client_id] = timestamp
                    self.client_coords[client_id] = ["{}{}".format(args[5], args[6]), "{}{}".format(args[7], args[8])]
                    logging.info("Client {} has been updated. New Timestamp: {} New Coordinates: {}".format(client_id, timestamp, self.client_coords[client_id]))
                    # send to other servers
                    await self.propagate_messages(message)

                else:
                    # most recent info is already stored, no need to update
                    logging.info("Client {}'s info is already stored.".format(client_id))
            else:
                # we should never get here, AT messages should always be valid
                logging.info("Error receieving AT message!")

        else:
            # all other weird messages
            sendback_message = "? {}".format(message)
            logging.info("Error receiving message.")

        # writes the message back!
        print("Sending message back: {}".format(sendback_message))
        writer.write(sendback_message.encode())
        await writer.drain()
        writer.close()

    async def nearby_search_request(self, location, radius, bound):
        async with aiohttp.ClientSession() as session:
        # location is in format [+-lat, +-long]
            async with session.get("{}&location={},{}&radius={}&key={}".format(nsr_url, location[0], location[1], radius, api_key)) as resp:
                response = (await resp.text())
                response_obj = json.loads(response)
                if len(response_obj["results"]) < int(bound):
                    return str(response_obj)
                else:
                    # must return only up to the upper bound of results
                    response_obj["results"] = response_obj["results"][0:int(bound)]
                    return str(response_obj)

    async def propagate_messages(self, message):
        # attempt to send message to each neighbor of server
        for neighbor in server_relations[self.name]:
            try:
                logging.info("Attempting to connect to neighbor {} on port {}".format(neighbor, servers[neighbor]))
                reader, writer = await asyncio.open_connection('127.0.0.1', servers[neighbor])
                writer.write(message.encode())
                await writer.drain()
                logging.info("Connection to {} has been closed.".format(neighbor))
                writer.close()
                await writer.wait_closed()
            except:
                # connection error
                logging.info("Error: cannot connect to server {}".format(neighbor))

    async def run_forever(self):
        server = await asyncio.start_server(self.handle_client_input, self.ip, self.port)
        # Serve requests until Ctrl+C is pressed
        print(f'serving on {server.sockets[0].getsockname()}')
        async with server:
            await server.serve_forever()
        # Close the server
        server.close()

    def validWHATSAT(self, args):
        if len(args) != 4:
            return False
        elif not is_number(args[2]) or not is_number(args[3]):
            return False
        elif int(args[2]) < 0 or int(args[2]) > 50 :
            return False
        elif int(args[3]) < 0 or int(args[3]) > 20:
            return False
        elif args[1] not in self.client_timestamp:
            # can't get WHATSAT for client, since there is no info
            print("No recent location for {}".format(args[1]))
            logging.info("Invalid request received: no recent location for {}".format(args[1]))
            return False
        else:
            return True

def main():
    parser = argparse.ArgumentParser('CS131 project example argument parser')
    parser.add_argument('server_name', type=str,
    help='required server name input')
    args = parser.parse_args()
    if not args.server_name in servers:
        print("Server {} does not exist!".format(args.server_name))
        sys.exit()
        print("Hello, welcome to server {}".format(args.server_name))
    logging.basicConfig(filename="{}.log".format(args.server_name), encoding='utf-8', filemode='w+', level=logging.INFO, format='%(message)s')
    server = Server(args.server_name)
    try:
        asyncio.run(server.run_forever())
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()