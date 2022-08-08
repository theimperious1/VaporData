abi = '''[
  {
    "inputs": [
      {
        "internalType": "address",
        "name": "account",
        "type": "address"
      }
    ],
    "name": "getAllNodes",
    "outputs": [
      {
        "components": [
          {
            "internalType": "string",
            "name": "name",
            "type": "string"
          },
          {
            "internalType": "uint256",
            "name": "creationTime",
            "type": "uint256"
          },
          {
            "internalType": "uint256",
            "name": "lastClaimTime",
            "type": "uint256"
          },
          {
            "internalType": "uint256",
            "name": "lastCompoundTime",
            "type": "uint256"
          },
          {
            "internalType": "uint256",
            "name": "amount",
            "type": "uint256"
          },
          {
            "internalType": "bool",
            "name": "deleted",
            "type": "bool"
          }
        ],
        "internalType": "struct NodeManager02.NodeEntity[]",
        "name": "",
        "type": "tuple[]"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  }
]'''
