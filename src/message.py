#src/utility/message.py

#Class for the message type used by nodes

class Message:
  def __init__(self, type, senderId, targetId, msg = None):
    self.msgType = type
    self.senderId = senderId
    self.targetId = targetId

  def to_dict(self):
    return {
      "type": self.msgType,
      "senderId": self.senderId,
      "targetId": self.targetId
    }
    
    
  def __repr__(self):
    return f"Message(type={self.msgType}, senderId={self.senderId}, targetId={self.targetId})"
    
  def __str__(self):
    return self.__repr__()
  
  
  def __eq__(self, other):
    if not isinstance(other, Message):
      return False
    return (self.msgType == other.msgType and
            self.senderId == other.senderId and
            self.targetId == other.targetId)
