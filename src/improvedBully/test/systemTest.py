# # tests/test_system_bully.py

# autopep8: off
import os
import sys
import time
import threading
import unittest
from unittest.mock import patch

# Assumes src.improvedBully.node and src.message are accessible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from src.improvedBully.node import Node
from src.message import Message
# autopep8: on


class TestSystemBully(unittest.TestCase):
    
    def setUp(self):
        print(f"\n=== Starting {self._testMethodName} ===")
        # Run cluster starts the node threads (as per Node class __init__)
        self.nodes = self.run_cluster(Node, num_nodes=5)
    
    def tearDown(self):
        """ Clean up and stop all node threads. """
        # CRITICAL: Ensures all node threads are terminated cleanly
        for n in self.nodes:
            # Assumes Node class has a stop() method to set self.alive = False
            # and gracefully close sockets/threads.
            if n.alive:
                 # n.stop() and n.join() are highly recommended here!
                 # For now, we set alive to False and rely on daemon threads to exit
                 n.alive = False 
        time.sleep(1) # Give time for daemon threads to finish
        print(f"=== Finished {self._testMethodName} ===\n")
        
    def run_cluster(self, NodeClass, num_nodes=5):
        nodes = []
        known_nodes = list(range(1, num_nodes + 1))

        for i in known_nodes:
            # Node constructor automatically starts its threads
            n = NodeClass(i, known_nodes)
            nodes.append(n)

        time.sleep(2) # Give threads a moment to bind sockets and initialize
        return nodes

    def waitForAllLeaders(self, expected_id, alive_nodes=None, timeout=20):
        """ Waits until all specified nodes have set their leaderId to the expected_id. """
        if alive_nodes is None:
            alive_nodes = self.nodes
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Only check nodes that are meant to be active
            leaders = [n.leaderId for n in alive_nodes if n.alive and n.leaderId is not None]
            
            # Check if all active nodes have set the correct leaderId
            if len(leaders) == len(alive_nodes) and all(l == expected_id for l in leaders):
                print(f"\n[TEST] All alive nodes ({len(alive_nodes)}) agreed on Leader {expected_id}.")
                return True
            time.sleep(0.5) # Polling interval
            
        self.fail(f"Nodes failed to agree on Leader {expected_id} within {timeout}s. Current leaders: {leaders}")

    def test_improved_bully_election(self):
        
        # --- SCENARIO 1: Initial Election (Node 5 becomes leader) ---
        print("\n[TEST] SCENARIO 1: Initial Election.")
        self.nodes[0].startElection(self.nodes[0].knownNodes)
        
        # Wait for all 5 nodes to agree on the highest ID (5)
        expected_leader_1 = 5
        self.waitForAllLeaders(expected_leader_1, timeout=10) 
        
        leaders = [n.leaderId for n in self.nodes if n.leaderId is not None]
        self.assertTrue(all(l == expected_leader_1 for l in leaders),
                        f"Leaders elected: {leaders}, expected: {expected_leader_1}")
        
        # --- SCENARIO 2: Leader Failure and Re-election (Node 4 becomes leader) ---
        print("\n[TEST] SCENARIO 2: Leader (Node 5) failure and Re-election.")
        
        # Simulate Node 5 crash (CRITICAL: Must be a clean stop in Node class)
        self.nodes[4].alive = False
        self.nodes[4].status = "Down"
        # Assuming you would add a stop() method to kill the threads in Node 5
        
        print(f"\n[TEST] Node {self.nodes[4].id} (Leader) is now down.")
        
        # Simulate Node 1 discovering the leader is down (triggers new election)
        # The sendAndWaitForReply should time out and call startElection()
        self.nodes[0].sendAndWaitForReply(5, Message("REQUEST", self.nodes[0].id, 5))
        
        # The new expected leader is the next highest ID (4)
        expected_leader_2 = 4
        alive_nodes_after_failure = self.nodes[:4]
        self.waitForAllLeaders(expected_leader_2, alive_nodes=alive_nodes_after_failure, timeout=15) 

        leaders = [n.leaderId for n in alive_nodes_after_failure if n.alive and n.leaderId is not None]
        self.assertTrue(all(l == expected_leader_2 for l in leaders),
                        f"Leaders elected after failure: {leaders}, expected: {expected_leader_2}")
        
        # --- SCENARIO 3: Leader Recovery and Reclaimation (Node 5 revives) ---
        print("\n[TEST] SCENARIO 3: Original Leader (Node 5) recovery.")

        # Simulate Node 5 recovery (CRITICAL: Must use a proper revive method)
        self.nodes[4].alive = True
        self.nodes[4].status = "Normal"
        # Node 5 needs to restart its threads (listen/processMessages) and call startElection()
        self.nodes[4].startElection(self.nodes[4].knownNodes) # Starts election on revival
        
        # The highest ID (5) should reclaim leadership immediately
        expected_leader_3 = 5
        self.waitForAllLeaders(expected_leader_3, timeout=10) 
        
        leaders = [n.leaderId for n in self.nodes if n.alive and n.leaderId is not None]
        self.assertTrue(all(l == expected_leader_3 for l in leaders),
                        f"Leaders elected after recovery: {leaders}, expected: {expected_leader_3}")
    
    
if __name__ == "__main__":
    unittest.main(verbosity=2)