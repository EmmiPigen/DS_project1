# DS_project1

This repository contains the code for a python implementation of the Bully Election Algorithm and an improved version of the algorithm. The code is located in the `src` folder, containing two folders, `originalBully` and `improvedBully`, each with their respective implementations. Inside each folder, there is a `node.py` file that contains the implementation of the node class, and a `tests` folder that contains unit tests for the implementation. In the `src` folder, there is also two files, containing the class for the message object and a network simulator to simulate the network environment for the nodes.

The implementation was created in python 3.13 and the node utilizes the `socket` library for communication between the nodes and network simulator. The nodes also use the `threading` library to handle multiple connections and messages simultaneously.

## How to run the implementation

To run the implementation, navigate to the `src` folder in your terminal and run the `network_simulator.py` file using the command:

```bash
python network_simulator.py <knownNode1> <knownNode2> ...
```

Where `<knownNode1> <knownNode2> ...` are the node id for the number of nodes you want to create in the network. For example, to create a network with 5 nodes, you would run:

```bash
python network_simulator.py 1 2 3 4 5
```

This will start the network simulator and tell it that 5 nodes will be created with the ids 1, 2, 3, 4 and 5. 

Next you will need to 