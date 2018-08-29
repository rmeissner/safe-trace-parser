import json
import threading
import time
import sys

from web3 import Web3, HTTPProvider, IPCProvider
from web3.middleware import geth_poa_middleware

master_copy = '0x44e7f5855a77fe1793a96be8a1c9c3eaf47e9d09'
provider = IPCProvider("/Users/rimeissner/Library/Ethereum/rinkeby/geth.ipc")
w3 = Web3(provider)
w3.middleware_stack.inject(geth_poa_middleware, layer=0)

def is_safe_tx(call):
    return call['type'] == 'DELEGATECALL' and call['to'] == master_copy

def parse_safe_tx(call, value, from_addr, transactions):
    data = call.get('input')
    safe = call['from']
    safe_txs = transactions.setdefault(safe, {})
    if data and data.startswith("0x09529334"): # executeTransaction entry
        out_txs = safe_txs.setdefault("out", [])
        data_length = int(data[586:650], 16)
        out_txs.append(
            {
                "to": "0x"+data[34:74],
                "value": "0x"+data[74:138],
                "data": "0x"+data[650:650+data_length*2]
            }
        )
    else:
        in_txs = safe_txs.setdefault("in", [])
        in_txs.append(
            {
                "from": from_addr,
                "value": value,
                "data": data
            }
        )

def check_calls(calls, value, from_addr, transactions):
    for call in calls:
        if (is_safe_tx(call)):
            parse_safe_tx(call, value, from_addr, transactions)
        sub_calls = call.get('calls')
        if (sub_calls):
            new_value = call.get('value')
            if (new_value):
                value = new_value
            new_from_addr = call.get('from')
            if (new_from_addr):
                from_addr = new_from_addr
            check_calls(sub_calls, value, from_addr, transactions)

def check_tx(tx, transactions):
    # 0x7400b8811f18957d54cfb67d1331ad3a28075790ab92e70a4c9a5ff15697dadc
    # 0x12d1313c0f61762f425ed52702b388074f80025ee6bf341cdcdfff19cbf51546
    response = provider.make_request("debug_traceTransaction", [ tx, { "tracer": "callTracer" } ])
    info = response["result"]
    calls = info.get('calls')
    if (info['type'] != 'CALL' or not calls):
        return
    check_calls(calls, info['value'], info['from'], transactions)

def check_block(block):
    print("Check block", block, end="\r")
    transactions = { }
    for tx in w3.eth.getBlock(block).transactions:
        check_tx(tx.hex(), transactions)
    for safe, txs in transactions.items():
        print()
        print("############## Transactions for", safe)
        # TODO get nonce of safe and check signaturesc
        out_txs = txs.get("out")
        if out_txs:
            print()
            print("Outgoing transactions")
            print("------------------------------------")
            for tx in out_txs:
                print("to:", tx['to'])
                print("value:", tx['value'])
                print("data:", tx['data'])
                print("------------------------------------")
        in_txs = txs.get("in")
        if in_txs:
            print()
            print("Incoming transactions")
            print("------------------------------------")
            for tx in in_txs:
                print("from:", tx['from'])
                print("value:", tx['value'])
                print("data:", tx['data'])
                print("------------------------------------")
        print()

last_checked_block = w3.eth.blockNumber - 5
while(True):
    if (last_checked_block >= w3.eth.blockNumber):
        time.sleep(5)
    else:
        last_checked_block += 1
        threading.Thread(target=check_block, args=(last_checked_block,)).start()

'''
main_thread = threading.main_thread()
for t in threading.enumerate():
    if t is main_thread:
        continue
    t.join()
'''

