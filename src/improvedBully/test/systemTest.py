# tests/test_system_bully.py

# autopep8: off
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.improvedBully.node import Node
from src.message import Message

import time
import threading
from unittest.mock import patch
import unittest

# autopep8: on


class TestSystemBully(unittest.TestCase):
  def setUp(self):
    print(f"\n=== Starting {self._testMethodName} ===")
    
    self.nodes = self.run_cluster(Node, num_nodes=5)
    
  
  def tearDown(self):
    """ Clean up after tests. """
    # Default tearDown just marks test end
    print(f"=== Finished {self._testMethodName} ===\n")
        
  def run_cluster(self, NodeClass, num_nodes=3):
    nodes = []
    known_nodes = list(range(1, num_nodes + 1))

    #with patch("time.sleep", return_value=None):
    for i in known_nodes:
      n = NodeClass(i, known_nodes)
      nodes.append(n)

    time.sleep(1) # allow threads to start

    return nodes

  def test_improved_bully_election(self):
    self.nodes[4].startElection([1, 2, 3, 4, 5])
    time.sleep(5)  # allow some time for the message exchanges    
    
    # In Bully algorithm, highest ID becomes leader
    expected = 5
    leaders = [n.leaderId for n in self.nodes if n.leaderId is not None]
    self.assertTrue(all(l == expected for l in leaders),
                    f"Leaders elected: {leaders}, expected: {expected}")
    
    time.sleep(5)  # allow some time for all message to be processed
    
    #Test failure of leader and re-election
    self.nodes[4].alive = False
    self.nodes[4].status = "Down"
    self.assertEqual(self.nodes[4].status, "Down")
    print(f"\n[TEST] Node {self.nodes[4].id} (Leader) is down.")
    
    # Simulate Node 1 sending request to node 5 and discover it's down
    self.nodes[0].sendAndWaitForReply(5, Message("REQUEST", self.nodes[0].id, 5))
    
    time.sleep(25) # give time for election
    
    # New leader should be the next-highest
    expected = 4
    leaders = [n.leaderId for n in self.nodes if n.alive and n.leaderId is not None]
    self.assertTrue(all(l == expected for l in leaders),
                    f"Leaders elected after failure: {leaders}, expected: {expected}")
    
    # Test recovery of original leader
    self.nodes[4].alive = True
    self.nodes[4].status = "Normal"
    self.nodes[4].startElection([1, 2, 3, 4, 5])
    
    time.sleep(5)  # allow some time for the message exchanges
    
    # Original leader should reclaim leadership
    expected = 5
    leaders = [n.leaderId for n in self.nodes if n.alive and n.leaderId is not None]
    self.assertTrue(all(l == expected for l in leaders),
                    f"Leaders elected after recovery: {leaders}, expected: {expected}")
    
    
    
    
if __name__ == "__main__":
  unittest.main(verbosity=2)
