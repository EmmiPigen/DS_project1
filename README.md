# DS_project1

This repository contains the code for a python implementation of the Bully Election Algorithm and an improved version of the algorithm. The code is located in the `src` folder, containing two folders, `originalBully` and `improvedBully`, each with their respective implementations. Inside each folder, there is a `node.py` file that contains the implementation of the node class, and a `tests` folder that contains unit tests for the implementation. In the `src` folder, there is also two files, containing the class for the message object and a network simulator to simulate the network environment for the nodes.

The implementation was created in python 3.13 and the node utilizes the `socket` library for communication between the nodes and network simulator. The nodes also use the `threading` library to handle multiple connections and messages simultaneously.

## How to run the implementation

To run the implementation, navigate to the `src` folder in your terminal and run the `network_simulator.py` file using the command:

```bash
python network_simulator.py <numberOfKnownNodes> 
```

Where `<numberOfKnownNodes>` are the number of nodes you want to create in the network. For example, to create 5 nodes, you would run:

```bash
python network_simulator.py 5
```

This will start the network simulator and initialize with the specified number of nodes as known nodes.

The nodes themselves have to be started manually in separate terminal windows. The process is the same for both the original and improved Bully algorithm.

open a new terminal window and navigate to the `src/originalBully` or `src/improvedBully` folder, depending on which implementation you want to run. Then, run the `node.py` file using the command:

```bash
python node.py <nodeId> <numberOfKnownNodes>
```

Where `<nodeId>` is the ID of the node you want to start (from 1 to N) and `<numberOfKnownNodes>` is the total number of nodes in the network. For example, to start node 1 in a network with 5 nodes, you would run:
```
python node.py 1 5
```
Each node will start and listen for messages from the network simulator and respond accordingly.

The nodes include commands that can be entered in the terminal to start an election, "kill" the node (simulating a failure), or "revive" the node (simulating a recovery), sending a "REQUEST REPLY" message to a specific node, e.g. "contact 3" to send a message to node 3.

The commands are:
- `election`: Start an election
- `status`: Print the status of the node (its ID, known nodes, node status(normal/down/election), alive status, and leader ID)
- `die`: Simulate a node failure - closing the socket connection
- `revive`: Simulate a node recovery - restarting the thread and socket connection
- `contact <nodeId>`: Send a "REQUEST" message to the specified node ID and wait for a "REPLY" message
- `exit`: Exit the node program

## Tests
Unit tests for both implementations can be found in the `tests` folder inside each implementation folder. The tests can be run using the command:

```bash
python -m unittest .\unitTest.py
```
This will run all the unit tests and display the results in the terminal.

## Note 
The implementation is a simulation and does not handle all edge cases or failures that may occur in a real distributed system. It is intended for educational purposes to demonstrate the Bully Election Algorithm and its improved version.

The implementation assumes that all nodes are started manually and that the network simulator is running before starting any nodes, initial election are not automatically started when nodes are started, and should be initiated manually by entering the `election` command in the node terminal.

When node recovers (revive command), it does automatically start an election, as per the Bully algorithm specification.
